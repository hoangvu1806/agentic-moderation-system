import argparse
import asyncio
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from rich.console import Console
from rich.json import JSON
from rich.markup import escape
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table
from rich.text import Text


ROOT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = ROOT_DIR / "backend"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.agents import (
    ContentSignalAgent,
    DomainIntakeAgent,
    ExplanationAgent,
    ImageSignalAgent,
    ModerationEvidenceAgent,
)
from app.kogito import (
    KogitoClientError,
    create_domain_classifier_client,
    create_kogito_http_client,
    create_workflow_client,
)
from app.repositories.moderation_repository import ModerationRepository
from app.schemas.moderation import ModerationRequest
from app.services.moderation_service import ModerationService


@dataclass(frozen=True)
class PipelineCliInput:
    text: str
    image_urls: list[str]
    metadata: dict[str, Any]
    stream_events: bool
    json_output: bool
    output_path: Path | None


@dataclass
class PipelineRunContext:
    run_index: int
    total_runs: int
    image_url: str | None


async def run_pipeline(cli_input: PipelineCliInput, console: Console) -> int:
    http_client = create_kogito_http_client()
    moderation_service = ModerationService(
        domain_intake_agent=DomainIntakeAgent(),
        domain_classifier_client=create_domain_classifier_client(http_client),
        content_signal_agent=ContentSignalAgent(),
        image_signal_agent=ImageSignalAgent(),
        evidence_agent=ModerationEvidenceAgent(),
        workflow_client=create_workflow_client(http_client),
        explanation_agent=ExplanationAgent(),
        repository=ModerationRepository(),
    )

    try:
        if not cli_input.json_output:
            render_startup(console, cli_input)
        result = await run_requests(moderation_service, cli_input, console)
    except KogitoClientError as exc:
        render_error(console, "Kogito moderation service is unavailable", str(exc), cli_input.json_output)
        return 1
    except ValueError as exc:
        render_error(console, str(exc), "", cli_input.json_output)
        return 1
    finally:
        await http_client.close()

    write_output(cli_input.output_path, result)
    if cli_input.json_output:
        print_json(result, sys.stdout)
    elif cli_input.output_path is not None:
        console.print(f"[dim]Full JSON written to[/dim] [cyan]{escape(str(cli_input.output_path))}[/cyan]")
    return 0


async def run_requests(
    moderation_service: ModerationService,
    cli_input: PipelineCliInput,
    console: Console,
) -> dict[str, Any]:
    request_image_urls = cli_input.image_urls or [None]
    runs = []

    for run_index, image_url in enumerate(request_image_urls, start=1):
        run_context = PipelineRunContext(
            run_index=run_index,
            total_runs=len(request_image_urls),
            image_url=image_url,
        )
        request = ModerationRequest(
            text=cli_input.text,
            image_url=image_url,
            metadata=build_run_metadata(cli_input.metadata, cli_input.image_urls, run_index, image_url),
        )
        response = await run_single_request(moderation_service, request, cli_input, run_context, console)
        runs.append({"run_index": run_index, "image_url": image_url, "response": response})

    if len(runs) == 1:
        return runs[0]["response"]
    return {"runs": runs}


async def run_single_request(
    moderation_service: ModerationService,
    request: ModerationRequest,
    cli_input: PipelineCliInput,
    run_context: PipelineRunContext,
    console: Console,
) -> dict[str, Any]:
    if cli_input.json_output and not cli_input.stream_events:
        response = await moderation_service.moderate(request)
        return response.model_dump(mode="json")

    final_response: dict[str, Any] | None = None
    if cli_input.json_output:
        async for event in moderation_service.moderate_events(request):
            print_json_line(event, sys.stdout)
            if event["stage"] == "complete":
                final_response = event["output"]
    else:
        final_response = await run_with_realtime_output(moderation_service, request, run_context, console)

    if final_response is None:
        raise ValueError("Pipeline did not return a final response")
    return final_response


async def run_with_realtime_output(
    moderation_service: ModerationService,
    request: ModerationRequest,
    run_context: PipelineRunContext,
    console: Console,
) -> dict[str, Any] | None:
    final_response: dict[str, Any] | None = None
    task_by_stage: dict[str, int] = {}

    console.print(run_header(run_context))
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        TimeElapsedColumn(),
        console=console,
        transient=False,
    ) as progress:
        async for event in moderation_service.moderate_events(request):
            render_event(progress, task_by_stage, event)
            if event["stage"] == "complete":
                final_response = event["output"]

    if final_response is not None:
        render_final_response(console, final_response)
    return final_response


def build_run_metadata(
    base_metadata: dict[str, Any],
    image_urls: list[str],
    run_index: int,
    image_url: str | None,
) -> dict[str, Any]:
    metadata = dict(base_metadata)
    metadata.update(
        {
            "cli_run_index": run_index,
            "cli_image_count": len(image_urls),
            "cli_image_urls": image_urls,
        }
    )
    if image_url is not None:
        metadata["cli_current_image_url"] = image_url
    return metadata


def parse_args() -> PipelineCliInput:
    parser = argparse.ArgumentParser(description="Run the full moderation pipeline from the CLI.")
    text_group = parser.add_mutually_exclusive_group(required=True)
    text_group.add_argument("--text", help="Post text to moderate.")
    text_group.add_argument("--text-file", type=Path, help="Path to a UTF-8 text file containing the post.")
    parser.add_argument("--image-path", action="append", default=[], type=Path, help="Local image path. Can be repeated.")
    parser.add_argument("--image-url", action="append", default=[], help="Image URL or URI. Can be repeated.")
    parser.add_argument("--metadata-json", default="{}", help="JSON object passed to the moderation metadata field.")
    parser.add_argument("--stream", action="store_true", help="Stream every pipeline event. Pretty by default, JSON lines with --json.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON instead of rich terminal output.")
    parser.add_argument("--output", type=Path, help="Optional path to write the final JSON result.")
    args = parser.parse_args()

    return PipelineCliInput(
        text=read_text(args.text, args.text_file),
        image_urls=collect_image_urls(args.image_path, args.image_url),
        metadata=parse_metadata(args.metadata_json),
        stream_events=args.stream,
        json_output=args.json,
        output_path=args.output,
    )


def read_text(inline_text: str | None, text_file: Path | None) -> str:
    if inline_text is not None:
        return validate_text(inline_text)
    if text_file is None:
        raise ValueError("Either --text or --text-file is required")
    if not text_file.is_file():
        raise ValueError(f"Text file does not exist: {text_file}")
    return validate_text(text_file.read_text(encoding="utf-8"))


def validate_text(text: str) -> str:
    normalized_text = text.strip()
    if not normalized_text:
        raise ValueError("Input text must not be empty")
    return normalized_text


def collect_image_urls(image_paths: list[Path], image_urls: list[str]) -> list[str]:
    path_urls = [image_path_to_uri(image_path) for image_path in image_paths]
    cleaned_urls = [image_url.strip() for image_url in image_urls if image_url.strip()]
    return path_urls + cleaned_urls


def image_path_to_uri(image_path: Path) -> str:
    resolved_path = image_path.expanduser().resolve()
    if not resolved_path.is_file():
        raise ValueError(f"Image path does not exist: {image_path}")
    return resolved_path.as_uri()


def parse_metadata(metadata_json: str) -> dict[str, Any]:
    try:
        metadata = json.loads(metadata_json)
    except json.JSONDecodeError as exc:
        raise ValueError("--metadata-json must be valid JSON") from exc
    if not isinstance(metadata, dict):
        raise ValueError("--metadata-json must be a JSON object")
    return metadata


def write_output(output_path: Path | None, result: dict[str, Any]) -> None:
    if output_path is None:
        return
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


def print_json(payload: dict[str, Any], output: Any) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2), file=output)


def print_json_line(payload: dict[str, Any], output: Any) -> None:
    print(json.dumps(payload, ensure_ascii=False), file=output)


def render_startup(console: Console, cli_input: PipelineCliInput) -> None:
    image_count = len(cli_input.image_urls)
    metadata_keys = ", ".join(sorted(cli_input.metadata.keys())) or "none"
    table = Table.grid(padding=(0, 2))
    table.add_column(style="bold cyan")
    table.add_column()
    table.add_row("Text", f"{len(cli_input.text)} characters")
    table.add_row("Images", str(image_count))
    table.add_row("Metadata", metadata_keys)
    table.add_row("Mode", "realtime events")
    console.print(Panel(table, title="[bold]Moderation Pipeline CLI[/bold]", border_style="cyan"))


def run_header(run_context: PipelineRunContext) -> Panel:
    title = f"Run {run_context.run_index}/{run_context.total_runs}"
    image_text = run_context.image_url or "text-only"
    return Panel(Text(image_text, overflow="fold"), title=title, border_style="blue")


def render_event(progress: Progress, task_by_stage: dict[str, int], event: dict[str, Any]) -> None:
    stage = str(event.get("stage", "unknown"))
    status = str(event.get("status", "unknown"))
    description = event_description(event)

    if stage not in task_by_stage:
        task_by_stage[stage] = progress.add_task(description, total=None)
    task_id = task_by_stage[stage]

    if status in {"completed", "skipped", "failed"}:
        progress.update(task_id, description=description, completed=1, total=1)
        progress.stop_task(task_id)
        return

    progress.update(task_id, description=description)


def event_description(event: dict[str, Any]) -> str:
    stage = str(event.get("stage", "unknown"))
    status = str(event.get("status", "unknown"))
    output = event.get("output") if isinstance(event.get("output"), dict) else {}
    stage_label = STAGE_LABELS.get(stage, stage.replace("_", " ").title())
    status_style = STATUS_STYLES.get(status, "white")
    detail = event_detail(stage, status, output)
    return f"[bold]{stage_label}[/bold] [{status_style}]{status}[/] {detail}"


def event_detail(stage: str, status: str, output: dict[str, Any]) -> str:
    if status == "in_progress" and output.get("message"):
        return f"[dim]- {escape(str(output['message']))}[/dim]"
    if stage == "classifier" and status == "completed":
        domain = escape(str(output.get("detected_domain", "UNKNOWN")))
        confidence = escape(str(output.get("domain_confidence", "?")))
        return f"[dim]- domain={domain} confidence={confidence}[/dim]"
    if stage == "text_signal" and status == "completed":
        risk = escape(str(output.get("primary_risk", "NONE")))
        labels = escape(format_list(output.get("topic_labels", [])))
        return f"[dim]- risk={risk} labels={labels}[/dim]"
    if stage == "image_signal" and status == "completed":
        image_risk = escape(str(output.get("image_risk_score", 0)))
        labels = escape(format_list(output.get("image_policy_labels", [])))
        return f"[dim]- image_risk={image_risk} labels={labels}[/dim]"
    if stage == "workflow" and status == "completed":
        decision = escape(str(output.get("dmn_decision", "?")))
        workflow_status = escape(str(output.get("status", "?")))
        return f"[dim]- decision={decision} status={workflow_status}[/dim]"
    if stage == "explanation" and status == "completed":
        return "[dim]- explanation ready[/dim]"
    if stage == "complete":
        return "[dim]- final response ready[/dim]"
    return ""


def render_final_response(console: Console, response: dict[str, Any]) -> None:
    explanations = response.get("explanations", {})
    signals = response.get("signals", {})
    console.print(summary_panel(response, explanations, signals))
    render_reasons(console, explanations)
    render_recommended_edits(console, explanations)


def summary_panel(
    response: dict[str, Any],
    explanations: dict[str, Any],
    signals: dict[str, Any],
) -> Panel:
    decision = str(response.get("decision", "UNKNOWN"))
    status = str(response.get("status", "UNKNOWN"))
    table = Table.grid(padding=(0, 2))
    table.add_column(style="bold cyan")
    table.add_column()
    table.add_row("Content ID", Text(str(response.get("content_id", ""))))
    table.add_row("Domain", Text(str(response.get("detected_domain", "UNKNOWN"))))
    table.add_row("Decision", colored_decision(decision))
    table.add_row("Status", colored_status(status))
    table.add_row("Primary risk", Text(str(signals.get("primary_risk", "NONE"))))
    table.add_row("Message", Text(str(response.get("message", ""))))
    if explanations.get("verdict_summary"):
        table.add_row("Summary", Text(str(explanations["verdict_summary"])))
    if explanations.get("article_commentary"):
        table.add_row("Commentary", Text(str(explanations["article_commentary"])))
    return Panel(table, title="[bold]Final Result[/bold]", border_style=decision_border_style(decision))


def render_reasons(console: Console, explanations: dict[str, Any]) -> None:
    reasons = list_text(explanations.get("policy_reasons"))
    if not reasons:
        return
    table = Table(title="Policy Reasons", border_style="yellow", show_lines=False)
    table.add_column("#", style="dim", width=4)
    table.add_column("Reason")
    for index, reason in enumerate(reasons, start=1):
        table.add_row(str(index), Text(reason))
    console.print(table)


def render_recommended_edits(console: Console, explanations: dict[str, Any]) -> None:
    edits = list_text(explanations.get("recommended_edits"))
    if not edits:
        return
    table = Table(title="Recommended Edits", border_style="green", show_lines=False)
    table.add_column("#", style="dim", width=4)
    table.add_column("Edit")
    for index, edit in enumerate(edits, start=1):
        table.add_row(str(index), Text(edit))
    console.print(table)


def render_error(console: Console, message: str, detail: str, json_output: bool) -> None:
    payload = {"error": message}
    if detail:
        payload["detail"] = detail
    if json_output:
        print_json(payload, sys.stderr)
        return
    console.print(Panel(JSON.from_data(payload), title="[bold red]Error[/bold red]", border_style="red"))


def colored_decision(decision: str) -> str:
    style = {
        "ALLOW": "bold green",
        "WARN_ALLOW": "bold yellow",
        "REJECT": "bold red",
        "MANUAL_REVIEW": "bold magenta",
    }.get(decision, "bold white")
    return f"[{style}]{decision}[/]"


def colored_status(status: str) -> str:
    style = {
        "PUBLISHED": "green",
        "PUBLISHED_WITH_WARNING": "yellow",
        "REJECTED": "red",
        "PENDING_HUMAN_REVIEW": "magenta",
    }.get(status, "white")
    return f"[{style}]{status}[/]"


def decision_border_style(decision: str) -> str:
    return {
        "ALLOW": "green",
        "WARN_ALLOW": "yellow",
        "REJECT": "red",
        "MANUAL_REVIEW": "magenta",
    }.get(decision, "white")


def format_list(value: Any) -> str:
    items = list_text(value)
    if not items:
        return "none"
    return ", ".join(items[:4])


def list_text(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def configure_output_encoding() -> None:
    for output in (sys.stdout, sys.stderr):
        if hasattr(output, "reconfigure"):
            output.reconfigure(encoding="utf-8")


STAGE_LABELS = {
    "intake": "Domain Intake",
    "classifier": "Domain Classifier",
    "signals": "Signal Phase",
    "text_signal": "Text Signal Agent",
    "image_signal": "Image Signal Agent",
    "evidence": "Evidence Builder",
    "workflow": "Kogito Workflow",
    "explanation": "Explanation Agent",
    "complete": "Complete",
}

STATUS_STYLES = {
    "started": "cyan",
    "in_progress": "yellow",
    "completed": "green",
    "skipped": "dim",
    "failed": "red",
}


def main() -> int:
    configure_output_encoding()
    load_dotenv(ROOT_DIR / ".env")
    console = Console()
    json_output_requested = "--json" in sys.argv
    try:
        cli_input = parse_args()
    except ValueError as exc:
        render_error(console, str(exc), "", json_output=json_output_requested)
        return 1
    return asyncio.run(run_pipeline(cli_input, console))


if __name__ == "__main__":
    raise SystemExit(main())

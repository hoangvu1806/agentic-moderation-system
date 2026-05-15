import asyncio
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from app.repositories.moderation_repository import ModerationRepository
from app.schemas.moderation import (
    ContentStatus,
    ModerationDecision,
    ModerationRecord,
    ModerationRequest,
    ModerationResponse,
    ROUTABLE_DOMAIN_VALUES,
)


class ModerationService:
    def __init__(
        self,
        domain_intake_agent: Any,
        domain_classifier_client: Any,
        content_signal_agent: Any,
        image_signal_agent: Any,
        evidence_agent: Any,
        workflow_client: Any,
        explanation_agent: Any,
        repository: ModerationRepository,
    ) -> None:
        self._domain_intake_agent = domain_intake_agent
        self._domain_classifier_client = domain_classifier_client
        self._content_signal_agent = content_signal_agent
        self._image_signal_agent = image_signal_agent
        self._evidence_agent = evidence_agent
        self._workflow_client = workflow_client
        self._explanation_agent = explanation_agent
        self._repository = repository

    async def moderate(self, request: ModerationRequest) -> ModerationResponse:
        content_id = f"CNT-{uuid.uuid4().hex[:12].upper()}"
        classification_input = await self._domain_intake_agent.prepare_classification_payload(
            text=request.text,
            image_url=request.image_url,
            metadata=request.metadata,
        )
        classification = await self._domain_classifier_client.classify_domain(classification_input)

        content_signals, image_signals = await self._run_signal_agents(content_id, request, classification)
        evidence = self._evidence_agent.build_evidence(
            content_id=content_id,
            classification=classification,
            content_signals=content_signals,
            image_signals=image_signals,
        )
        workflow = await self._workflow_client.start_pre_publication_moderation(
            evidence["process_variables"],
            business_key=content_id,
        )

        signals = _response_signals(content_signals, image_signals)
        explanations = await self._explanation_agent.explain(
            content_id=content_id,
            request=request,
            classification=classification,
            workflow=workflow,
            signals=signals,
            evidence=evidence,
        )
        response = _moderation_response(
            content_id=content_id,
            classification=classification,
            workflow=workflow,
            signals=signals,
            evidence=evidence,
            explanations=explanations,
        )
        self._repository.save(ModerationRecord(content_id=content_id, request=request, response=response))
        return response

    async def moderate_events(self, request: ModerationRequest) -> AsyncIterator[dict[str, Any]]:
        content_id = f"CNT-{uuid.uuid4().hex[:12].upper()}"

        yield _agent_event("intake", "started", content_id=content_id)
        intake_task = asyncio.create_task(
            self._domain_intake_agent.prepare_classification_payload(
                text=request.text,
                image_url=request.image_url,
                metadata=request.metadata,
            )
        )
        while True:
            completed_tasks, pending_tasks = await asyncio.wait(
                {intake_task},
                timeout=0.6,
                return_when=asyncio.FIRST_COMPLETED,
            )
            if completed_tasks:
                classification_input = intake_task.result()
                break
            if pending_tasks:
                yield _agent_event(
                    "intake",
                    "in_progress",
                    content_id=content_id,
                    output={"message": "Preparing classification payload"},
                )
        yield _agent_event("intake", "completed", content_id=content_id, output=classification_input)

        yield _agent_event("classifier", "started", content_id=content_id)
        classifier_task = asyncio.create_task(
            self._domain_classifier_client.classify_domain(classification_input)
        )
        while True:
            completed_tasks, pending_tasks = await asyncio.wait(
                {classifier_task},
                timeout=0.6,
                return_when=asyncio.FIRST_COMPLETED,
            )
            if completed_tasks:
                classification = classifier_task.result()
                break
            if pending_tasks:
                yield _agent_event(
                    "classifier",
                    "in_progress",
                    content_id=content_id,
                    output={"message": "Running domain classification decision"},
                )
        yield _agent_event("classifier", "completed", content_id=content_id, output=classification)

        yield _agent_event("signals", "started", content_id=content_id)
        detected_domain = str(classification.get("detected_domain", "UNKNOWN"))
        if detected_domain not in ROUTABLE_DOMAIN_VALUES:
            content_signals = _empty_content_signals()
            image_signals = None
            yield _agent_event("text_signal", "skipped", content_id=content_id, output=content_signals)
            yield _agent_event("image_signal", "skipped", content_id=content_id, output={"has_image": False})
            yield _agent_event("signals", "completed", content_id=content_id, output={"mode": "bypassed"})
        else:
            yield _agent_event("text_signal", "started", content_id=content_id)
            content_task = asyncio.create_task(
                self._content_signal_agent.analyze_text(
                    content_id=content_id,
                    text=request.text,
                    detected_domain=detected_domain,
                    content_prompt_profile=str(classification["content_prompt_profile"]),
                    metadata=request.metadata,
                )
            )

            image_task: asyncio.Task[dict[str, Any]] | None = None
            if request.image_url:
                yield _agent_event("image_signal", "started", content_id=content_id)
                image_task = asyncio.create_task(
                    self._image_signal_agent.analyze_image(
                        content_id=content_id,
                        image_url=request.image_url,
                        detected_domain=detected_domain,
                        image_prompt_profile=str(classification.get("image_prompt_profile", "")),
                        metadata=request.metadata,
                    )
                )
            else:
                yield _agent_event("image_signal", "skipped", content_id=content_id, output={"has_image": False})

            content_signals = None
            image_signals = None
            pending_tasks = {content_task}
            if image_task is not None:
                pending_tasks.add(image_task)

            while pending_tasks:
                completed_tasks, pending_tasks = await asyncio.wait(
                    pending_tasks,
                    timeout=0.6,
                    return_when=asyncio.FIRST_COMPLETED,
                )
                if not completed_tasks:
                    yield _agent_event(
                        "signals",
                        "in_progress",
                        content_id=content_id,
                        output={"pending_tasks": len(pending_tasks)},
                    )
                    continue
                for completed_task in completed_tasks:
                    if completed_task is content_task:
                        content_signals = completed_task.result()
                        yield _agent_event("text_signal", "completed", content_id=content_id, output=content_signals)
                    elif image_task is not None and completed_task is image_task:
                        image_signals = completed_task.result()
                        yield _agent_event("image_signal", "completed", content_id=content_id, output=image_signals)

            if content_signals is None:
                raise ValueError("content signals are missing")
            yield _agent_event("signals", "completed", content_id=content_id, output={"mode": "parallel"})

        yield _agent_event("evidence", "started", content_id=content_id)
        evidence = self._evidence_agent.build_evidence(
            content_id=content_id,
            classification=classification,
            content_signals=content_signals,
            image_signals=image_signals,
        )
        yield _agent_event(
            "evidence",
            "completed",
            content_id=content_id,
            output={"evidence_id": evidence["evidence_id"], "process_id": evidence["process_id"]},
        )

        yield _agent_event("workflow", "started", content_id=content_id)
        workflow_task = asyncio.create_task(
            self._workflow_client.start_pre_publication_moderation(
                evidence["process_variables"],
                business_key=content_id,
            )
        )
        while True:
            completed_tasks, pending_tasks = await asyncio.wait(
                {workflow_task},
                timeout=0.6,
                return_when=asyncio.FIRST_COMPLETED,
            )
            if completed_tasks:
                workflow = workflow_task.result()
                break
            if pending_tasks:
                yield _agent_event(
                    "workflow",
                    "in_progress",
                    content_id=content_id,
                    output={"message": "Evaluating DMN decision"},
                )
        yield _agent_event("workflow", "completed", content_id=content_id, output={key: value for key, value in workflow.items() if key != "raw"})

        signals = _response_signals(content_signals, image_signals)
        yield _agent_event("explanation", "started", content_id=content_id)
        explanations = await self._explanation_agent.explain(
            content_id=content_id,
            request=request,
            classification=classification,
            workflow=workflow,
            signals=signals,
            evidence=evidence,
        )
        yield _agent_event("explanation", "completed", content_id=content_id, output=explanations)

        response = _moderation_response(
            content_id=content_id,
            classification=classification,
            workflow=workflow,
            signals=signals,
            evidence=evidence,
            explanations=explanations,
        )
        self._repository.save(ModerationRecord(content_id=content_id, request=request, response=response))
        yield _agent_event("complete", "completed", content_id=content_id, output=response.model_dump(mode="json"))

    async def _run_signal_agents(
        self,
        content_id: str,
        request: ModerationRequest,
        classification: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any] | None]:
        detected_domain = str(classification.get("detected_domain", "UNKNOWN"))
        if detected_domain not in ROUTABLE_DOMAIN_VALUES:
            return _empty_content_signals(), None

        content_task = self._content_signal_agent.analyze_text(
            content_id=content_id,
            text=request.text,
            detected_domain=detected_domain,
            content_prompt_profile=str(classification["content_prompt_profile"]),
            metadata=request.metadata,
        )
        if not request.image_url:
            return await content_task, None

        image_task = self._image_signal_agent.analyze_image(
            content_id=content_id,
            image_url=request.image_url,
            detected_domain=detected_domain,
            image_prompt_profile=str(classification.get("image_prompt_profile", "")),
            metadata=request.metadata,
        )
        content_signals, image_signals = await asyncio.gather(content_task, image_task)
        return content_signals, image_signals

    async def _run_signal_agents_with_events(
        self,
        content_id: str,
        request: ModerationRequest,
        classification: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any] | None]:
        detected_domain = str(classification.get("detected_domain", "UNKNOWN"))
        if detected_domain not in ROUTABLE_DOMAIN_VALUES:
            return _empty_content_signals(), None

        content_task = asyncio.create_task(
            self._content_signal_agent.analyze_text(
                content_id=content_id,
                text=request.text,
                detected_domain=detected_domain,
                content_prompt_profile=str(classification["content_prompt_profile"]),
                metadata=request.metadata,
            )
        )

        if not request.image_url:
            content_signals = await content_task
            return content_signals, None

        image_task = asyncio.create_task(
            self._image_signal_agent.analyze_image(
                content_id=content_id,
                image_url=request.image_url,
                detected_domain=detected_domain,
                image_prompt_profile=str(classification.get("image_prompt_profile", "")),
                metadata=request.metadata,
            )
        )
        content_signals: dict[str, Any] | None = None
        image_signals: dict[str, Any] | None = None
        pending_tasks = {content_task, image_task}
        while pending_tasks:
            completed_tasks, pending_tasks = await asyncio.wait(
                pending_tasks,
                return_when=asyncio.FIRST_COMPLETED,
            )
            for completed_task in completed_tasks:
                if completed_task is content_task:
                    content_signals = completed_task.result()
                else:
                    image_signals = completed_task.result()

        if content_signals is None:
            raise ValueError("content signals are missing")
        return content_signals, image_signals


def _empty_content_signals() -> dict[str, Any]:
    return {
        "language": "unknown",
        "topic_labels": [],
        "primary_risk": "NONE",
        "matched_signals": [],
        "generic_scores": {},
    }


def _agent_event(
    stage: str,
    status: str,
    *,
    content_id: str,
    output: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "stage": stage,
        "status": status,
        "content_id": content_id,
        "ts": datetime.now(UTC).isoformat(),
        "output": output or {},
    }


def _moderation_response(
    content_id: str,
    classification: dict[str, Any],
    workflow: dict[str, Any],
    signals: dict[str, Any],
    evidence: dict[str, Any],
    explanations: dict[str, Any],
) -> ModerationResponse:
    return ModerationResponse(
        content_id=content_id,
        status=ContentStatus(str(workflow.get("status", ContentStatus.PENDING_HUMAN_REVIEW.value))),
        decision=_api_decision(str(workflow.get("dmn_decision", "MANUAL_REVIEW"))),
        message=str(explanations["user_message"]),
        detected_domain=classification["detected_domain"],
        analysis_profile=str(classification["analysis_profile"]),
        workflow={key: value for key, value in workflow.items() if key != "raw"},
        signals=signals,
        evidence={"evidence_id": evidence["evidence_id"]},
        explanations=explanations,
    )


def _api_decision(dmn_decision: str) -> ModerationDecision:
    if dmn_decision.upper() == "TEMP_BAN":
        return ModerationDecision.REJECT
    try:
        return ModerationDecision(dmn_decision.upper())
    except ValueError:
        return ModerationDecision.MANUAL_REVIEW


def _response_signals(
    content_signals: dict[str, Any],
    image_signals: dict[str, Any] | None,
) -> dict[str, Any]:
    generic_scores = content_signals.get("generic_scores", {})
    signals = {
        "language": content_signals.get("language", "unknown"),
        "topic_labels": content_signals.get("topic_labels", []),
        "primary_risk": content_signals.get("primary_risk", "NONE"),
        "matched_signals": content_signals.get("matched_signals", []),
        **generic_scores,
    }
    for key, value in content_signals.items():
        if key.endswith("_scores") and isinstance(value, dict):
            signals.update(value)
    if image_signals:
        signals.update(
            {
                "has_image": bool(image_signals.get("has_image", True)),
                "image_risk_score": image_signals.get("image_risk_score", 0.0),
                "image_policy_labels": image_signals.get("image_policy_labels", []),
                "image_matched_signals": image_signals.get("image_matched_signals", []),
                "image_ocr_text": image_signals.get("image_ocr_text", ""),
            }
        )
    else:
        signals.update(
            {
                "has_image": False,
                "image_risk_score": 0.0,
                "image_policy_labels": [],
                "image_matched_signals": [],
                "image_ocr_text": "",
            }
        )
    return signals

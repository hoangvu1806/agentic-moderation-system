import json
import uuid
from typing import Any

from google.adk.agents.llm_agent import Agent
from google.adk.runners import InMemoryRunner
from google.genai import types


DEFAULT_MODEL = "gemini-2.5-flash"
SYSTEM_USER_ID = "system"


class JsonAdkAgent:
    """wrapper for agentsreturn one JSON object."""

    def __init__(
        self,
        app_name: str,
        name: str,
        description: str,
        instruction: str,
        model: str = DEFAULT_MODEL,
    ) -> None:
        self._app_name = app_name
        self._runner = InMemoryRunner(
            app_name=app_name,
            agent=Agent(
                model=model,
                name=name,
                description=description,
                instruction=instruction,
            ),
        )

    async def run_json(self, payload: dict[str, Any]) -> dict[str, Any]:
        session_id = str(uuid.uuid4())
        await self._runner.session_service.create_session(
            app_name=self._app_name,
            user_id=SYSTEM_USER_ID,
            session_id=session_id,
        )

        message = types.Content(
            role="user",
            parts=[types.Part.from_text(text=json.dumps(payload, ensure_ascii=False))],
        )

        final_text = "{}"
        async for event in self._runner.run_async(
            user_id=SYSTEM_USER_ID,
            session_id=session_id,
            new_message=message,
        ):
            event_text = _event_text(event)
            if event_text:
                final_text = event_text

        try:
            result = json.loads(strip_json_fence(final_text))
        except json.JSONDecodeError as exc:
            raise ValueError("Agent returned invalid JSON") from exc

        if not isinstance(result, dict):
            raise ValueError("Agent must return a JSON object")
        return result


def normalize_text(text: str) -> str:
    return " ".join(text.strip().split())


def require_text(value: str, field_name: str) -> str:
    cleaned = normalize_text(value)
    if not cleaned:
        raise ValueError(f"{field_name} must not be empty")
    return cleaned


def clamp_score(value: Any) -> float:
    return max(0.0, min(1.0, float(value or 0.0)))


def string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def metadata_text(
    metadata: dict[str, Any] | None,
    key: str,
    default_value: str,
) -> str:
    value = (metadata or {}).get(key, default_value)
    return str(value).strip() or default_value


def strip_json_fence(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```json"):
        return cleaned.removeprefix("```json").removesuffix("```").strip()
    if cleaned.startswith("```"):
        return cleaned.removeprefix("```").removesuffix("```").strip()
    return cleaned


def _event_text(event: Any) -> str:
    if not getattr(event, "content", None) or not event.content.parts:
        return ""
    return "".join(part.text or "" for part in event.content.parts).strip()

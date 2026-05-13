import json
import uuid
from typing import Any

from google.adk.agents.llm_agent import Agent
from google.adk.runners import InMemoryRunner
from google.genai import types


TEXT_PREVIEW_MAX_LENGTH = 240
DEFAULT_MODEL = "gemini-2.0-flash"
UNKNOWN_VALUE = "unknown"


class DomainIntakeAgent:
    """Chuẩn bị classification payload trước khi gọi DomainClassificationDecision.dmn."""

    def __init__(self, model: str = DEFAULT_MODEL) -> None:
        self._runner = InMemoryRunner(
            app_name="domain_intake_agent",
            agent=Agent(
                model=model,
                name="domain_intake_agent",
                description="Classifies post domain hints for Kogito DMN.",
                instruction=(
                    "Return only JSON with keys: domain_hint, confidence, "
                    "topic_hints, language_hint. "
                    "domain_hint must be one of EDTECH, ECOMMERCE, REAL_ESTATE, "
                    "HEALTHCARE, ENTERPRISE_HR, UNKNOWN. "
                    "Map product reviews, listings, promotions, QR payment, and marketplace posts to ECOMMERCE. "
                    "Do not return moderation decisions."
                ),
            ),
        )

    async def prepare_classification_payload(
        self,
        text: str,
        image_url: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        normalized_text = " ".join(text.strip().split())
        if not normalized_text:
            raise ValueError("text must not be empty")

        text_preview = self._shorten_text(normalized_text)
        llm_result = await self._classify_with_adk(text_preview, image_url, metadata or {})

        return {
            "text_preview": text_preview,
            "content_type": self._metadata_value(metadata, "content_type", "post"),
            "has_image": bool(image_url),
            "declared_category": self._metadata_value(metadata, "declared_category", UNKNOWN_VALUE),
            "source_channel": self._metadata_value(metadata, "source_channel", UNKNOWN_VALUE),
            "language_hint": llm_result.get("language_hint", UNKNOWN_VALUE),
            "content_length": len(normalized_text),
            "llm_domain_hint": llm_result.get("domain_hint", UNKNOWN_VALUE),
            "llm_domain_confidence_hint": llm_result.get("confidence", 0.0),
            "topic_hints": llm_result.get("topic_hints", []),
        }

    async def _classify_with_adk(
        self,
        text_preview: str,
        image_url: str | None,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        session_id = str(uuid.uuid4())
        await self._runner.session_service.create_session(
            app_name="domain_intake_agent",
            user_id="system",
            session_id=session_id,
        )

        prompt = json.dumps(
            {
                "text_preview": text_preview,
                "has_image": bool(image_url),
                "metadata": metadata,
            },
            ensure_ascii=False,
        )
        message = types.Content(role="user", parts=[types.Part.from_text(text=prompt)])

        final_text = "{}"
        async for event in self._runner.run_async(
            user_id="system",
            session_id=session_id,
            new_message=message,
        ):
            if getattr(event, "content", None) and event.content.parts:
                event_text = "".join(part.text or "" for part in event.content.parts).strip()
                if event_text:
                    final_text = event_text

        return json.loads(final_text)

    @staticmethod
    def _shorten_text(text: str) -> str:
        if len(text) <= TEXT_PREVIEW_MAX_LENGTH:
            return text

        return f"{text[: TEXT_PREVIEW_MAX_LENGTH - 3].rstrip()}..."

    @staticmethod
    def _metadata_value(
        metadata: dict[str, Any] | None,
        key: str,
        default_value: str,
    ) -> str:
        value = (metadata or {}).get(key, default_value)
        return str(value).strip() or default_value

from typing import Any

from app.agents._shared import (
    DEFAULT_MODEL,
    JsonAdkAgent,
    clamp_score,
    metadata_text,
    require_text,
    string_list,
)


TEXT_PREVIEW_MAX_LENGTH = 240
UNKNOWN_VALUE = "unknown"

class DomainIntakeAgent:
    """Preparing classification payload before calling DomainClassificationDecision.dm"""

    def __init__(self, model: str = DEFAULT_MODEL) -> None:
        self._agent = JsonAdkAgent(
            app_name="domain_intake_agent",
            name="domain_intake_agent",
            model=model,
            description="Classifies post domain hints for Kogito DMN.",
            instruction=(
                "Return only JSON with keys: domain_hint, confidence, topic_hints, language_hint. "
                "domain_hint must be EDTECH, ECOMMERCE, REAL_ESTATE, HEALTHCARE, ENTERPRISE_HR, or UNKNOWN. "
                "Map product reviews, listings, promotions, QR payment, and marketplace posts to ECOMMERCE. "
                "Do not return moderation decisions."
            ),
        )

    async def prepare_classification_payload(
        self,
        text: str,
        image_url: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        normalized_text = require_text(text, "text")
        text_preview = _shorten_text(normalized_text)
        llm_result = await self._agent.run_json(
            {
                "text_preview": text_preview,
                "has_image": bool(image_url),
                "metadata": metadata or {},
            }
        )

        return {
            "text_preview": text_preview,
            "content_type": metadata_text(metadata, "content_type", "post"),
            "has_image": bool(image_url),
            "declared_category": metadata_text(metadata, "declared_category", UNKNOWN_VALUE),
            "source_channel": metadata_text(metadata, "source_channel", UNKNOWN_VALUE),
            "language_hint": str(llm_result.get("language_hint", UNKNOWN_VALUE)),
            "content_length": len(normalized_text),
            "llm_domain_hint": str(llm_result.get("domain_hint", "UNKNOWN")),
            "llm_domain_confidence_hint": clamp_score(llm_result.get("confidence")),
            "topic_hints": string_list(llm_result.get("topic_hints")),
        }


def _shorten_text(text: str) -> str:
    if len(text) <= TEXT_PREVIEW_MAX_LENGTH:
        return text
    return f"{text[: TEXT_PREVIEW_MAX_LENGTH - 3].rstrip()}..."

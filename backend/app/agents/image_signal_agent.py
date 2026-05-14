from typing import Any

from app.agents._shared import DEFAULT_MODEL, JsonAdkAgent, clamp_score, require_text, string_list
from app.prompts.loader import load_domain_prompt, load_prompt
from app.schemas.moderation import ImageSignals, ROUTABLE_DOMAIN_VALUES


class ImageSignalAgent:
    """Tạo image signals từ URL/metadata an toàn, không tải ảnh remote."""

    def __init__(self, model: str = DEFAULT_MODEL) -> None:
        self._agent = JsonAdkAgent(
            app_name="image_signal_agent",
            name="image_signal_agent",
            model=model,
            description="Produces domain-aware image moderation signals from safe metadata.",
            instruction=load_prompt("image_signal_base.md"),
        )

    async def analyze_image(
        self,
        content_id: str,
        image_url: str,
        detected_domain: str,
        image_prompt_profile: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        require_text(image_url, "image_url")
        _validate_domain(detected_domain)
        require_text(image_prompt_profile, "image_prompt_profile")

        llm_result = await self._agent.run_json(
            {
                "content_id": content_id,
                "image_url": image_url,
                "detected_domain": detected_domain,
                "image_prompt_profile": image_prompt_profile,
                "domain_prompt": load_domain_prompt(detected_domain),
                "metadata": metadata or {},
                "analysis_scope": "Use URL text and metadata only. Do not fetch remote content.",
            }
        )
        return normalize_image_signals(llm_result)


def normalize_image_signals(result: dict[str, Any]) -> dict[str, Any]:
    signals = ImageSignals(
        has_image=True,
        image_risk_score=clamp_score(result.get("image_risk_score")),
        image_policy_labels=string_list(result.get("image_policy_labels")),
        image_ocr_text=str(result.get("image_ocr_text", "")).strip(),
        image_matched_signals=string_list(result.get("image_matched_signals")),
        agent_version=str(result.get("agent_version", "llm-image-v1")).strip(),
    )
    return signals.model_dump(mode="json")


def _validate_domain(detected_domain: str) -> None:
    if detected_domain not in ROUTABLE_DOMAIN_VALUES:
        raise ValueError("detected_domain is not supported")

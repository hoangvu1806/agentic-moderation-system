from typing import Any

from app.agents._shared import DEFAULT_MODEL, JsonAdkAgent, clamp_score, require_text, string_list
from app.schemas.moderation import (
    ContentSignals,
    DOMAIN_SCORE_FIELD_BY_DOMAIN,
    DOMAIN_SCORE_KEYS,
    GENERIC_SCORE_KEYS,
    PRIMARY_RISK_VALUES,
    ROUTABLE_DOMAIN_VALUES,
)
from app.prompts.loader import load_domain_prompt, load_prompt


class ContentSignalAgent:
    """Creating text signals by domain profile. Dont decise allow/reject"""

    def __init__(self, model: str = DEFAULT_MODEL) -> None:
        self._agent = JsonAdkAgent(
            app_name="content_signal_agent",
            name="content_signal_agent",
            model=model,
            description="Produces domain-aware text moderation signals.",
            instruction=load_prompt("content_signal_base.md"),
        )

    async def analyze_text(
        self,
        content_id: str,
        text: str,
        detected_domain: str,
        content_prompt_profile: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        normalized_text = require_text(text, "text")
        _validate_domain(detected_domain)
        require_text(content_prompt_profile, "content_prompt_profile")

        llm_result = await self._agent.run_json(
            {
                "content_id": content_id,
                "text": normalized_text,
                "detected_domain": detected_domain,
                "content_prompt_profile": content_prompt_profile,
                "expected_score_keys": _expected_score_keys(detected_domain),
                "domain_prompt": load_domain_prompt(detected_domain),
                "metadata": metadata or {},
            }
        )
        return normalize_content_signals(llm_result, detected_domain)


def normalize_content_signals(result: dict[str, Any], detected_domain: str) -> dict[str, Any]:
    _validate_domain(detected_domain)
    domain_score_keys = list(DOMAIN_SCORE_KEYS[detected_domain])
    primary_risk = str(result.get("primary_risk", "NONE")).strip().upper()

    signals = {
        "language": str(result.get("language", "unknown")).strip() or "unknown",
        "topic_labels": string_list(result.get("topic_labels")),
        "primary_risk": primary_risk if primary_risk in PRIMARY_RISK_VALUES else "NONE",
        "matched_signals": string_list(result.get("matched_signals")),
        "domain_score_keys": domain_score_keys,
        "agent_version": str(result.get("agent_version", "llm-content-v1")).strip(),
        "generic_scores": _score_group(result, GENERIC_SCORE_KEYS),
        DOMAIN_SCORE_FIELD_BY_DOMAIN[detected_domain]: _score_group(result, domain_score_keys),
    }
    return ContentSignals(**signals).model_dump(mode="json")


def _expected_score_keys(detected_domain: str) -> list[str]:
    return list(GENERIC_SCORE_KEYS + DOMAIN_SCORE_KEYS[detected_domain])


def _score_group(source: dict[str, Any], keys: tuple[str, ...] | list[str]) -> dict[str, float]:
    return {key: clamp_score(source.get(key)) for key in keys}


def _validate_domain(detected_domain: str) -> None:
    if detected_domain not in ROUTABLE_DOMAIN_VALUES:
        raise ValueError("detected_domain is not supported")

import uuid
from typing import Any

from app.agents._shared import clamp_score, require_text
from app.schemas.moderation import (
    DOMAIN_SCORE_FIELD_BY_DOMAIN,
    DOMAIN_SCORE_KEYS,
    GENERIC_SCORE_KEYS,
    ROUTABLE_DOMAIN_VALUES,
    SUPPORTED_DOMAIN_VALUES,
)


PROCESS_ID = "pre_publication_moderation_process"


class ModerationEvidenceAgent:
    def build_evidence(
        self,
        content_id: str,
        classification: dict[str, Any],
        content_signals: dict[str, Any],
        image_signals: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        clean_content_id = require_text(content_id, "content_id")
        detected_domain = _detected_domain(classification)

        evidence_id = f"EVD-{uuid.uuid4().hex[:12].upper()}"
        process_variables = {
            "content_id": clean_content_id,
            "evidence_id": evidence_id,
            "is_repeat_offender": False,
            **_classification_variables(classification, detected_domain),
            **_content_variables(content_signals, detected_domain),
            **_image_variables(image_signals),
        }

        return {
            "evidence_id": evidence_id,
            "process_id": PROCESS_ID,
            "process_variables": process_variables,
        }


def _classification_variables(classification: dict[str, Any], detected_domain: str) -> dict[str, Any]:
    return {
        "detected_domain": detected_domain,
        "domain_confidence": clamp_score(classification.get("domain_confidence")),
        "analysis_profile": require_text(str(classification.get("analysis_profile", "")), "analysis_profile"),
        "content_prompt_profile": require_text(
            str(classification.get("content_prompt_profile", "")),
            "content_prompt_profile",
        ),
        "image_prompt_profile": str(classification.get("image_prompt_profile", "")).strip(),
        "requires_domain_review": bool(classification.get("requires_domain_review", False)),
    }


def _content_variables(content_signals: dict[str, Any], detected_domain: str) -> dict[str, Any]:
    if detected_domain not in ROUTABLE_DOMAIN_VALUES:
        return {
            "topic_labels": list(content_signals.get("topic_labels", [])),
            "matched_signals": list(content_signals.get("matched_signals", [])),
            "domain_score_keys": [],
            "language": str(content_signals.get("language", "unknown")),
            "primary_risk": str(content_signals.get("primary_risk", "NONE")),
            **{key: 0.0 for key in GENERIC_SCORE_KEYS},
            **_all_domain_scores(),
        }

    return {
        "topic_labels": list(content_signals.get("topic_labels", [])),
        "matched_signals": list(content_signals.get("matched_signals", [])),
        "domain_score_keys": list(DOMAIN_SCORE_KEYS[detected_domain]),
        "language": str(content_signals.get("language", "unknown")),
        "primary_risk": str(content_signals.get("primary_risk", "NONE")),
        **_generic_scores(content_signals),
        **_domain_scores(content_signals, detected_domain),
    }


def _generic_scores(content_signals: dict[str, Any]) -> dict[str, float]:
    generic_scores = content_signals.get("generic_scores", {})
    return {key: clamp_score(generic_scores.get(key, content_signals.get(key))) for key in GENERIC_SCORE_KEYS}


def _domain_scores(content_signals: dict[str, Any], detected_domain: str) -> dict[str, float]:
    score_field = DOMAIN_SCORE_FIELD_BY_DOMAIN[detected_domain]
    domain_scores = content_signals.get(score_field, {})
    return {
        key: clamp_score(domain_scores.get(key, content_signals.get(key)))
        for key in DOMAIN_SCORE_KEYS[detected_domain]
    }


def _all_domain_scores() -> dict[str, float]:
    return {
        score_key: 0.0
        for domain_score_keys in DOMAIN_SCORE_KEYS.values()
        for score_key in domain_score_keys
    }


def _image_variables(image_signals: dict[str, Any] | None) -> dict[str, Any]:
    if not image_signals:
        return {
            "has_image": False,
            "image_risk_score": 0.0,
            "image_policy_labels": [],
            "image_matched_signals": [],
            "image_ocr_text": "",
        }

    return {
        "has_image": bool(image_signals.get("has_image", True)),
        "image_risk_score": clamp_score(image_signals.get("image_risk_score")),
        "image_policy_labels": list(image_signals.get("image_policy_labels", [])),
        "image_matched_signals": list(image_signals.get("image_matched_signals", [])),
        "image_ocr_text": str(image_signals.get("image_ocr_text", "")),
    }


def _detected_domain(classification: dict[str, Any]) -> str:
    detected_domain = str(classification.get("detected_domain", "")).strip()
    if detected_domain not in SUPPORTED_DOMAIN_VALUES:
        raise ValueError("detected_domain is not supported")
    return detected_domain

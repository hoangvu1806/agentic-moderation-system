from typing import Any

from app.agents._shared import DEFAULT_MODEL, JsonAdkAgent, require_text, string_list
from app.prompts.loader import load_prompt
from app.schemas.moderation import ModerationRequest


DEFAULT_USER_MESSAGES = {
    "ALLOW": "Bài viết đã được chấp nhận.",
    "WARN_ALLOW": "Bài viết được chấp nhận nhưng cần lưu ý chỉnh sửa để giảm rủi ro.",
    "REJECT": "Bài viết chưa thể được đăng vì có dấu hiệu vi phạm chính sách nội dung.",
    "MANUAL_REVIEW": "Bài viết cần được người kiểm duyệt xem xét trước khi đăng.",
}

DEFAULT_RESUBMISSION_GUIDANCE = {
    "ALLOW": "Bạn có thể tiếp tục đăng bài.",
    "WARN_ALLOW": "Bạn nên chỉnh lại các phần dễ gây hiểu nhầm trước khi tiếp tục đăng các nội dung tương tự.",
    "REJECT": "Hãy loại bỏ nội dung rủi ro, viết lại phần gây vi phạm và gửi lại khi nội dung đã rõ ràng hơn.",
    "MANUAL_REVIEW": "Vui lòng chờ kiểm duyệt hoặc bổ sung thông tin xác thực nếu hệ thống yêu cầu.",
}


class ExplanationAgent:
    def __init__(self, model: str = DEFAULT_MODEL) -> None:
        self._agent = JsonAdkAgent(
            app_name="explanation_agent",
            name="explanation_agent",
            model=model,
            description="Produces user-facing and reviewer-facing moderation explanations.",
            instruction=load_prompt("explanation_base.txt"),
        )

    async def explain(
        self,
        content_id: str,
        request: ModerationRequest,
        classification: dict[str, Any],
        workflow: dict[str, Any],
        signals: dict[str, Any],
        evidence: dict[str, Any],
    ) -> dict[str, Any]:
        clean_content_id = require_text(content_id, "content_id")
        payload = _build_explanation_payload(
            content_id=clean_content_id,
            request=request,
            classification=classification,
            workflow=workflow,
            signals=signals,
            evidence=evidence,
        )

        try:
            llm_result = await self._agent.run_json(payload)
        except ValueError:
            return _fallback_explanation(payload)
        return _normalize_explanation(llm_result, payload)


def _build_explanation_payload(
    content_id: str,
    request: ModerationRequest,
    classification: dict[str, Any],
    workflow: dict[str, Any],
    signals: dict[str, Any],
    evidence: dict[str, Any],
) -> dict[str, Any]:
    return {
        "content_id": content_id,
        "text_preview": _text_preview(request.text),
        "image_url": request.image_url,
        "metadata": request.metadata,
        "classification": _public_classification(classification),
        "workflow": {key: value for key, value in workflow.items() if key != "raw"},
        "signals": signals,
        "evidence": {"evidence_id": evidence.get("evidence_id")},
        "decision": _decision(workflow),
        "status": _status(workflow),
    }


def _public_classification(classification: dict[str, Any]) -> dict[str, Any]:
    return {
        "detected_domain": classification.get("detected_domain", "UNKNOWN"),
        "domain_confidence": classification.get("domain_confidence", 0.0),
        "analysis_profile": classification.get("analysis_profile", ""),
        "requires_domain_review": classification.get("requires_domain_review", False),
    }


def _normalize_explanation(result: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    decision = str(payload["decision"])
    fallback = _fallback_explanation(payload)
    risk_summary = result.get("risk_summary", {})
    if not isinstance(risk_summary, dict):
        risk_summary = fallback["risk_summary"]

    return {
        "user_message": _required_text(result.get("user_message"), fallback["user_message"]),
        "verdict_summary": _required_text(result.get("verdict_summary"), fallback["verdict_summary"]),
        "article_commentary": _required_text(result.get("article_commentary"), fallback["article_commentary"]),
        "policy_reasons": _policy_reasons(result, decision, fallback),
        "recommended_edits": _recommended_edits(result, decision, fallback),
        "resubmission_guidance": _required_text(
            result.get("resubmission_guidance"),
            fallback["resubmission_guidance"],
        ),
        "admin_explanation": _required_text(result.get("admin_explanation"), fallback["admin_explanation"]),
        "risk_summary": _normalize_risk_summary(risk_summary, fallback["risk_summary"]),
        "redacted": True,
    }


def _policy_reasons(
    result: dict[str, Any],
    decision: str,
    fallback: dict[str, Any],
) -> list[str]:
    policy_reasons = string_list(result.get("policy_reasons"))
    if policy_reasons or decision == "ALLOW":
        return policy_reasons
    return list(fallback["policy_reasons"])


def _recommended_edits(
    result: dict[str, Any],
    decision: str,
    fallback: dict[str, Any],
) -> list[str]:
    recommended_edits = string_list(result.get("recommended_edits"))
    if recommended_edits or decision == "ALLOW":
        return recommended_edits
    return list(fallback["recommended_edits"])


def _normalize_risk_summary(
    risk_summary: dict[str, Any],
    fallback: dict[str, Any],
) -> dict[str, Any]:
    return {
        "primary_risk": _required_text(risk_summary.get("primary_risk"), fallback["primary_risk"]),
        "strongest_signals": string_list(risk_summary.get("strongest_signals")) or fallback["strongest_signals"],
        "image_notes": string_list(risk_summary.get("image_notes")) or fallback["image_notes"],
    }


def _fallback_explanation(payload: dict[str, Any]) -> dict[str, Any]:
    decision = str(payload["decision"])
    status = str(payload["status"])
    domain = str(payload["classification"].get("detected_domain", "UNKNOWN"))
    primary_risk = str(payload["signals"].get("primary_risk", "NONE")).strip().upper()
    strongest_signals = _strongest_signals(payload["signals"])
    image_notes = _image_notes(payload["signals"])

    return {
        "user_message": DEFAULT_USER_MESSAGES.get(decision, DEFAULT_USER_MESSAGES["MANUAL_REVIEW"]),
        "verdict_summary": _fallback_verdict_summary(decision, domain, primary_risk),
        "article_commentary": _fallback_article_commentary(primary_risk, strongest_signals, image_notes),
        "policy_reasons": _fallback_policy_reasons(decision, primary_risk, strongest_signals, image_notes),
        "recommended_edits": _fallback_recommended_edits(decision, primary_risk, image_notes),
        "resubmission_guidance": DEFAULT_RESUBMISSION_GUIDANCE.get(
            decision,
            DEFAULT_RESUBMISSION_GUIDANCE["MANUAL_REVIEW"],
        ),
        "admin_explanation": (
            f"Content {payload['content_id']} ended with status {status}. "
            f"DMN decision: {decision}. Domain: {domain}. Primary risk: {primary_risk}. "
            f"Strongest signals: {', '.join(strongest_signals) or 'none'}."
        ),
        "risk_summary": {
            "primary_risk": primary_risk,
            "strongest_signals": strongest_signals,
            "image_notes": image_notes,
        },
        "redacted": True,
    }


def _fallback_verdict_summary(decision: str, domain: str, primary_risk: str) -> str:
    if decision == "ALLOW":
        return f"Nội dung thuộc nhóm {domain} và không có tín hiệu rủi ro nổi bật."
    if decision == "WARN_ALLOW":
        return f"Nội dung thuộc nhóm {domain} được chấp nhận nhưng có tín hiệu cần lưu ý: {primary_risk}."
    if decision == "REJECT":
        return f"Nội dung thuộc nhóm {domain} bị từ chối do tín hiệu rủi ro chính: {primary_risk}."
    return f"Nội dung thuộc nhóm {domain} cần kiểm duyệt thủ công do tín hiệu: {primary_risk}."


def _fallback_article_commentary(
    primary_risk: str,
    strongest_signals: list[str],
    image_notes: list[str],
) -> str:
    signal_text = ", ".join(strongest_signals) if strongest_signals else "không có tín hiệu nội dung nổi bật"
    image_text = f" Tín hiệu ảnh: {', '.join(image_notes)}." if image_notes else ""
    return f"Bài viết được đánh dấu với rủi ro chính {primary_risk}; các tín hiệu liên quan gồm {signal_text}.{image_text}"


def _fallback_policy_reasons(
    decision: str,
    primary_risk: str,
    strongest_signals: list[str],
    image_notes: list[str],
) -> list[str]:
    if decision == "ALLOW":
        return []

    reasons = [f"Tín hiệu rủi ro chính: {primary_risk}."]
    if strongest_signals:
        reasons.append(f"Các tín hiệu nội dung liên quan: {', '.join(strongest_signals)}.")
    if image_notes:
        reasons.append(f"Các tín hiệu ảnh liên quan: {', '.join(image_notes)}.")
    return reasons


def _fallback_recommended_edits(decision: str, primary_risk: str, image_notes: list[str]) -> list[str]:
    if decision == "ALLOW":
        return []

    edits = [
        f"Viết lại hoặc loại bỏ các phần liên quan đến rủi ro {primary_risk}.",
        "Bổ sung thông tin xác thực, điều kiện áp dụng, nguồn tin hoặc ngữ cảnh cần thiết.",
    ]
    if image_notes:
        edits.append("Thay ảnh hoặc làm rõ nội dung ảnh nếu ảnh đang tạo tín hiệu rủi ro.")
    return edits


def _strongest_signals(signals: dict[str, Any]) -> list[str]:
    matched_signals = string_list(signals.get("matched_signals"))
    policy_labels = string_list(signals.get("image_policy_labels"))
    score_signals = [
        key
        for key, value in signals.items()
        if key.endswith("_score") and _is_high_score(value)
    ]
    return list(dict.fromkeys(matched_signals + policy_labels + score_signals))


def _image_notes(signals: dict[str, Any]) -> list[str]:
    if not signals.get("has_image"):
        return []
    notes = string_list(signals.get("image_policy_labels"))
    if _is_high_score(signals.get("image_risk_score")):
        notes.append("image_risk_score cao")
    return list(dict.fromkeys(notes))


def _is_high_score(value: Any) -> bool:
    try:
        return float(value) >= 0.6
    except (TypeError, ValueError):
        return False


def _decision(workflow: dict[str, Any]) -> str:
    return str(workflow.get("dmn_decision", "MANUAL_REVIEW")).strip().upper()


def _status(workflow: dict[str, Any]) -> str:
    return str(workflow.get("status", "PENDING_HUMAN_REVIEW")).strip()


def _required_text(value: Any, fallback: str) -> str:
    cleaned = str(value or "").strip()
    return cleaned or fallback


def _text_preview(text: str, max_length: int = 1200) -> str:
    normalized_text = require_text(text, "text")
    if len(normalized_text) <= max_length:
        return normalized_text
    return f"{normalized_text[: max_length - 3].rstrip()}..."

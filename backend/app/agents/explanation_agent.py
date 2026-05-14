from typing import Any


USER_MESSAGES = {
    "ALLOW": "Your content has been published.",
    "WARN_ALLOW": "Your content has been published with a policy warning.",
    "REJECT": "Your content could not be published because it appears to violate our content policy.",
    "MANUAL_REVIEW": "Your content is waiting for moderator review.",
}


class ExplanationAgent:
    def explain(
        self,
        content_id: str,
        workflow: dict[str, Any],
        signals: dict[str, Any],
    ) -> dict[str, Any]:
        if not content_id.strip():
            raise ValueError("content_id is required")

        dmn_decision = str(workflow.get("dmn_decision", "MANUAL_REVIEW")).strip().upper()
        status = str(workflow.get("status", "PENDING_HUMAN_REVIEW")).strip()
        primary_risk = str(signals.get("primary_risk", "NONE")).strip().upper()

        return {
            "user_message": USER_MESSAGES.get(dmn_decision, USER_MESSAGES["MANUAL_REVIEW"]),
            "admin_explanation": (
                f"Content {content_id} ended with status {status}. "
                f"DMN decision: {dmn_decision}. Primary signal: {primary_risk}."
            ),
            "redacted": True,
        }

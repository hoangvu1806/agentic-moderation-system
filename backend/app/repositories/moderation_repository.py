from app.schemas.moderation import (
    ContentStatus,
    ModerationDecision,
    ModerationRecord,
    ModerationResponse,
    ReviewerDecision,
)


class ModerationRepository:
    """In-memory moderation state for backend"""
    def __init__(self) -> None:
        self._records: dict[str, ModerationRecord] = {}

    def save(self, record: ModerationRecord) -> None:
        self._records[record.content_id] = record

    def get(self, content_id: str) -> ModerationRecord | None:
        return self._records.get(content_id)

    def pending_review(self) -> list[ModerationRecord]:
        return [
            record
            for record in self._records.values()
            if record.response.status == ContentStatus.PENDING_HUMAN_REVIEW
        ]

    def apply_review_decision(
        self,
        content_id: str,
        reviewer_id: str,
        decision: ReviewerDecision,
        note: str = "",
    ) -> ModerationRecord | None:
        record = self.get(content_id)
        if record is None:
            return None

        response = _reviewed_response(record.response, decision)
        updated_record = record.model_copy(
            update={
                "response": response,
                "reviewer_id": reviewer_id,
                "review_note": note,
            }
        )
        self.save(updated_record)
        return updated_record


def _reviewed_response(response: ModerationResponse, decision: ReviewerDecision) -> ModerationResponse:
    if decision == ReviewerDecision.APPROVE_PUBLISH:
        return response.model_copy(
            update={
                "status": ContentStatus.PUBLISHED,
                "decision": ModerationDecision.ALLOW,
                "message": "Your content has been published after moderator review.",
            }
        )

    return response.model_copy(
        update={
            "status": ContentStatus.REJECTED,
            "decision": ModerationDecision.REJECT,
            "message": "Your content was rejected after moderator review.",
        }
    )

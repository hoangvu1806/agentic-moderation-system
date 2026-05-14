from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.agents import (
    ContentSignalAgent,
    DomainIntakeAgent,
    ExplanationAgent,
    ImageSignalAgent,
    ModerationEvidenceAgent,
)
from app.kogito import (
    KogitoClientError,
    create_domain_classifier_client,
    create_kogito_http_client,
    create_workflow_client,
)
from app.repositories.moderation_repository import ModerationRepository
from app.schemas.moderation import (
    ModerationRecord,
    ModerationRequest,
    ModerationResponse,
    ReviewerDecisionRequest,
)
from app.services.moderation_service import ModerationService


router = APIRouter()


def get_repository(request: Request) -> ModerationRepository:
    repository = getattr(request.app.state, "moderation_repository", None)
    if repository is None:
        repository = ModerationRepository()
        request.app.state.moderation_repository = repository
    return repository


async def get_moderation_service(
    repository: ModerationRepository = Depends(get_repository),
) -> AsyncIterator[ModerationService]:
    http_client = create_kogito_http_client()
    try:
        yield ModerationService(
            domain_intake_agent=DomainIntakeAgent(),
            domain_classifier_client=create_domain_classifier_client(http_client),
            content_signal_agent=ContentSignalAgent(),
            image_signal_agent=ImageSignalAgent(),
            evidence_agent=ModerationEvidenceAgent(),
            workflow_client=create_workflow_client(http_client),
            explanation_agent=ExplanationAgent(),
            repository=repository,
        )
    finally:
        await http_client.close()


@router.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/contents/moderate", response_model=ModerationResponse)
async def moderate_content(
    moderation_request: ModerationRequest,
    moderation_service: ModerationService = Depends(get_moderation_service),
) -> ModerationResponse:
    try:
        return await moderation_service.moderate(moderation_request)
    except KogitoClientError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Kogito moderation service is unavailable",
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/contents/{content_id}/moderation", response_model=ModerationResponse)
async def get_moderation_result(
    content_id: str,
    repository: ModerationRepository = Depends(get_repository),
) -> ModerationResponse:
    record = repository.get(content_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Content moderation result not found")
    return record.response


@router.get("/moderation/review-queue", response_model=list[ModerationRecord])
async def list_review_queue(
    repository: ModerationRepository = Depends(get_repository),
) -> list[ModerationRecord]:
    return repository.pending_review()


@router.post("/moderation/review-queue/{content_id}/decision", response_model=ModerationResponse)
async def submit_reviewer_decision(
    content_id: str,
    reviewer_decision: ReviewerDecisionRequest,
    repository: ModerationRepository = Depends(get_repository),
) -> ModerationResponse:
    record = repository.apply_review_decision(
        content_id=content_id,
        reviewer_id=reviewer_decision.reviewer_id,
        decision=reviewer_decision.decision,
        note=reviewer_decision.note,
    )
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Content moderation result not found")
    return record.response

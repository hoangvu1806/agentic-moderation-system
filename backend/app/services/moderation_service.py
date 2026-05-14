import asyncio
import uuid
from typing import Any

from app.repositories.moderation_repository import ModerationRepository
from app.schemas.moderation import (
    ContentStatus,
    ModerationDecision,
    ModerationRecord,
    ModerationRequest,
    ModerationResponse,
    ROUTABLE_DOMAIN_VALUES,
)


class ModerationService:
    def __init__(
        self,
        domain_intake_agent: Any,
        domain_classifier_client: Any,
        content_signal_agent: Any,
        image_signal_agent: Any,
        evidence_agent: Any,
        workflow_client: Any,
        explanation_agent: Any,
        repository: ModerationRepository,
    ) -> None:
        self._domain_intake_agent = domain_intake_agent
        self._domain_classifier_client = domain_classifier_client
        self._content_signal_agent = content_signal_agent
        self._image_signal_agent = image_signal_agent
        self._evidence_agent = evidence_agent
        self._workflow_client = workflow_client
        self._explanation_agent = explanation_agent
        self._repository = repository

    async def moderate(self, request: ModerationRequest) -> ModerationResponse:
        content_id = f"CNT-{uuid.uuid4().hex[:12].upper()}"
        classification_input = await self._domain_intake_agent.prepare_classification_payload(
            text=request.text,
            image_url=request.image_url,
            metadata=request.metadata,
        )
        classification = await self._domain_classifier_client.classify_domain(classification_input)

        content_signals, image_signals = await self._run_signal_agents(content_id, request, classification)
        evidence = self._evidence_agent.build_evidence(
            content_id=content_id,
            classification=classification,
            content_signals=content_signals,
            image_signals=image_signals,
        )
        workflow = await self._workflow_client.start_pre_publication_moderation(
            evidence["process_variables"],
            business_key=content_id,
        )

        signals = _response_signals(content_signals, image_signals)
        explanations = self._explanation_agent.explain(content_id, workflow, signals)
        response = _moderation_response(
            content_id=content_id,
            classification=classification,
            workflow=workflow,
            signals=signals,
            evidence=evidence,
            explanations=explanations,
        )
        self._repository.save(ModerationRecord(content_id=content_id, request=request, response=response))
        return response

    async def _run_signal_agents(
        self,
        content_id: str,
        request: ModerationRequest,
        classification: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any] | None]:
        detected_domain = str(classification.get("detected_domain", "UNKNOWN"))
        if detected_domain not in ROUTABLE_DOMAIN_VALUES:
            return _empty_content_signals(), None

        content_task = self._content_signal_agent.analyze_text(
            content_id=content_id,
            text=request.text,
            detected_domain=detected_domain,
            content_prompt_profile=str(classification["content_prompt_profile"]),
            metadata=request.metadata,
        )
        if not request.image_url:
            return await content_task, None

        image_task = self._image_signal_agent.analyze_image(
            content_id=content_id,
            image_url=request.image_url,
            detected_domain=detected_domain,
            image_prompt_profile=str(classification.get("image_prompt_profile", "")),
            metadata=request.metadata,
        )
        content_signals, image_signals = await asyncio.gather(content_task, image_task)
        return content_signals, image_signals


def _empty_content_signals() -> dict[str, Any]:
    return {
        "language": "unknown",
        "topic_labels": [],
        "primary_risk": "NONE",
        "matched_signals": [],
        "generic_scores": {},
    }


def _moderation_response(
    content_id: str,
    classification: dict[str, Any],
    workflow: dict[str, Any],
    signals: dict[str, Any],
    evidence: dict[str, Any],
    explanations: dict[str, Any],
) -> ModerationResponse:
    return ModerationResponse(
        content_id=content_id,
        status=ContentStatus(str(workflow.get("status", ContentStatus.PENDING_HUMAN_REVIEW.value))),
        decision=_api_decision(str(workflow.get("dmn_decision", "MANUAL_REVIEW"))),
        message=str(explanations["user_message"]),
        detected_domain=classification["detected_domain"],
        analysis_profile=str(classification["analysis_profile"]),
        workflow={key: value for key, value in workflow.items() if key != "raw"},
        signals=signals,
        evidence={"evidence_id": evidence["evidence_id"]},
        explanations=explanations,
    )


def _api_decision(dmn_decision: str) -> ModerationDecision:
    if dmn_decision.upper() == "TEMP_BAN":
        return ModerationDecision.REJECT
    try:
        return ModerationDecision(dmn_decision.upper())
    except ValueError:
        return ModerationDecision.MANUAL_REVIEW


def _response_signals(
    content_signals: dict[str, Any],
    image_signals: dict[str, Any] | None,
) -> dict[str, Any]:
    generic_scores = content_signals.get("generic_scores", {})
    signals = {
        "language": content_signals.get("language", "unknown"),
        "topic_labels": content_signals.get("topic_labels", []),
        "primary_risk": content_signals.get("primary_risk", "NONE"),
        **generic_scores,
    }
    for key, value in content_signals.items():
        if key.endswith("_scores") and isinstance(value, dict):
            signals.update(value)
    if image_signals:
        signals.update(
            {
                "has_image": bool(image_signals.get("has_image", True)),
                "image_risk_score": image_signals.get("image_risk_score", 0.0),
                "image_policy_labels": image_signals.get("image_policy_labels", []),
            }
        )
    else:
        signals.update({"has_image": False, "image_risk_score": 0.0, "image_policy_labels": []})
    return signals

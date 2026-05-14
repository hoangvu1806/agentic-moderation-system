from typing import Any

from app.kogito.client import KogitoHttpClient, KogitoResponseError


PROCESS_ID = "pre_publication_moderation_process"
FINAL_STATUS_BY_DMN_DECISION = {
    "ALLOW": "PUBLISHED",
    "WARN_ALLOW": "PUBLISHED_WITH_WARNING",
    "REJECT": "REJECTED",
    "TEMP_BAN": "REJECTED",
    "MANUAL_REVIEW": "PENDING_HUMAN_REVIEW",
}


class KogitoWorkflowClient:
    """Starts and reads the Kogito pre-publication moderation process"""
    def __init__(self, http_client: KogitoHttpClient) -> None:
        self._http_client = http_client

    async def start_pre_publication_moderation(
        self,
        process_variables: dict[str, Any],
        business_key: str | None = None,
    ) -> dict[str, Any]:
        params = {"businessKey": business_key} if business_key else None
        response = await self._http_client.post_json(f"/{PROCESS_ID}", process_variables, params=params)
        return self._normalize_process_response(response)

    async def get_process_instance(self, process_instance_id: str) -> dict[str, Any]:
        if not process_instance_id.strip():
            raise ValueError("process_instance_id is required")
        response = await self._http_client.get_json(f"/{PROCESS_ID}/{process_instance_id}")
        return self._normalize_process_response(response)

    @staticmethod
    def _normalize_process_response(response: dict[str, Any]) -> dict[str, Any]:
        process_instance_id = str(response.get("id", "")).strip()
        if not process_instance_id:
            raise KogitoResponseError("Kogito process response is missing id")

        dmn_decision = str(response.get("dmn_decision", "MANUAL_REVIEW")).strip().upper()
        status = str(
            response.get("moderation_status")
            or FINAL_STATUS_BY_DMN_DECISION.get(dmn_decision, "PENDING_HUMAN_REVIEW")
        )

        return {
            "process_id": PROCESS_ID,
            "process_instance_id": process_instance_id,
            "content_id": response.get("content_id"),
            "detected_domain": response.get("detected_domain"),
            "domain_dmn": response.get("domain_dmn"),
            "dmn_decision": dmn_decision,
            "status": status,
            "raw": response,
        }

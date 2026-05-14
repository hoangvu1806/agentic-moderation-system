from typing import Any

from app.kogito.client import KogitoHttpClient, KogitoResponseError
from app.schemas.moderation import DomainClassificationResult


DOMAIN_CLASSIFICATION_DECISION = "DomainClassificationDecision"

class KogitoDomainClassifierClient:
    def __init__(self, http_client: KogitoHttpClient) -> None:
        self._http_client = http_client

    async def classify_domain(self, classification_input: dict[str, Any]) -> dict[str, Any]:
        response = await self._http_client.post_json(
            f"/{DOMAIN_CLASSIFICATION_DECISION}",
            classification_input,
        )
        decision_output = response.get(DOMAIN_CLASSIFICATION_DECISION)
        if not isinstance(decision_output, dict):
            raise KogitoResponseError("DomainClassificationDecision output is missing or invalid")

        return DomainClassificationResult(**decision_output).model_dump(mode="json")

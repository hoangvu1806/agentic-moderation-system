from app.kogito.client import KogitoHttpClient
from app.kogito.domain_classifier_client import KogitoDomainClassifierClient
from app.kogito.workflow_client import KogitoWorkflowClient
from app.settings import Settings, settings


def create_kogito_http_client(app_settings: Settings = settings) -> KogitoHttpClient:
    return KogitoHttpClient(
        base_url=app_settings.kogito_base_url,
        timeout_seconds=app_settings.kogito_timeout_seconds,
    )


def create_domain_classifier_client(
    http_client: KogitoHttpClient,
) -> KogitoDomainClassifierClient:
    return KogitoDomainClassifierClient(http_client)


def create_workflow_client(http_client: KogitoHttpClient) -> KogitoWorkflowClient:
    return KogitoWorkflowClient(http_client)

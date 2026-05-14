# Kogito Moderation Service

This service hosts the BPMN and DMN assets for the Multi-Agent Pre-Publication Content Moderation Workflow.

## Role

- `src/main/resources/dmn/ContentModerationDecision.dmn` receives moderation signals from the agent/backend layer and returns a deterministic moderation decision.
- `src/main/resources/bpmn/pre_publication_moderation_process.bpmn2` is the placeholder process for the pre-publication moderation lifecycle.
- Google ADK is not embedded in this service. The Python backend/agent layer should call this service over HTTP.

## Prerequisites

- JDK 17
- Maven 3.9+

## Run

```powershell
mvn clean compile quarkus:dev
```

The service is configured to run at:

```text
http://localhost:8080
```

Useful Quarkus endpoints:

```text
http://localhost:8080/q/swagger-ui
http://localhost:8080/q/openapi
http://localhost:8080/q/health
```

## Next Steps

1. Expand `ContentModerationDecision.dmn` from the starter table into the full moderation policy.
2. Replace the BPMN placeholder with the real flow:
   `PENDING_MODERATION -> PUBLISHED / REJECTED / PENDING_HUMAN_REVIEW`.
3. Add FastAPI/Google ADK integration that sends moderation scores to the Kogito decision endpoint.

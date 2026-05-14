from typing import Any

import httpx

DEFAULT_TIMEOUT_SECONDS = 10.0

class KogitoClientError(RuntimeError):
    """Base error for Kogito integration failures."""


class KogitoServiceUnavailableError(KogitoClientError):
    """Raised when the Kogito service cannot be reached."""


class KogitoResponseError(KogitoClientError):
    """Raised when Kogito returns an invalid status or payload."""


class KogitoHttpClient:
    """Small HTTP boundary around the Kogito service."""

    def __init__(
        self,
        base_url: str,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not base_url.strip():
            raise ValueError("Kogito base_url is required")

        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=httpx.Timeout(timeout_seconds),
            headers={"Accept": "application/json"},
        )

    async def post_json(
        self,
        path: str,
        payload: dict[str, Any],
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        response = await self._request("POST", path, json=payload, params=params)
        return self._json(response, path)

    async def get_json(self, path: str) -> dict[str, Any]:
        response = await self._request("GET", path)
        return self._json(response, path)

    async def health(self) -> dict[str, Any]:
        return await self.get_json("/q/health")

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> "KogitoHttpClient":
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        try:
            response = await self._client.request(method, path, **kwargs)
        except httpx.RequestError as exc:
            raise KogitoServiceUnavailableError(f"Kogito request failed: {method} {path}") from exc

        if response.status_code >= 400:
            raise KogitoResponseError(
                f"Kogito returned HTTP {response.status_code} for {method} {path}: {response.text[:500]}"
            )
        return response

    @staticmethod
    def _json(response: httpx.Response, path: str) -> dict[str, Any]:
        try:
            payload = response.json()
        except ValueError as exc:
            raise KogitoResponseError(f"Kogito returned non-JSON response for {path}") from exc

        if not isinstance(payload, dict):
            raise KogitoResponseError(f"Kogito returned non-object JSON for {path}")
        return payload

import httpx
from loguru import logger

from openutm_verification.models import FlightBlenderError


class BaseBlenderAPIClient:
    """A base client for interacting with the Flight Blender API."""

    def __init__(self, base_url: str, credentials: dict, request_timeout: int = 10):
        self.base_url = base_url
        self.client = httpx.Client(timeout=request_timeout)
        if credentials and "access_token" in credentials:
            self.client.headers.update(
                {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {credentials['access_token']}",
                }
            )
        else:
            self.client.headers.update(
                {
                    "Content-Type": "application/json",
                }
            )

    def _request(self, method: str, endpoint: str, json: dict | None = None, silent_status: list[int] | None = None) -> httpx.Response:
        url = f"{self.base_url}{endpoint}"
        try:
            response = self.client.request(method, url, json=json)
            if not (silent_status and response.status_code in silent_status):
                response.raise_for_status()
            return response
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error occurred: {e.response.status_code} - {e.response.text}")
            raise FlightBlenderError(f"Request failed: {e.response.status_code}") from e
        except httpx.RequestError as e:
            logger.error(f"Request error occurred: {e}")
            raise FlightBlenderError("Request failed") from e

    def get(self, endpoint: str, silent_status: list[int] | None = None) -> httpx.Response:
        return self._request("GET", endpoint, silent_status=silent_status)

    def post(self, endpoint: str, json: dict, silent_status: list[int] | None = None) -> httpx.Response:
        return self._request("POST", endpoint, json=json, silent_status=silent_status)

    def put(self, endpoint: str, json: dict, silent_status: list[int] | None = None) -> httpx.Response:
        return self._request("PUT", endpoint, json=json, silent_status=silent_status)

    def delete(self, endpoint: str, silent_status: list[int] | None = None) -> httpx.Response:
        return self._request("DELETE", endpoint, silent_status=silent_status)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.client.close()

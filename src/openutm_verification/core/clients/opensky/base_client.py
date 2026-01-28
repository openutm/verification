from __future__ import annotations

from typing import TYPE_CHECKING

import httpx
from loguru import logger
from pydantic import BaseModel

from openutm_verification.auth.oauth2 import OAuth2Client
from openutm_verification.core.execution.config_models import get_settings

if TYPE_CHECKING:
    from openutm_verification.core.execution.config_models import OpenSkyConfig

config = get_settings()


class OpenSkyError(Exception):
    """Custom exception for OpenSky API errors."""


class OpenSkySettings(BaseModel):
    """Settings for OpenSky Network API."""

    client_id: str = ""
    client_secret: str = ""
    auth_url: str = "https://auth.opensky-network.org/auth/realms/opensky-network/protocol/openid-connect/token"
    base_url: str = "https://opensky-network.org/api"
    request_timeout: int = 10
    viewport: tuple[float, float, float, float] = (45.8389, 47.8229, 5.9962, 10.5226)

    @classmethod
    def from_config(cls, opensky_config: "OpenSkyConfig") -> "OpenSkySettings":
        """Create settings from OpenSkyConfig."""
        return cls(
            client_id=opensky_config.auth.client_id,
            client_secret=opensky_config.auth.client_secret,
        )


class BaseOpenSkyAPIClient:
    """Base client for OpenSky Network API interactions with OAuth2 authentication."""

    def __init__(self, settings: OpenSkySettings):
        self.settings = settings
        self.oauth_client = OAuth2Client(
            token_url=settings.auth_url,
            client_id=settings.client_id,
            client_secret=settings.client_secret,
            timeout=settings.request_timeout,
        )
        # Create our own HTTP client for API requests
        self.client = httpx.AsyncClient(timeout=settings.request_timeout)

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: dict | None = None,
        silent_status: list[int] | None = None,
    ) -> httpx.Response:
        """Make authenticated request to OpenSky API."""
        url = f"{self.settings.base_url}{endpoint}"
        headers = {}
        if config.opensky.auth.type == "oauth2":
            headers["Authorization"] = f"Bearer {await self.oauth_client.get_access_token()}"

        logger.debug(f"Making {method} request to {url}")
        response = await self.client.request(method, url, params=params, headers=headers)

        if response.status_code == 401 and config.opensky.auth.type == "oauth2":
            logger.warning("Token expired, retrying with new token...")
            headers["Authorization"] = f"Bearer {await self.oauth_client.get_access_token()}"
            response = await self.client.request(method, url, params=params, headers=headers)

        if not (silent_status and response.status_code in silent_status):
            response.raise_for_status()
        return response

    async def get(
        self,
        endpoint: str,
        params: dict | None = None,
        silent_status: list[int] | None = None,
    ) -> httpx.Response:
        """Make GET request to OpenSky API."""
        return await self._request("GET", endpoint, params=params, silent_status=silent_status)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()
        await self.oauth_client.__aexit__(exc_type, exc_val, exc_tb)

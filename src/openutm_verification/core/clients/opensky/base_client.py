from typing import Optional, Tuple

import httpx
from loguru import logger
from pydantic_settings import BaseSettings

from openutm_verification.auth.oauth2 import OAuth2Client
from openutm_verification.core.execution.config_models import get_settings

config = get_settings()


class OpenSkyError(Exception):
    """Custom exception for OpenSky API errors."""


class OpenSkySettings(BaseSettings):
    """Pydantic settings for OpenSky Network API with automatic .env loading."""

    # OAuth2 credentials (required)
    opensky_client_id: str
    opensky_client_secret: str

    # OAuth2 endpoints
    auth_url: str = "https://auth.opensky-network.org/auth/realms/opensky-network/protocol/openid-connect/token"

    # Optional configuration with defaults
    base_url: str = "https://opensky-network.org/api"
    request_timeout: int = 10
    viewport: Tuple[float, float, float, float] = (45.8389, 47.8229, 5.9962, 10.5226)

    # Simulation settings
    simulation_config_path: str
    simulation_duration_seconds: int = 30


def create_opensky_settings() -> OpenSkySettings:
    """Factory function to create OpenSkySettings from config after initialization."""
    return OpenSkySettings(
        opensky_client_id=config.opensky.auth.client_id or "",
        opensky_client_secret=config.opensky.auth.client_secret or "",
        simulation_config_path=config.data_files.telemetry or "",
        simulation_duration_seconds=30,
    )


class BaseOpenSkyAPIClient:
    """Base client for OpenSky Network API interactions with OAuth2 authentication."""

    def __init__(self, settings: OpenSkySettings):
        self.settings = settings
        self.oauth_client = OAuth2Client(
            token_url=settings.auth_url,
            client_id=settings.opensky_client_id,
            client_secret=settings.opensky_client_secret,
            timeout=settings.request_timeout,
        )
        # Create our own HTTP client for API requests
        self.client = httpx.Client(timeout=settings.request_timeout)

    def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[dict] = None,
        silent_status: Optional[list[int]] = None,
    ) -> httpx.Response:
        """Make authenticated request to OpenSky API."""
        url = f"{self.settings.base_url}{endpoint}"
        headers = {}
        if config.opensky.auth.type == "oauth2":
            headers["Authorization"] = f"Bearer {self.oauth_client.get_access_token()}"

        logger.debug(f"Making {method} request to {url}")
        response = self.client.request(method, url, params=params, headers=headers)

        if response.status_code == 401 and config.opensky.auth.type == "oauth2":
            logger.warning("Token expired, retrying with new token...")
            headers["Authorization"] = f"Bearer {self.oauth_client.get_access_token()}"
            response = self.client.request(method, url, params=params, headers=headers)

        if not (silent_status and response.status_code in silent_status):
            response.raise_for_status()
        return response

    def get(
        self,
        endpoint: str,
        params: Optional[dict] = None,
        silent_status: Optional[list[int]] = None,
    ) -> httpx.Response:
        """Make GET request to OpenSky API."""
        return self._request("GET", endpoint, params=params, silent_status=silent_status)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.client.close()
        self.oauth_client.client.close()

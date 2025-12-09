import time
from typing import Optional

import httpx
from loguru import logger
from pydantic import BaseModel


class OAuth2Error(Exception):
    """Custom exception for OAuth2 related errors."""


class OAuth2Token(BaseModel):
    """OAuth2 token response model."""

    access_token: str
    token_type: str = "Bearer"
    expires_in: int
    expires_at: Optional[float] = None

    def is_expired(self, buffer_seconds: int = 60) -> bool:
        """Check if token is expired with buffer time."""
        if not self.expires_at:
            return True
        return time.time() >= (self.expires_at - buffer_seconds)


class OAuth2Client:
    """A generalized client for OAuth2 authentication using the client credentials flow."""

    def __init__(
        self,
        token_url: str,
        client_id: str,
        client_secret: str,
        timeout: int = 10,
    ):
        self.token_url = token_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.client = httpx.AsyncClient(timeout=timeout)
        self._token: Optional[OAuth2Token] = None

    async def get_access_token(self) -> str:
        """Get valid access token, acquiring or refreshing as needed."""
        if not self._token or self._token.is_expired():
            await self._acquire_token()
        if not self._token:
            raise OAuth2Error("Failed to acquire OAuth2 access token")
        return self._token.access_token

    async def _acquire_token(self) -> None:
        """Acquire OAuth2 access token using client credentials flow."""
        logger.debug("Acquiring new OAuth2 token...")
        data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
        try:
            response = await self.client.post(
                self.token_url,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()
            token_data = response.json()
            self._token = OAuth2Token(
                access_token=token_data["access_token"],
                expires_in=token_data["expires_in"],
            )
            self._token.expires_at = time.time() + self._token.expires_in
            logger.info(f"Acquired OAuth2 token, expires in {self._token.expires_in}s")
        except httpx.HTTPStatusError as e:
            logger.error(f"OAuth2 error: {e.response.status_code} - {e.response.text}")
            raise OAuth2Error(f"Token acquisition failed: {e.response.status_code}") from e
        except Exception as e:
            logger.error(f"OAuth2 acquisition error: {e}")
            raise OAuth2Error(f"Token acquisition failed: {e}") from e

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()

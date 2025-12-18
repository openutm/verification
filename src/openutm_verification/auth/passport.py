"""
Passport-based authentication credentials provider.
"""

from os import environ as env

import requests
from loguru import logger


class PassportCredentialsGetter:
    """Credentials getter that uses Passport OAuth for authentication."""

    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        audience: str | None = None,
        token_endpoint: str | None = None,
        passport_base_url: str | None = None,
    ):
        self.client_id = client_id or env.get("BLENDER_WRITE_CLIENT_ID")
        self.client_secret = client_secret or env.get("BLENDER_WRITE_CLIENT_SECRET")
        self.audience = audience
        self.token_endpoint = token_endpoint or env.get("PASSPORT_TOKEN_URL")
        self.base_url = passport_base_url or env.get("PASSPORT_URL")

    def get_cached_credentials(self, audience: str | None = None, scopes: list[str] | None = None):
        """Get cached credentials with token refresh logic."""

        if not audience:
            return {"error": "An audience parameter must be provided"}
        if not scopes:
            return {"error": "A list of scopes parameter must be provided"}

        scopes_str = " ".join(scopes)
        logger.info("Obtaining Passport token for audience '{audience}'", audience=audience)
        logger.debug(
            "Requesting Passport token for audience '{audience}' with scopes: {scopes_str}",
            audience=audience,
            scopes_str=scopes_str,
        )

        payload = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "audience": audience,
            "scope": scopes_str,
        }
        url = f"{self.base_url}{self.token_endpoint}"
        logger.debug("Requesting token from URL: {url}", url=url)
        token_data = requests.post(
            url,
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=10,
        )
        logger.debug("Received token response: {response}", response=token_data.text)
        logger.info("Successfully obtained Passport token")

        return token_data.json()

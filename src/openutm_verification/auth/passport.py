"""
Passport-based authentication credentials provider.
"""

import json
from datetime import datetime, timedelta
from os import environ as env
from typing import List, Optional

import requests

from openutm_verification.utils.redis_utils import get_redis


class PassportCredentialsGetter:
    """Credentials getter that uses Passport OAuth for authentication."""

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        audience: Optional[str] = None,
        token_url: Optional[str] = None,
    ):
        self.client_id = client_id or env.get("BLENDER_WRITE_CLIENT_ID")
        self.client_secret = client_secret or env.get("BLENDER_WRITE_CLIENT_SECRET")
        self.audience = audience
        self.token_url = token_url or env.get("PASSPORT_TOKEN_URL")
        self.base_url = env.get("PASSPORT_URL")

    def get_cached_credentials(self, audience: Optional[str] = None, scopes: Optional[List[str]] = None):
        """Get cached credentials with token refresh logic."""
        r = get_redis()

        if not audience:
            return {"error": "An audience parameter must be provided"}
        if not scopes:
            return {"error": "A list of scopes parameter must be provided"}

        scopes_str = " ".join(scopes)
        now = datetime.now()

        token_details = r.get("flight_blender_write_air_traffic_token")
        if token_details:
            token_details = json.loads(token_details)
            created_at = token_details["created_at"]
            set_date = datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%S.%f")
            if now < (set_date - timedelta(minutes=58)):
                credentials = self.get_write_credentials(audience=audience, scopes=scopes_str)
                r.set(
                    "flight_blender_write_air_traffic_token",
                    json.dumps({"credentials": credentials, "created_at": now.isoformat()}),
                )
            else:
                credentials = token_details["credentials"]
        else:
            credentials = self.get_write_credentials(audience=audience, scopes=scopes_str)
            if "error" not in credentials:
                r.set(
                    "flight_blender_write_air_traffic_token",
                    json.dumps({"credentials": credentials, "created_at": now.isoformat()}),
                )
                r.expire("flight_blender_write_air_traffic_token", timedelta(minutes=58))

        return credentials

    def get_write_credentials(self, audience: str, scopes: str):
        """Get fresh credentials from Passport."""
        payload = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "audience": audience,
            "scope": scopes,
        }
        url = f"{self.base_url}{self.token_url}"
        token_data = requests.post(url, data=payload, headers={"Content-Type": "application/x-www-form-urlencoded"}, timeout=10)
        return token_data.json()

"""
No-authentication credentials provider for development/testing.
"""

from typing import List

from openutm_verification.auth.dev_auth import NoAuth


class NoAuthCredentialsGetter:
    """Credentials getter that uses dummy authentication for development."""

    def __init__(self):
        pass

    def get_cached_credentials(self, audience: str, scopes: List[str]):
        """Get cached credentials using dummy authentication."""
        if not audience:
            return {"error": "An audience parameter must be provided"}
        if not scopes:
            return {"error": "A list of scopes parameter must be provided"}

        adapter = NoAuth()
        token = adapter.issue_token(audience, scopes)

        return {"access_token": token}

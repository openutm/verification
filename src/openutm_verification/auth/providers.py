"""
Authentication providers for Flight Blender API.
"""

from openutm_verification.auth.noauth import NoAuthCredentialsGetter
from openutm_verification.auth.passport import PassportCredentialsGetter
from openutm_verification.config_models import AuthConfig


def get_auth_provider(auth_config: AuthConfig):
    """Returns the appropriate authentication provider based on config."""
    if auth_config.type == "passport":
        return PassportCredentialsGetter(
            client_id=auth_config.client_id,
            client_secret=auth_config.client_secret,
            audience=auth_config.audience,
            token_url=auth_config.token_url,
        )
    return NoAuthCredentialsGetter()

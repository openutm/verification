"""
Authentication providers for the OpenUTM Verification Tool.
"""

from openutm_verification.auth.noauth import NoAuthCredentialsGetter
from openutm_verification.auth.passport import PassportCredentialsGetter
from openutm_verification.auth.providers import get_auth_provider

__all__ = [
    "NoAuthCredentialsGetter",
    "PassportCredentialsGetter",
    "get_auth_provider",
]

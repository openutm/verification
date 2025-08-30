"""
Authentication providers for the OpenUTM Verification Tool.
"""

from .noauth import NoAuthCredentialsGetter
from .passport import PassportCredentialsGetter
from .providers import get_auth_provider

__all__ = [
    "NoAuthCredentialsGetter",
    "PassportCredentialsGetter",
    "get_auth_provider",
]

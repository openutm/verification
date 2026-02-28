"""Air traffic providers module.

Providers generate or fetch air traffic observation data from various sources.
"""

from .factory import ProviderType, create_provider
from .latency import DataQualityType
from .opensky_provider import DEFAULT_SWITZERLAND_VIEWPORT
from .protocol import AirTrafficProvider

__all__ = [
    "AirTrafficProvider",
    "DEFAULT_SWITZERLAND_VIEWPORT",
    "DataQualityType",
    "ProviderType",
    "create_provider",
]

"""OpenSky Network live air traffic provider - wraps OpenSkyClient."""

from __future__ import annotations

from typing import TYPE_CHECKING

from openutm_verification.core.clients.opensky.base_client import OpenSkySettings
from openutm_verification.core.clients.opensky.opensky_client import OpenSkyClient
from openutm_verification.core.execution.config_models import get_settings

if TYPE_CHECKING:
    from openutm_verification.simulator.models.flight_data_types import (
        FlightObservationSchema,
    )


class OpenSkyProvider:
    """Provider that fetches live air traffic from OpenSky Network.

    Wraps the existing OpenSkyClient to provide a consistent interface.
    Note: OpenSky returns flat observation lists (not per-aircraft), so we
    wrap them in an outer list for consistency with other providers.
    """

    def __init__(
        self,
        viewport: tuple[float, float, float, float] | None = None,
        duration: int | None = None,
    ):
        """Initialize the OpenSky provider.

        Args:
            viewport: Geographic bounds (lat_min, lat_max, lon_min, lon_max).
            duration: Poll duration in seconds (how long to fetch data).
        """
        self._viewport = viewport or (45.8389, 47.8229, 5.9962, 10.5226)
        self._duration = duration or 30

    @property
    def name(self) -> str:
        """Provider identifier."""
        return "opensky"

    @classmethod
    def from_kwargs(
        cls,
        viewport: tuple[float, float, float, float] | None = None,
        duration: int | None = None,
        **_kwargs,  # Ignore unknown kwargs for flexibility
    ) -> "OpenSkyProvider":
        """Factory method to create provider from keyword arguments."""
        return cls(
            viewport=viewport,
            duration=duration,
        )

    async def get_observations(
        self,
        duration: int | None = None,
    ) -> list[list["FlightObservationSchema"]]:
        """Fetch observations from OpenSky Network.

        Args:
            duration: Override duration in seconds (currently single fetch).

        Returns:
            List containing a single observation list (all aircraft in one batch).
            Returns empty list if no data available.
        """
        # Get OpenSky config from application settings
        config = get_settings()

        settings = OpenSkySettings(
            client_id=config.opensky.auth.client_id,
            client_secret=config.opensky.auth.client_secret,
            viewport=self._viewport,
        )

        async with OpenSkyClient(settings) as client:
            observations = await client.fetch_data()
            if observations is None:
                return []
            # Wrap flat list in outer list for interface consistency
            # OpenSky returns all aircraft in a single list, not grouped by aircraft
            return [observations]

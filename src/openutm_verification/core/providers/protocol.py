"""Protocol definitions for air traffic providers.

Providers are responsible for generating or fetching air traffic observation data.
They abstract the data source (GeoJSON files, simulators, live APIs) behind a common interface.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from openutm_verification.simulator.models.flight_data_types import (
        FlightObservationSchema,
    )


@runtime_checkable
class AirTrafficProvider(Protocol):
    """Protocol for air traffic data sources.

    Providers generate or fetch batches of flight observations. Each provider
    wraps a specific data source (GeoJSON, BlueSky, Bayesian, OpenSky) and
    exposes a uniform interface for getting observations.
    """

    @property
    def name(self) -> str:
        """Provider identifier (e.g., 'geojson', 'bluesky', 'opensky')."""
        ...

    async def get_observations(
        self,
        duration: int | None = None,
    ) -> list[list["FlightObservationSchema"]]:
        """Get observation batches for the configured duration.

        Args:
            duration: Override for simulation/fetch duration in seconds.
                If None, uses provider's default configuration.

        Returns:
            List of observation lists - outer list is per aircraft/track,
            inner list is the time series of observations.
        """
        ...

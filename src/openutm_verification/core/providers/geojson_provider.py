"""GeoJSON air traffic provider - wraps AirTrafficClient."""

from __future__ import annotations

from typing import TYPE_CHECKING

from openutm_verification.core.clients.air_traffic.air_traffic_client import (
    AirTrafficClient,
)
from openutm_verification.core.clients.air_traffic.base_client import (
    AirTrafficSettings,
)

if TYPE_CHECKING:
    from openutm_verification.simulator.models.flight_data_types import (
        FlightObservationSchema,
    )


class GeoJSONProvider:
    """Provider that generates air traffic from GeoJSON trajectory files.

    Wraps the existing AirTrafficClient to provide a consistent interface.
    """

    def __init__(
        self,
        config_path: str | None = None,
        number_of_aircraft: int | None = None,
        duration: int | None = None,
        sensor_ids: list[str] | None = None,
        session_ids: list[str] | None = None,
    ):
        """Initialize the GeoJSON provider.

        Args:
            config_path: Path to the GeoJSON trajectory file.
            number_of_aircraft: Number of aircraft to simulate.
            duration: Simulation duration in seconds.
            sensor_ids: List of sensor UUID strings.
            session_ids: List of session UUID strings.
        """
        self._config_path = config_path or ""
        self._number_of_aircraft = number_of_aircraft or 2
        self._duration = duration or 30
        self._sensor_ids = sensor_ids or []
        self._session_ids = session_ids or []

    @property
    def name(self) -> str:
        """Provider identifier."""
        return "geojson"

    @classmethod
    def from_kwargs(
        cls,
        config_path: str | None = None,
        number_of_aircraft: int | None = None,
        duration: int | None = None,
        sensor_ids: list[str] | None = None,
        session_ids: list[str] | None = None,
        **_kwargs,  # Ignore unknown kwargs for flexibility
    ) -> "GeoJSONProvider":
        """Factory method to create provider from keyword arguments."""
        return cls(
            config_path=config_path,
            number_of_aircraft=number_of_aircraft,
            duration=duration,
            sensor_ids=sensor_ids,
            session_ids=session_ids,
        )

    async def get_observations(
        self,
        duration: int | None = None,
    ) -> list[list["FlightObservationSchema"]]:
        """Generate observations using the underlying AirTrafficClient.

        Args:
            duration: Override duration in seconds.

        Returns:
            List of observation lists per aircraft.
        """
        effective_duration = duration or self._duration

        settings = AirTrafficSettings(
            simulation_config_path=self._config_path,
            simulation_duration=effective_duration,
            number_of_aircraft=self._number_of_aircraft,
            sensor_ids=self._sensor_ids,
            session_ids=self._session_ids,
        )

        async with AirTrafficClient(settings) as client:
            return await client.generate_simulated_air_traffic_data(
                config_path=self._config_path,
                duration=effective_duration,
            )

"""Factory for creating air traffic providers."""

from typing import Literal

from .bayesian_provider import BayesianProvider
from .bluesky_provider import BlueSkyProvider
from .geojson_provider import GeoJSONProvider
from .opensky_provider import OpenSkyProvider
from .protocol import AirTrafficProvider

ProviderType = Literal["geojson", "bluesky", "bayesian", "opensky"]


def create_provider(
    name: ProviderType,
    *,
    config_path: str | None = None,
    number_of_aircraft: int | None = None,
    duration: int | None = None,
    sensor_ids: list[str] | None = None,
    session_ids: list[str] | None = None,
    viewport: tuple[float, float, float, float] | None = None,
    **kwargs,
) -> AirTrafficProvider:
    """Factory function to create providers by name.

    Args:
        name: Provider type - geojson, bluesky, bayesian, or opensky.
        config_path: Path to configuration file (provider-specific).
        number_of_aircraft: Number of aircraft to simulate.
        duration: Simulation/fetch duration in seconds.
        sensor_ids: List of sensor UUID strings.
        session_ids: List of session UUID strings.
        viewport: Geographic bounds for OpenSky (lat_min, lat_max, lon_min, lon_max).
        **kwargs: Additional provider-specific arguments.

    Returns:
        An AirTrafficProvider instance.

    Raises:
        ValueError: If the provider name is not recognized.
    """
    providers: dict[str, type] = {
        "geojson": GeoJSONProvider,
        "bluesky": BlueSkyProvider,
        "bayesian": BayesianProvider,
        "opensky": OpenSkyProvider,
    }

    if name not in providers:
        raise ValueError(f"Unknown provider: {name}. Available: {list(providers.keys())}")

    return providers[name].from_kwargs(
        config_path=config_path,
        number_of_aircraft=number_of_aircraft,
        duration=duration,
        sensor_ids=sensor_ids,
        session_ids=session_ids,
        viewport=viewport,
        **kwargs,
    )

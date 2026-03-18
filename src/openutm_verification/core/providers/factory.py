"""Factory for creating air traffic providers."""

from enum import StrEnum

from .bayesian_provider import BayesianProvider
from .bluesky_provider import BlueSkyProvider
from .geojson_provider import GeoJSONProvider
from .latency import DataQualityType, LatencyProviderWrapper
from .opensky_provider import OpenSkyProvider
from .protocol import AirTrafficProvider


class ProviderType(StrEnum):
    GEOJSON = "geojson"
    BLUESKY = "bluesky"
    BAYESIAN = "bayesian"
    OPENSKY = "opensky"


# Registry mapping data quality types to their wrapper classes.
# Add new entries here to support additional quality degradation modes
# without modifying the create_provider function.
_QUALITY_WRAPPERS: dict[DataQualityType, type] = {
    DataQualityType.LATENCY: LatencyProviderWrapper,
}


def create_provider(
    name: ProviderType,
    *,
    config_path: str | None = None,
    number_of_aircraft: int | None = None,
    duration: int | None = None,
    sensor_ids: list[str] | None = None,
    session_ids: list[str] | None = None,
    viewport: tuple[float, float, float, float] | None = None,
    data_quality: DataQualityType = DataQualityType.NOMINAL,
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
        data_quality: Data quality mode - "nominal" or "latency".
        **kwargs: Additional provider-specific arguments.

    Returns:
        An AirTrafficProvider instance, optionally wrapped with latency simulation.

    Raises:
        ValueError: If the provider name is not recognized.
    """
    providers: dict[ProviderType, type] = {
        ProviderType.GEOJSON: GeoJSONProvider,
        ProviderType.BLUESKY: BlueSkyProvider,
        ProviderType.BAYESIAN: BayesianProvider,
        ProviderType.OPENSKY: OpenSkyProvider,
    }

    if name not in providers:
        raise ValueError(f"Unknown provider: {name}. Available: {list(providers.keys())}")

    provider = providers[name].from_kwargs(
        config_path=config_path,
        number_of_aircraft=number_of_aircraft,
        duration=duration,
        sensor_ids=sensor_ids,
        session_ids=session_ids,
        viewport=viewport,
        **kwargs,
    )

    # Apply quality wrapper if registered for this quality type
    wrapper_cls = _QUALITY_WRAPPERS.get(data_quality)
    if wrapper_cls:
        return wrapper_cls(provider)

    return provider

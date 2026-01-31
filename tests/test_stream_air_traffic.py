"""Tests for the unified Stream Air Traffic step."""

import pytest

from openutm_verification.core.providers import ProviderType, create_provider
from openutm_verification.core.providers.geojson_provider import GeoJSONProvider
from openutm_verification.core.providers.opensky_provider import OpenSkyProvider
from openutm_verification.core.steps import AirTrafficStepClient
from openutm_verification.core.streamers import StreamResult, TargetType, create_streamer
from openutm_verification.core.streamers.null_streamer import NullStreamer


class TestProviderFactory:
    """Tests for the provider factory."""

    def test_create_geojson_provider(self):
        """Test creating a GeoJSON provider."""
        provider = create_provider(
            name="geojson",
            config_path="/some/path.geojson",
            duration=60,
            number_of_aircraft=3,
        )
        assert isinstance(provider, GeoJSONProvider)
        assert provider.name == "geojson"

    def test_create_opensky_provider(self):
        """Test creating an OpenSky provider."""
        viewport = (45.0, 48.0, 6.0, 11.0)
        provider = create_provider(
            name="opensky",
            viewport=viewport,
            duration=30,
        )
        assert isinstance(provider, OpenSkyProvider)
        assert provider.name == "opensky"

    def test_create_unknown_provider_raises(self):
        """Test that unknown provider name raises ValueError."""
        with pytest.raises(ValueError, match="Unknown provider"):
            create_provider(name="unknown")  # type: ignore


class TestStreamerFactory:
    """Tests for the streamer factory."""

    def test_create_null_streamer(self):
        """Test creating a null streamer."""
        streamer = create_streamer(name="none")
        assert isinstance(streamer, NullStreamer)
        assert streamer.name == "none"

    def test_create_unknown_streamer_raises(self):
        """Test that unknown streamer name raises ValueError."""
        with pytest.raises(ValueError, match="Unknown streamer"):
            create_streamer(name="unknown")  # type: ignore


class TestStreamResult:
    """Tests for StreamResult dataclass."""

    def test_stream_result_creation(self):
        """Test creating a StreamResult."""
        result = StreamResult(
            success=True,
            provider="geojson",
            target="none",
            duration_seconds=30,
            total_observations=100,
            total_batches=2,
        )
        assert result.success is True
        assert result.provider == "geojson"
        assert result.target == "none"
        assert result.total_observations == 100
        assert result.errors == []
        assert result.observations is None

    def test_stream_result_with_errors(self):
        """Test creating a StreamResult with errors."""
        result = StreamResult(
            success=False,
            provider="opensky",
            target="flight_blender",
            duration_seconds=30,
            total_observations=0,
            total_batches=0,
            errors=["Connection failed", "Timeout"],
        )
        assert result.success is False
        assert len(result.errors) == 2


class TestAirTrafficStepClient:
    """Tests for the AirTrafficStepClient."""

    def test_client_context_manager(self):
        """Test that client can be used as async context manager."""
        import asyncio

        async def test():
            async with AirTrafficStepClient() as client:
                assert client is not None

        asyncio.run(test())

    def test_step_registration(self):
        """Test that the step is registered in STEP_REGISTRY."""
        from openutm_verification.core.execution.scenario_runner import STEP_REGISTRY

        # Force registration by importing the client
        _ = AirTrafficStepClient

        assert "Stream Air Traffic" in STEP_REGISTRY
        entry = STEP_REGISTRY["Stream Air Traffic"]
        assert entry.client_class == AirTrafficStepClient
        assert entry.method_name == "stream_air_traffic"

    def test_step_param_model_has_required_fields(self):
        """Test that the parameter model has the expected fields."""
        from openutm_verification.core.execution.scenario_runner import STEP_REGISTRY

        entry = STEP_REGISTRY["Stream Air Traffic"]
        param_model = entry.param_model

        # Check required fields are present
        fields = param_model.model_fields
        assert "provider" in fields
        assert "duration" in fields
        assert "target" in fields

    def test_provider_type_literal(self):
        """Test that ProviderType includes expected values."""
        from typing import get_args

        expected = {"geojson", "bluesky", "bayesian", "opensky"}
        actual = set(get_args(ProviderType))
        assert actual == expected

    def test_target_type_literal(self):
        """Test that TargetType includes expected values."""
        from typing import get_args

        expected = {"flight_blender", "amqp", "none"}
        actual = set(get_args(TargetType))
        assert actual == expected

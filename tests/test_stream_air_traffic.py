"""Tests for the unified Stream Air Traffic step."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from openutm_verification.core.providers import ProviderType, create_provider
from openutm_verification.core.providers.geojson_provider import GeoJSONProvider
from openutm_verification.core.providers.opensky_provider import OpenSkyProvider
from openutm_verification.core.steps import AirTrafficStepClient
from openutm_verification.core.streamers import StreamResult, TargetType, create_streamer
from openutm_verification.core.streamers.null_streamer import NullStreamer
from openutm_verification.simulator.models.flight_data_types import FlightObservationSchema


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


# ============================================================================
# Integration Tests with Mocked Clients
# ============================================================================


def _create_mock_observations():
    """Helper to create mock flight observations."""
    return [
        [
            FlightObservationSchema(
                lat_dd=46.9,
                lon_dd=7.4,
                altitude_mm=1000000,
                traffic_source=0,
                source_type=0,
                icao_address="ABC123",
                timestamp=1234567890,
            ),
        ],
        [
            FlightObservationSchema(
                lat_dd=46.95,
                lon_dd=7.45,
                altitude_mm=1100000,
                traffic_source=0,
                source_type=0,
                icao_address="DEF456",
                timestamp=1234567891,
            ),
        ],
    ]


class TestGeoJSONProviderIntegration:
    """Integration tests for GeoJSONProvider with mocked AirTrafficClient."""

    @pytest.mark.asyncio
    @patch("openutm_verification.core.providers.geojson_provider.AirTrafficClient")
    async def test_geojson_provider_instantiates_client_with_correct_settings(self, mock_client_class):
        """Test that GeoJSONProvider passes correct settings to AirTrafficClient."""
        mock_observations = _create_mock_observations()

        # Setup mock client instance
        mock_client_instance = AsyncMock()
        mock_client_instance.generate_simulated_air_traffic_data = AsyncMock(return_value=mock_observations)
        mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_class.return_value.__aexit__ = AsyncMock(return_value=None)

        # Create provider with specific settings
        provider = GeoJSONProvider(
            config_path="/path/to/trajectory.geojson",
            number_of_aircraft=3,
            duration=60,
            sensor_ids=["sensor-uuid-1", "sensor-uuid-2"],
            session_ids=["session-uuid-1"],
        )

        # Call get_observations
        result = await provider.get_observations(duration=45)

        # Verify AirTrafficClient was instantiated with correct settings
        mock_client_class.assert_called_once()
        call_args = mock_client_class.call_args
        settings = call_args[0][0]  # First positional argument

        assert settings.simulation_config_path == "/path/to/trajectory.geojson"
        assert settings.simulation_duration == 45  # Should use the override duration
        assert settings.number_of_aircraft == 3
        assert settings.sensor_ids == ["sensor-uuid-1", "sensor-uuid-2"]
        assert settings.session_ids == ["session-uuid-1"]

        # Verify the method was called with correct arguments
        mock_client_instance.generate_simulated_air_traffic_data.assert_called_once_with(
            config_path="/path/to/trajectory.geojson",
            duration=45,
        )

        # Verify result
        assert result == mock_observations

    @pytest.mark.asyncio
    @patch("openutm_verification.core.providers.geojson_provider.AirTrafficClient")
    async def test_geojson_provider_uses_default_duration_when_not_overridden(self, mock_client_class):
        """Test that GeoJSONProvider uses constructor duration when not overridden."""
        mock_observations = _create_mock_observations()

        mock_client_instance = AsyncMock()
        mock_client_instance.generate_simulated_air_traffic_data = AsyncMock(return_value=mock_observations)
        mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_class.return_value.__aexit__ = AsyncMock(return_value=None)

        provider = GeoJSONProvider(config_path="/test.geojson", duration=120)

        # Call without duration override
        await provider.get_observations()

        # Should use constructor duration (120)
        settings = mock_client_class.call_args[0][0]
        assert settings.simulation_duration == 120


class TestBlueSkyProviderIntegration:
    """Integration tests for BlueSkyProvider with mocked BlueSkyClient."""

    @pytest.mark.asyncio
    @patch("openutm_verification.core.providers.bluesky_provider.BlueSkyClient")
    async def test_bluesky_provider_instantiates_client_with_correct_settings(self, mock_client_class):
        """Test that BlueSkyProvider passes correct settings to BlueSkyClient."""
        from openutm_verification.core.providers.bluesky_provider import BlueSkyProvider

        mock_observations = [
            [
                FlightObservationSchema(
                    lat_dd=46.9,
                    lon_dd=7.4,
                    altitude_mm=5000000,
                    traffic_source=0,
                    source_type=0,
                    icao_address="BLUESKY1",
                    timestamp=1234567890,
                ),
            ],
        ]

        mock_client_instance = AsyncMock()
        mock_client_instance.generate_bluesky_sim_air_traffic_data = AsyncMock(return_value=mock_observations)
        mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_class.return_value.__aexit__ = AsyncMock(return_value=None)

        provider = BlueSkyProvider(
            config_path="/path/to/scenario.scn",
            number_of_aircraft=2,
            duration=30,
            sensor_ids=["sensor-1"],
            session_ids=["session-1"],
        )

        result = await provider.get_observations(duration=25)

        # Verify BlueSkyClient was instantiated with correct settings
        mock_client_class.assert_called_once()
        settings = mock_client_class.call_args[0][0]

        assert settings.simulation_config_path == "/path/to/scenario.scn"
        assert settings.simulation_duration_seconds == 25
        assert settings.number_of_aircraft == 2
        assert settings.sensor_ids == ["sensor-1"]
        assert settings.session_ids == ["session-1"]

        # Verify method call
        mock_client_instance.generate_bluesky_sim_air_traffic_data.assert_called_once_with(
            config_path="/path/to/scenario.scn",
            duration=25,
        )

        assert result == mock_observations


class TestBayesianProviderIntegration:
    """Integration tests for BayesianProvider with mocked BayesianTrafficClient."""

    @pytest.mark.asyncio
    @patch("openutm_verification.core.providers.bayesian_provider.BayesianTrafficClient")
    async def test_bayesian_provider_instantiates_client_with_correct_settings(self, mock_client_class):
        """Test that BayesianProvider passes correct settings to BayesianTrafficClient."""
        from openutm_verification.core.providers.bayesian_provider import BayesianProvider

        mock_observations = [
            [
                FlightObservationSchema(
                    lat_dd=47.0,
                    lon_dd=8.0,
                    altitude_mm=3000000,
                    traffic_source=0,
                    source_type=0,
                    icao_address="BAYES1",
                    timestamp=1234567890,
                ),
            ],
        ]

        mock_client_instance = AsyncMock()
        mock_client_instance.generate_bayesian_sim_air_traffic_data = AsyncMock(return_value=mock_observations)
        mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_class.return_value.__aexit__ = AsyncMock(return_value=None)

        provider = BayesianProvider(
            config_path="/path/to/model.mat",
            number_of_aircraft=5,
            duration=100,
            sensor_ids=["sensor-bayesian"],
            session_ids=["session-bayesian"],
        )

        result = await provider.get_observations(duration=80)

        # Verify BayesianTrafficClient was instantiated with correct settings
        mock_client_class.assert_called_once()
        settings = mock_client_class.call_args[0][0]

        assert settings.simulation_config_path == "/path/to/model.mat"
        assert settings.simulation_duration_seconds == 80
        assert settings.number_of_aircraft == 5
        assert settings.sensor_ids == ["sensor-bayesian"]
        assert settings.session_ids == ["session-bayesian"]

        assert result == mock_observations

    @pytest.mark.asyncio
    @patch("openutm_verification.core.providers.bayesian_provider.BayesianTrafficClient")
    async def test_bayesian_provider_handles_none_result(self, mock_client_class):
        """Test that BayesianProvider returns empty list when client returns None."""
        from openutm_verification.core.providers.bayesian_provider import BayesianProvider

        mock_client_instance = AsyncMock()
        mock_client_instance.generate_bayesian_sim_air_traffic_data = AsyncMock(return_value=None)
        mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_class.return_value.__aexit__ = AsyncMock(return_value=None)

        provider = BayesianProvider()
        result = await provider.get_observations()

        assert result == []


class TestOpenSkyProviderIntegration:
    """Integration tests for OpenSkyProvider with mocked OpenSkyClient."""

    @pytest.mark.asyncio
    @patch("openutm_verification.core.providers.opensky_provider.OpenSkyClient")
    @patch("openutm_verification.core.providers.opensky_provider.get_settings")
    async def test_opensky_provider_instantiates_client_with_correct_viewport(self, mock_get_settings, mock_client_class):
        """Test that OpenSkyProvider passes correct viewport settings to OpenSkyClient."""
        mock_observations = [
            FlightObservationSchema(
                lat_dd=46.5,
                lon_dd=7.0,
                altitude_mm=10000000,
                traffic_source=2,
                source_type=1,
                icao_address="LIVE123",
                timestamp=1234567890,
            ),
            FlightObservationSchema(
                lat_dd=47.0,
                lon_dd=8.0,
                altitude_mm=11000000,
                traffic_source=2,
                source_type=1,
                icao_address="LIVE456",
                timestamp=1234567890,
            ),
        ]

        # Mock get_settings
        mock_config = MagicMock()
        mock_config.opensky.auth.client_id = "test-client-id"
        mock_config.opensky.auth.client_secret = "test-client-secret"
        mock_get_settings.return_value = mock_config

        mock_client_instance = AsyncMock()
        mock_client_instance.fetch_data = AsyncMock(return_value=mock_observations)
        mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_class.return_value.__aexit__ = AsyncMock(return_value=None)

        custom_viewport = (44.0, 49.0, 5.0, 12.0)
        provider = OpenSkyProvider(viewport=custom_viewport, duration=60)

        result = await provider.get_observations()

        # Verify OpenSkyClient was instantiated with correct settings
        mock_client_class.assert_called_once()
        settings = mock_client_class.call_args[0][0]

        assert settings.client_id == "test-client-id"
        assert settings.client_secret == "test-client-secret"
        assert settings.viewport == custom_viewport

        # Verify fetch_data was called
        mock_client_instance.fetch_data.assert_called_once()

        # Result should be wrapped in outer list for consistency
        assert result == [mock_observations]

    @pytest.mark.asyncio
    @patch("openutm_verification.core.providers.opensky_provider.OpenSkyClient")
    @patch("openutm_verification.core.providers.opensky_provider.get_settings")
    async def test_opensky_provider_returns_empty_list_when_no_data(self, mock_get_settings, mock_client_class):
        """Test that OpenSkyProvider returns empty list when no data available."""
        mock_config = MagicMock()
        mock_config.opensky.auth.client_id = "test-id"
        mock_config.opensky.auth.client_secret = "test-secret"
        mock_get_settings.return_value = mock_config

        mock_client_instance = AsyncMock()
        mock_client_instance.fetch_data = AsyncMock(return_value=None)
        mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_class.return_value.__aexit__ = AsyncMock(return_value=None)

        provider = OpenSkyProvider()
        result = await provider.get_observations()

        assert result == []


class TestFlightBlenderStreamerIntegration:
    """Integration tests for FlightBlenderStreamer with mocked FlightBlenderClient."""

    @pytest.mark.asyncio
    @patch("openutm_verification.core.streamers.flight_blender_streamer.FlightBlenderClient")
    @patch("openutm_verification.core.streamers.flight_blender_streamer.get_settings")
    async def test_flight_blender_streamer_submits_to_client(self, mock_get_settings, mock_fb_class):
        """Test that FlightBlenderStreamer properly submits observations to FlightBlenderClient."""
        from openutm_verification.core.streamers.flight_blender_streamer import FlightBlenderStreamer

        mock_observations = _create_mock_observations()

        # Mock get_settings
        mock_config = MagicMock()
        mock_config.flight_blender.url = "http://test-flight-blender:8080"
        mock_config.flight_blender.auth.username = "test-user"
        mock_config.flight_blender.auth.password = "test-pass"
        mock_get_settings.return_value = mock_config

        mock_fb_client = AsyncMock()
        mock_fb_client.submit_simulated_air_traffic = AsyncMock(return_value={"success": True, "observations_submitted": 1})
        mock_fb_class.return_value.__aenter__ = AsyncMock(return_value=mock_fb_client)
        mock_fb_class.return_value.__aexit__ = AsyncMock(return_value=None)

        # Create a mock provider
        mock_provider = AsyncMock()
        mock_provider.name = "geojson"
        mock_provider.get_observations = AsyncMock(return_value=mock_observations)

        streamer = FlightBlenderStreamer()
        result = await streamer.stream_from_provider(mock_provider, duration_seconds=30)

        # Verify FlightBlenderClient was instantiated with correct credentials
        mock_fb_class.assert_called_once()
        call_kwargs = mock_fb_class.call_args[1]
        assert call_kwargs["base_url"] == "http://test-flight-blender:8080"
        assert call_kwargs["credentials"]["username"] == "test-user"
        assert call_kwargs["credentials"]["password"] == "test-pass"

        # Verify submit was called with observations
        mock_fb_client.submit_simulated_air_traffic.assert_called_once()
        call_args = mock_fb_client.submit_simulated_air_traffic.call_args
        assert call_args[1]["observations"] == mock_observations

        # Verify result
        assert result.success is True
        assert result.provider == "geojson"
        assert result.target == "flight_blender"
        assert result.total_batches == 2

    @pytest.mark.asyncio
    async def test_flight_blender_streamer_handles_empty_observations(self):
        """Test that FlightBlenderStreamer handles empty observations gracefully."""
        from openutm_verification.core.streamers.flight_blender_streamer import FlightBlenderStreamer

        mock_provider = AsyncMock()
        mock_provider.name = "geojson"
        mock_provider.get_observations = AsyncMock(return_value=[])

        streamer = FlightBlenderStreamer()
        result = await streamer.stream_from_provider(mock_provider, duration_seconds=10)

        # Should succeed with zero observations, without calling FlightBlenderClient
        assert result.success is True
        assert result.total_observations == 0
        assert result.total_batches == 0

    @pytest.mark.asyncio
    @patch("openutm_verification.core.streamers.flight_blender_streamer.FlightBlenderClient")
    @patch("openutm_verification.core.streamers.flight_blender_streamer.get_settings")
    async def test_flight_blender_streamer_handles_client_error(self, mock_get_settings, mock_fb_class):
        """Test that FlightBlenderStreamer handles client errors gracefully."""
        from openutm_verification.core.streamers.flight_blender_streamer import FlightBlenderStreamer

        mock_observations = _create_mock_observations()

        mock_config = MagicMock()
        mock_config.flight_blender.url = "http://test:8080"
        mock_config.flight_blender.auth.username = "user"
        mock_config.flight_blender.auth.password = "pass"
        mock_get_settings.return_value = mock_config

        mock_fb_client = AsyncMock()
        mock_fb_client.submit_simulated_air_traffic = AsyncMock(side_effect=Exception("Connection refused"))
        mock_fb_class.return_value.__aenter__ = AsyncMock(return_value=mock_fb_client)
        mock_fb_class.return_value.__aexit__ = AsyncMock(return_value=None)

        mock_provider = AsyncMock()
        mock_provider.name = "geojson"
        mock_provider.get_observations = AsyncMock(return_value=mock_observations)

        streamer = FlightBlenderStreamer()
        result = await streamer.stream_from_provider(mock_provider, duration_seconds=30)

        assert result.success is False
        assert "Connection refused" in result.errors[0]


class TestNullStreamerIntegration:
    """Integration tests for NullStreamer."""

    @pytest.mark.asyncio
    async def test_null_streamer_collects_observations_without_sending(self):
        """Test that NullStreamer collects all observations and returns them."""
        mock_observations = [
            [
                FlightObservationSchema(
                    lat_dd=46.9,
                    lon_dd=7.4,
                    altitude_mm=1000000,
                    traffic_source=0,
                    source_type=0,
                    icao_address="NULL1",
                    timestamp=1234567890,
                ),
            ],
            [
                FlightObservationSchema(
                    lat_dd=47.0,
                    lon_dd=7.5,
                    altitude_mm=1100000,
                    traffic_source=0,
                    source_type=0,
                    icao_address="NULL2",
                    timestamp=1234567891,
                ),
            ],
        ]

        mock_provider = AsyncMock()
        mock_provider.name = "geojson"
        mock_provider.get_observations = AsyncMock(return_value=mock_observations)

        streamer = NullStreamer()
        result = await streamer.stream_from_provider(mock_provider, duration_seconds=30)

        # Verify provider was called with correct duration
        mock_provider.get_observations.assert_called_once_with(duration=30)

        # Verify result contains all observations
        assert result.success is True
        assert result.target == "none"
        assert result.total_batches == 2
        assert result.total_observations == 2
        assert result.observations == mock_observations


class TestEndToEndStreamAirTraffic:
    """End-to-end tests for the Stream Air Traffic step."""

    @pytest.mark.asyncio
    @patch("openutm_verification.core.providers.geojson_provider.AirTrafficClient")
    async def test_stream_air_traffic_with_null_target(self, mock_client_class):
        """Test complete flow: provider -> null streamer."""
        from openutm_verification.core.reporting.reporting_models import Status

        mock_observations = [
            [
                FlightObservationSchema(
                    lat_dd=46.9,
                    lon_dd=7.4,
                    altitude_mm=1000000,
                    traffic_source=0,
                    source_type=0,
                    icao_address="E2E1",
                    timestamp=1234567890,
                ),
            ],
        ]

        # Mock the AirTrafficClient used by GeoJSONProvider
        mock_client_instance = AsyncMock()
        mock_client_instance.generate_simulated_air_traffic_data = AsyncMock(return_value=mock_observations)
        mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_class.return_value.__aexit__ = AsyncMock(return_value=None)

        async with AirTrafficStepClient() as client:
            step_result = await client.stream_air_traffic(
                provider="geojson",
                duration=10,
                target="none",
                config_path="/test/path.geojson",
                number_of_aircraft=1,
            )

        # The @scenario_step decorator wraps the result in a StepResult
        assert step_result.status == Status.PASS
        assert step_result.name == "Stream Air Traffic"

        # The inner StreamResult is in step_result.result
        stream_result = step_result.result
        assert stream_result.success is True
        assert stream_result.provider == "geojson"
        assert stream_result.target == "none"
        assert stream_result.total_observations == 1
        assert stream_result.observations == mock_observations

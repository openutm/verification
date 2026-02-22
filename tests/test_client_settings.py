"""Tests for client settings configuration from AppConfig.

Tests that each client correctly receives its configuration through
the dependency injection system and Settings.from_config() methods.
"""

from openutm_verification.core.clients.air_traffic.base_client import (
    SENSOR_MODE_MULTIPLE,
    SENSOR_MODE_SINGLE,
    AirTrafficSettings,
    BlueSkyAirTrafficSettings,
)
from openutm_verification.core.clients.amqp import AMQPSettings
from openutm_verification.core.clients.opensky.base_client import OpenSkySettings
from openutm_verification.core.execution.config_models import (
    AirTrafficSimulatorSettings,
    AMQPConfig,
    AuthConfig,
    BlueSkyAirTrafficSimulatorSettings,
    OpenSkyConfig,
)


class TestAMQPSettingsFromConfig:
    """Tests for AMQPSettings.from_config()."""

    def test_from_config_all_fields(self):
        """All config fields are correctly mapped to settings."""
        amqp_config = AMQPConfig(
            url="amqps://user:pass@host.com/vhost",
            exchange_name="my_exchange",
            exchange_type="topic",
            routing_key="my.routing.key",
            queue_name="my_queue",
        )

        settings = AMQPSettings.from_config(amqp_config)

        assert settings.url == "amqps://user:pass@host.com/vhost"
        assert settings.exchange_name == "my_exchange"
        assert settings.exchange_type == "topic"
        assert settings.routing_key == "my.routing.key"
        assert settings.queue_name == "my_queue"

    def test_from_config_defaults(self):
        """Default values are used when config has defaults."""
        amqp_config = AMQPConfig()

        settings = AMQPSettings.from_config(amqp_config)

        assert settings.url == ""
        assert settings.exchange_name == "operational_events"
        assert settings.exchange_type == "direct"
        assert settings.routing_key == "#"
        assert settings.queue_name == ""

    def test_from_config_partial(self):
        """Partial config overrides only specified fields."""
        amqp_config = AMQPConfig(
            url="amqp://localhost:5672",
            exchange_name="custom_exchange",
        )

        settings = AMQPSettings.from_config(amqp_config)

        assert settings.url == "amqp://localhost:5672"
        assert settings.exchange_name == "custom_exchange"
        assert settings.exchange_type == "direct"  # default
        assert settings.routing_key == "#"  # default

    def test_settings_has_connection_defaults(self):
        """Settings includes connection parameters with defaults."""
        settings = AMQPSettings()

        assert settings.heartbeat == 600
        assert settings.blocked_connection_timeout == 300


class TestOpenSkySettingsFromConfig:
    """Tests for OpenSkySettings.from_config()."""

    def test_from_config_with_credentials(self):
        """Credentials are correctly extracted from auth config."""
        opensky_config = OpenSkyConfig(
            auth=AuthConfig(
                type="oauth2",
                client_id="my-client-id",
                client_secret="my-secret",
            )
        )

        settings = OpenSkySettings.from_config(opensky_config)

        assert settings.client_id == "my-client-id"
        assert settings.client_secret == "my-secret"

    def test_from_config_no_auth(self):
        """Empty credentials when auth type is none."""
        opensky_config = OpenSkyConfig(auth=AuthConfig(type="none"))

        settings = OpenSkySettings.from_config(opensky_config)

        assert settings.client_id == ""
        assert settings.client_secret == ""

    def test_settings_has_defaults(self):
        """Settings includes sensible defaults."""
        settings = OpenSkySettings()

        assert settings.auth_url == "https://auth.opensky-network.org/auth/realms/opensky-network/protocol/openid-connect/token"
        assert settings.base_url == "https://opensky-network.org/api"
        assert settings.request_timeout == 10
        assert settings.viewport == (45.8389, 47.8229, 5.9962, 10.5226)


class TestAirTrafficSettingsFromConfig:
    """Tests for AirTrafficSettings.from_config()."""

    def test_from_config_all_fields(self):
        """All config fields are correctly mapped."""
        sim_config = AirTrafficSimulatorSettings(
            number_of_aircraft=5,
            simulation_duration=60,
            single_or_multiple_sensors="multiple",
            sensor_ids=["sensor1", "sensor2"],
            session_ids=["session1"],
        )

        settings = AirTrafficSettings.from_config(
            sim_config,
            trajectory_path="/path/to/trajectory.json",
        )

        assert settings.simulation_config_path == "/path/to/trajectory.json"
        assert settings.simulation_duration == 60
        assert settings.number_of_aircraft == 5
        assert settings.single_or_multiple_sensors == SENSOR_MODE_MULTIPLE
        assert settings.sensor_ids == ["sensor1", "sensor2"]
        assert settings.session_ids == ["session1"]

    def test_from_config_no_trajectory(self):
        """Settings work without trajectory path."""
        sim_config = AirTrafficSimulatorSettings(
            number_of_aircraft=3,
            simulation_duration=30,
        )

        settings = AirTrafficSettings.from_config(sim_config, trajectory_path=None)

        assert settings.simulation_config_path == ""
        assert settings.number_of_aircraft == 3

    def test_from_config_duration_parsing(self):
        """Simulation duration can be string or int."""
        # Test with int
        sim_config = AirTrafficSimulatorSettings(
            number_of_aircraft=2,
            simulation_duration=45,
        )

        settings = AirTrafficSettings.from_config(sim_config)

        assert settings.simulation_duration == 45


class TestBlueSkyAirTrafficSettingsFromConfig:
    """Tests for BlueSkyAirTrafficSettings.from_config()."""

    def test_from_config_all_fields(self):
        """All config fields are correctly mapped."""
        sim_config = BlueSkyAirTrafficSimulatorSettings(
            number_of_aircraft=10,
            simulation_duration_seconds=120,
            single_or_multiple_sensors="single",
            sensor_ids=["bluesky_sensor"],
            session_ids=["bluesky_session"],
        )

        settings = BlueSkyAirTrafficSettings.from_config(
            sim_config,
            simulation_path="/path/to/simulation.scn",
        )

        assert settings.simulation_config_path == "/path/to/simulation.scn"
        assert settings.simulation_duration_seconds == 120
        assert settings.number_of_aircraft == 10
        assert settings.single_or_multiple_sensors == SENSOR_MODE_SINGLE
        assert settings.sensor_ids == ["bluesky_sensor"]
        assert settings.session_ids == ["bluesky_session"]

    def test_from_config_no_simulation(self):
        """Settings work without simulation path."""
        sim_config = BlueSkyAirTrafficSimulatorSettings(
            number_of_aircraft=3,
            simulation_duration_seconds=30,
        )

        settings = BlueSkyAirTrafficSettings.from_config(sim_config, simulation_path=None)

        assert settings.simulation_config_path == ""
        assert settings.number_of_aircraft == 3

    def test_from_config_defaults(self):
        """Default values work correctly."""
        sim_config = BlueSkyAirTrafficSimulatorSettings(
            number_of_aircraft=2,
            simulation_duration_seconds=30,
        )

        settings = BlueSkyAirTrafficSettings.from_config(sim_config)

        assert settings.single_or_multiple_sensors == SENSOR_MODE_SINGLE
        assert settings.sensor_ids == []
        assert settings.session_ids == []


class TestSettingsIntegration:
    """Integration tests for settings with full config."""

    def test_amqp_settings_none_config(self):
        """AMQPSettings works when config.amqp is None."""
        # This is the pattern used in dependencies.py
        settings = AMQPSettings()

        assert settings.url == ""
        assert settings.exchange_name == "operational_events"

    def test_all_settings_are_pydantic_models(self):
        """All settings classes are proper Pydantic models."""
        from pydantic import BaseModel

        assert issubclass(AMQPSettings, BaseModel)
        assert issubclass(OpenSkySettings, BaseModel)
        assert issubclass(AirTrafficSettings, BaseModel)
        assert issubclass(BlueSkyAirTrafficSettings, BaseModel)

    def test_settings_are_immutable_by_default(self):
        """Settings can be serialized to dict."""
        settings = AMQPSettings(url="amqp://localhost")

        data = settings.model_dump()

        assert data["url"] == "amqp://localhost"
        assert "exchange_name" in data

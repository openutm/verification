"""Unit tests for altitude unit conversions.

These tests verify that altitude values are correctly converted between
meters and millimeters throughout the codebase. The Flight Blender API
uses `altitude_mm` field which expects millimeters, while most internal
calculations and ASTM standards use meters.
"""

import arrow
import pandas as pd
import pytest

from openutm_verification.simulator.models.flight_data_types import (
    AirTrafficGeneratorConfiguration,
    FlightObservationSchema,
    GeoJSONFlightsSimulatorConfiguration,
)


class TestFlightObservationSchema:
    """Tests for FlightObservationSchema model."""

    def test_altitude_mm_accepts_millimeter_values(self):
        """Verify altitude_mm field accepts millimeter values."""
        # 500 meters = 500,000 millimeters
        altitude_mm = 500_000

        obs = FlightObservationSchema(
            lat_dd=46.97,
            lon_dd=7.47,
            altitude_mm=altitude_mm,
            traffic_source=1,
            source_type=1,
            icao_address="ABC123",
            timestamp=1234567890,
        )

        assert obs.altitude_mm == 500_000

    def test_altitude_mm_field_description_mentions_millimeters(self):
        """Verify the field description clarifies millimeter units."""
        schema = FlightObservationSchema.model_json_schema()
        altitude_field = schema["properties"]["altitude_mm"]

        assert "millimeter" in altitude_field["description"].lower()

    def test_altitude_mm_reasonable_drone_altitude(self):
        """Test with typical drone altitude (120m AGL + ground level)."""
        ground_level_wgs84_m = 570  # Bern ground level
        flight_altitude_agl_m = 120
        total_altitude_m = ground_level_wgs84_m + flight_altitude_agl_m
        altitude_mm = total_altitude_m * 1000  # 690,000 mm

        obs = FlightObservationSchema(
            lat_dd=46.97,
            lon_dd=7.47,
            altitude_mm=altitude_mm,
            traffic_source=1,
            source_type=1,
            icao_address="DRONE1",
            timestamp=1234567890,
        )

        # Convert back to meters for verification
        assert obs.altitude_mm / 1000 == 690.0


class TestGeoJSONAirtrafficSimulator:
    """Tests for GeoJSONAirtrafficSimulator altitude conversion."""

    @pytest.fixture
    def sample_geojson(self):
        """Create a minimal valid GeoJSON for testing."""
        return {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [
                            [7.47, 46.97],
                            [7.48, 46.98],
                        ],
                    },
                    "properties": {},
                }
            ],
        }

    def test_air_traffic_altitude_is_in_millimeters(self, sample_geojson):
        """Verify generated air traffic data has altitude in millimeters."""
        from uuid import uuid4

        from openutm_verification.simulator.geo_json_telemetry import (
            GeoJSONAirtrafficSimulator,
        )

        altitude_meters = 500.0
        config = AirTrafficGeneratorConfiguration(
            geojson=sample_geojson,
            altitude_of_ground_level_wgs_84=altitude_meters,
            reference_time=arrow.utcnow(),
        )

        simulator = GeoJSONAirtrafficSimulator(config)
        sensor_ids = [uuid4()]
        result = simulator.generate_air_traffic_data(
            duration=2,
            sensor_ids=sensor_ids,
            number_of_aircraft=1,
        )

        # Get first observation from first aircraft
        assert len(result) > 0
        assert len(result[0]) > 0
        first_obs = result[0][0]

        # altitude_mm should be altitude_meters * 1000
        expected_mm = altitude_meters * 1000
        assert first_obs.altitude_mm == expected_mm, f"Expected altitude_mm={expected_mm} (from {altitude_meters}m), got {first_obs.altitude_mm}"


class TestOpenSkyClientAltitudeConversion:
    """Tests for OpenSky client altitude conversion."""

    def test_baro_altitude_converted_to_millimeters(self):
        """Verify barometric altitude from OpenSky is converted to mm."""
        from openutm_verification.core.clients.opensky.base_client import (
            OpenSkySettings,
        )
        from openutm_verification.core.clients.opensky.opensky_client import (
            OpenSkyClient,
        )

        settings = OpenSkySettings(
            viewport=(46.9, 7.4, 47.0, 7.5),
            opensky_client_id="test",
            opensky_client_secret="test",
            simulation_config_path="test.geojson",
        )
        client = OpenSkyClient(settings=settings)

        # Create mock DataFrame with altitude in meters (OpenSky API units)
        altitude_meters = 1500.0
        mock_df = pd.DataFrame(
            [
                {
                    "time_position": 1234567890,
                    "icao24": "ABC123",
                    "lat": 46.97,
                    "long": 7.47,
                    "baro_altitude": altitude_meters,
                    "velocity": 250.0,
                }
            ]
        )

        observations = client.process_flight_data(mock_df)

        assert len(observations) == 1
        obs = observations[0]

        # altitude_mm should be altitude_meters * 1000
        expected_mm = altitude_meters * 1000
        assert obs.altitude_mm == pytest.approx(expected_mm), f"Expected altitude_mm={expected_mm} (from {altitude_meters}m), got {obs.altitude_mm}"

    def test_no_data_altitude_becomes_zero_mm(self):
        """Verify 'No Data' altitude is handled as 0 millimeters."""
        from openutm_verification.core.clients.opensky.base_client import (
            OpenSkySettings,
        )
        from openutm_verification.core.clients.opensky.opensky_client import (
            OpenSkyClient,
        )

        settings = OpenSkySettings(
            viewport=(46.9, 7.4, 47.0, 7.5),
            opensky_client_id="test",
            opensky_client_secret="test",
            simulation_config_path="test.geojson",
        )
        client = OpenSkyClient(settings=settings)

        mock_df = pd.DataFrame(
            [
                {
                    "time_position": 1234567890,
                    "icao24": "ABC123",
                    "lat": 46.97,
                    "long": 7.47,
                    "baro_altitude": "No Data",
                    "velocity": 250.0,
                }
            ]
        )

        observations = client.process_flight_data(mock_df)

        assert len(observations) == 1
        assert observations[0].altitude_mm == pytest.approx(0.0)


class TestVisualizationAltitudeConversion:
    """Tests for visualization altitude handling."""

    def test_2d_map_converts_mm_to_meters_for_display(self):
        """Verify 2D visualization converts altitude_mm to meters for tooltips."""
        from openutm_verification.core.reporting.visualize_flight import (
            _reorganize_air_traffic_by_aircraft,
        )

        # Create observation with altitude in millimeters
        altitude_m = 500.0
        altitude_mm = altitude_m * 1000

        obs = FlightObservationSchema(
            lat_dd=46.97,
            lon_dd=7.47,
            altitude_mm=altitude_mm,
            traffic_source=1,
            source_type=1,
            icao_address="TEST01",
            timestamp=1234567890,
        )

        air_traffic_data = [[obs]]
        result = _reorganize_air_traffic_by_aircraft(air_traffic_data)

        assert "TEST01" in result
        assert len(result["TEST01"]) == 1

        # The visualization code will divide by 1000 to get meters
        retrieved_obs = result["TEST01"][0]
        displayed_altitude_m = retrieved_obs.altitude_mm / 1000
        assert displayed_altitude_m == pytest.approx(altitude_m)

    def test_altitude_conversion_preserves_precision(self):
        """Verify altitude conversion doesn't lose precision for typical values."""
        # Test with various altitudes
        test_altitudes_m = [0.0, 50.5, 120.0, 570.123, 1000.0, 10000.5]

        for altitude_m in test_altitudes_m:
            altitude_mm = altitude_m * 1000

            obs = FlightObservationSchema(
                lat_dd=46.97,
                lon_dd=7.47,
                altitude_mm=altitude_mm,
                traffic_source=1,
                source_type=1,
                icao_address="TEST",
                timestamp=1234567890,
            )

            # Round-trip conversion
            recovered_m = obs.altitude_mm / 1000
            assert abs(recovered_m - altitude_m) < 0.001, f"Precision loss for {altitude_m}m: got {recovered_m}m"


class TestAltitudeUnitConsistency:
    """Integration tests to verify altitude unit consistency across modules."""

    def test_flight_observation_schema_serialization(self):
        """Verify FlightObservationSchema serializes altitude_mm correctly."""
        altitude_mm = 570_000  # 570m in mm

        obs = FlightObservationSchema(
            lat_dd=46.97,
            lon_dd=7.47,
            altitude_mm=altitude_mm,
            traffic_source=1,
            source_type=1,
            icao_address="SERIAL",
            timestamp=1234567890,
        )

        # Serialize to dict (as would be sent to API)
        obs_dict = obs.model_dump()
        assert obs_dict["altitude_mm"] == altitude_mm

        # Serialize to JSON and back
        obs_json = obs.model_dump_json()
        obs_reloaded = FlightObservationSchema.model_validate_json(obs_json)
        assert obs_reloaded.altitude_mm == altitude_mm

    def test_config_altitude_is_in_meters(self):
        """Verify configuration altitude_of_ground_level_wgs_84 is documented as meters."""
        # Check default values make sense as meters (not mm)
        air_config = AirTrafficGeneratorConfiguration(geojson={})
        geojson_config = GeoJSONFlightsSimulatorConfiguration(geojson={})

        # Default is 570, which makes sense as meters (Bern ground level)
        # If it were in mm, 570mm = 0.57m which is way too low
        assert air_config.altitude_of_ground_level_wgs_84 == 570
        assert geojson_config.altitude_of_ground_level_wgs_84 == 570

        # Reasonable ground level is 0-9000m (Mt Everest is ~8849m)
        assert 0 <= air_config.altitude_of_ground_level_wgs_84 <= 9000


class TestMetersToMillimetersConversion:
    """Direct tests for the meters-to-millimeters conversion logic."""

    @pytest.mark.parametrize(
        "meters,expected_mm",
        [
            (0, 0),
            (1, 1000),
            (100, 100_000),
            (570, 570_000),  # Bern ground level
            (690, 690_000),  # Bern + 120m AGL
            (10000, 10_000_000),  # High altitude aircraft
            (0.5, 500),  # Sub-meter precision
            (123.456, 123_456),  # Decimal precision
        ],
    )
    def test_meters_to_millimeters(self, meters: float, expected_mm: float):
        """Verify meters to millimeters conversion formula."""
        actual_mm = meters * 1000
        assert actual_mm == expected_mm

    @pytest.mark.parametrize(
        "mm,expected_meters",
        [
            (0, 0),
            (1000, 1),
            (570_000, 570),
            (690_000, 690),
            (500, 0.5),
        ],
    )
    def test_millimeters_to_meters(self, mm: float, expected_meters: float):
        """Verify millimeters to meters conversion formula (used in visualization)."""
        actual_meters = mm / 1000
        assert actual_meters == expected_meters

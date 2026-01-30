"""Tests for SuiteScenario.merge_defaults() and config loading."""

from pathlib import Path

import yaml

from openutm_verification.core.execution.config_models import (
    AppConfig,
    DataFiles,
    SuiteConfig,
    SuiteScenario,
)


class TestSuiteScenarioMergeDefaults:
    """Test SuiteScenario.merge_defaults() method."""

    def test_merge_fills_all_none_fields(self):
        """When scenario has no overrides, all fields come from defaults."""
        defaults = DataFiles(
            trajectory="default_trajectory.json",
            simulation="default_simulation.scn",
            flight_declaration="default_fd.json",
            flight_declaration_via_operational_intent="default_fdoi.json",
            geo_fence="default_geo.geojson",
        )
        scenario = SuiteScenario(name="test_scenario")

        scenario.merge_defaults(defaults)

        assert scenario.trajectory == "default_trajectory.json"
        assert scenario.simulation == "default_simulation.scn"
        assert scenario.flight_declaration == "default_fd.json"
        assert scenario.flight_declaration_via_operational_intent == "default_fdoi.json"
        assert scenario.geo_fence == "default_geo.geojson"

    def test_merge_preserves_explicit_overrides(self):
        """Explicitly set fields are not overwritten by defaults."""
        defaults = DataFiles(
            trajectory="default_trajectory.json",
            simulation="default_simulation.scn",
            flight_declaration="default_fd.json",
            geo_fence="default_geo.geojson",
        )
        scenario = SuiteScenario(
            name="test_scenario",
            trajectory="override_trajectory.json",
            simulation="override_simulation.scn",
        )

        scenario.merge_defaults(defaults)

        # Overrides preserved
        assert scenario.trajectory == "override_trajectory.json"
        assert scenario.simulation == "override_simulation.scn"
        # Defaults used for None fields
        assert scenario.flight_declaration == "default_fd.json"
        assert scenario.geo_fence == "default_geo.geojson"

    def test_merge_partial_overrides(self):
        """Only None fields are filled from defaults."""
        defaults = DataFiles(
            trajectory="default_trajectory.json",
            simulation="default_simulation.scn",
            flight_declaration="default_fd.json",
        )
        scenario = SuiteScenario(
            name="test_scenario",
            trajectory="trajectory_f3.json",  # Override
            # simulation is None - use default
            # flight_declaration is None - use default
        )

        scenario.merge_defaults(defaults)

        assert scenario.trajectory == "trajectory_f3.json"  # Override preserved
        assert scenario.simulation == "default_simulation.scn"  # Default used
        assert scenario.flight_declaration == "default_fd.json"  # Default used

    def test_merge_with_none_defaults(self):
        """When default is also None, field stays None."""
        defaults = DataFiles(trajectory="traj.json")  # simulation is None
        scenario = SuiteScenario(name="test")  # simulation is None

        scenario.merge_defaults(defaults)

        assert scenario.trajectory == "traj.json"
        assert scenario.simulation is None


class TestSuiteConfigResolve:
    """Test SuiteConfig.resolve_paths() method."""

    def test_resolve_paths_calls_merge_on_scenarios(self, tmp_path):
        """SuiteConfig.resolve_paths should work with merged scenarios."""
        # Create test files
        (tmp_path / "traj.json").write_text("{}")
        (tmp_path / "fd.json").write_text("{}")

        scenario = SuiteScenario(
            name="test",
            trajectory=str(tmp_path / "traj.json"),
            flight_declaration=str(tmp_path / "fd.json"),
        )
        suite = SuiteConfig(scenarios=[scenario])

        suite.resolve_paths(tmp_path)

        # Paths should be resolved (absolute)
        assert Path(scenario.trajectory).is_absolute()
        assert Path(scenario.flight_declaration).is_absolute()


class TestAppConfigResolvePathsMergesDefaults:
    """Test that AppConfig.resolve_paths() merges defaults into scenarios."""

    def test_config_loading_merges_defaults(self, tmp_path):
        """When config is loaded, scenario None fields are filled from data_files."""
        # Create test files
        (tmp_path / "default_traj.json").write_text("{}")
        (tmp_path / "override_traj.json").write_text("{}")
        (tmp_path / "default_fd.json").write_text("{}")
        (tmp_path / "default_geo.geojson").write_text("{}")
        (tmp_path / "sim.scn").write_text("")

        config_data = {
            "version": "1.0",
            "flight_blender": {
                "url": "http://localhost:8000",
                "auth": {"type": "none"},
            },
            "opensky": {"auth": {"type": "none"}},
            "air_traffic_simulator_settings": {
                "number_of_aircraft": 3,
                "simulation_duration": 10,
            },
            "blue_sky_air_traffic_simulator_settings": {
                "number_of_aircraft": 3,
                "simulation_duration_seconds": 30,
            },
            "bayesian_air_traffic_simulator_settings": {
                "number_of_aircraft": 3,
                "simulation_duration_seconds": 30,
            },
            "data_files": {
                "trajectory": "default_traj.json",
                "flight_declaration": "default_fd.json",
                "geo_fence": "default_geo.geojson",
            },
            "suites": {
                "basic": {
                    "scenarios": [
                        {
                            "name": "scenario_with_override",
                            "trajectory": "override_traj.json",
                            "simulation": "sim.scn",
                            # flight_declaration not set - should use default
                        },
                        {
                            "name": "scenario_no_override",
                            # All fields None - should use all defaults
                        },
                    ]
                }
            },
            "reporting": {"output_dir": "reports"},
        }

        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump(config_data))

        config = AppConfig(**config_data)
        config.resolve_paths(config_file)

        # Get scenarios
        scenario_with_override = config.suites["basic"].scenarios[0]
        scenario_no_override = config.suites["basic"].scenarios[1]

        # Scenario with override: trajectory and simulation are overridden
        assert "override_traj.json" in scenario_with_override.trajectory
        assert "sim.scn" in scenario_with_override.simulation
        # But flight_declaration should come from defaults
        assert "default_fd.json" in scenario_with_override.flight_declaration
        assert "default_geo.geojson" in scenario_with_override.geo_fence

        # Scenario without overrides: all should come from defaults
        assert "default_traj.json" in scenario_no_override.trajectory
        assert "default_fd.json" in scenario_no_override.flight_declaration
        assert "default_geo.geojson" in scenario_no_override.geo_fence
        # Simulation was None in both scenario and defaults
        assert scenario_no_override.simulation is None

    def test_daa_scenario_config_example(self, tmp_path):
        """Test the exact test_scenario scenario case: trajectory override with simulation override."""
        # Create test files
        (tmp_path / "trajectory_f1.json").write_text("{}")
        (tmp_path / "trajectory_f3.json").write_text("{}")
        (tmp_path / "blue_sky_sim_bern.scn").write_text("")
        (tmp_path / "fd.json").write_text("{}")
        (tmp_path / "geo.geojson").write_text("{}")

        config_data = {
            "version": "1.0",
            "flight_blender": {
                "url": "http://localhost:8000",
                "auth": {"type": "none"},
            },
            "opensky": {"auth": {"type": "none"}},
            "air_traffic_simulator_settings": {
                "number_of_aircraft": 3,
                "simulation_duration": 10,
            },
            "blue_sky_air_traffic_simulator_settings": {
                "number_of_aircraft": 3,
                "simulation_duration_seconds": 30,
            },
            "bayesian_air_traffic_simulator_settings": {
                "number_of_aircraft": 3,
                "simulation_duration_seconds": 30,
            },
            "data_files": {
                "trajectory": "trajectory_f1.json",  # DEFAULT
                "flight_declaration": "fd.json",
                "geo_fence": "geo.geojson",
            },
            "suites": {
                "basic_conformance": {
                    "scenarios": [
                        {
                            "name": "test_scenario",
                            "trajectory": "trajectory_f3.json",  # OVERRIDE
                            "simulation": "blue_sky_sim_bern.scn",  # OVERRIDE
                        },
                    ]
                }
            },
            "reporting": {"output_dir": "reports"},
        }

        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump(config_data))

        config = AppConfig(**config_data)
        config.resolve_paths(config_file)

        daa_scenario = config.suites["basic_conformance"].scenarios[0]

        # The key test: trajectory should be trajectory_f3.json, NOT trajectory_f1.json
        assert "trajectory_f3.json" in daa_scenario.trajectory
        assert "trajectory_f1.json" not in daa_scenario.trajectory

        # Simulation override should be preserved
        assert "blue_sky_sim_bern.scn" in daa_scenario.simulation

        # Defaults should be used for unset fields
        assert "fd.json" in daa_scenario.flight_declaration
        assert "geo.geojson" in daa_scenario.geo_fence

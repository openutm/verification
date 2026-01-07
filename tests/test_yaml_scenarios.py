import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml

from openutm_verification.core.execution.config_models import DataFiles
from openutm_verification.core.execution.definitions import ScenarioDefinition
from openutm_verification.server.runner import SessionManager

SCENARIOS_DIR = Path(os.getenv("SCENARIOS_PATH", Path(__file__).parent.parent / "scenarios"))
YAML_FILES = list(SCENARIOS_DIR.glob("*.yaml"))


@pytest.fixture
def mock_clients():
    """Create mocks for all client classes."""
    mocks = {}

    # FlightBlenderClient mock
    fb_client = AsyncMock()
    # Mock context managers
    fb_client.create_flight_declaration = MagicMock()
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=None)
    cm.__aexit__ = AsyncMock(return_value=None)
    fb_client.create_flight_declaration.return_value = cm

    # Mock methods that return values used in other steps
    fb_client.upload_geo_fence.return_value = {"id": "geo_fence_123"}
    fb_client.upload_flight_declaration.return_value = {"id": "flight_decl_123", "is_approved": True}
    fb_client.start_stop_sdsp_session.return_value = "Session Started"

    # Mock methods that return objects with attributes accessed in YAML
    # e.g. ${{ steps.Generate Simulated Air Traffic Data.result.details }}
    # But wait, we changed it to just .result in the previous turn.
    # Let's check if any other steps return complex objects.

    mocks["FlightBlenderClient"] = fb_client

    # AirTrafficClient mock
    at_client = AsyncMock()
    # Mock generate_simulated_air_traffic_data to return a list of observations
    # The YAML expects .result to be the observations list directly now
    at_client.generate_simulated_air_traffic_data.return_value = [{"lat_dd": 47.0, "lon_dd": 7.5}]
    mocks["AirTrafficClient"] = at_client

    # OpenSkyClient mock
    os_client = AsyncMock()
    os_client.fetch_data.return_value = [{"lat_dd": 47.0, "lon_dd": 7.5}]
    mocks["OpenSkyClient"] = os_client

    # CommonClient mock
    common_client = AsyncMock()
    common_client.generate_uuid.return_value = "uuid-1234"
    mocks["CommonClient"] = common_client

    return mocks


@pytest.fixture
def mock_data_files():
    return DataFiles(
        trajectory="path/to/trajectory.json", flight_declaration="path/to/flight_declaration.json", geo_fence="path/to/geo_fence.geojson"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("yaml_file", YAML_FILES, ids=[f.name for f in YAML_FILES])
async def test_yaml_scenario_execution(yaml_file, mock_clients, mock_data_files):
    """Verify that each YAML scenario can be loaded and executed with mocked clients."""

    # Load YAML
    with open(yaml_file, "r") as f:
        scenario_data = yaml.safe_load(f)
    scenario = ScenarioDefinition(**scenario_data)

    # Initialize SessionManager
    # We mock _load_config to avoid reading real config files
    with (
        patch("openutm_verification.server.runner.SessionManager._load_config") as mock_load_config,
        patch("openutm_verification.server.runner.SessionManager._generate_data") as mock_gen_data,
    ):
        mock_load_config.return_value = MagicMock()
        mock_load_config.return_value.suites = {"default": {}}

        # Mock _generate_data to return None, None (we don't need real data for this test)
        mock_gen_data.return_value = (None, None)

        manager = SessionManager()

        # Initialize session (creates resolver)
        # We need to patch DependencyResolver.resolve to return our mocks
        with patch("openutm_verification.core.execution.dependency_resolution.DependencyResolver.resolve", new_callable=AsyncMock) as mock_resolve:

            async def resolve_side_effect(dependency_type):
                if dependency_type == DataFiles:
                    return mock_data_files

                client_name = dependency_type.__name__
                if client_name in mock_clients:
                    return mock_clients[client_name]

                return AsyncMock()

            mock_resolve.side_effect = resolve_side_effect

            # We need to manually set session_resolver because initialize_session creates a new one
            # Alternatively, we can mock DependencyResolver class
            with patch("openutm_verification.server.runner.DependencyResolver") as MockResolverCls:
                mock_resolver_instance = MockResolverCls.return_value
                mock_resolver_instance.resolve = mock_resolve

                await manager.initialize_session()

                # Run scenario
                results = await manager.run_scenario(scenario)

                # Verify results
                for step_result in results:
                    if step_result["status"] == "running":
                        continue

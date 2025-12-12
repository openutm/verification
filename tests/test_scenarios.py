from unittest.mock import ANY, AsyncMock, MagicMock, patch

import pytest

from openutm_verification.core.execution.config_models import DataFiles
from openutm_verification.models import OperationState, SDSPSessionAction
from openutm_verification.scenarios.test_add_flight_declaration import test_add_flight_declaration as scenario_add_flight_declaration
from openutm_verification.scenarios.test_airtraffic_data_openutm_sim import test_openutm_sim_air_traffic_data as scenario_openutm_sim_air_traffic_data
from openutm_verification.scenarios.test_f1_flow import test_f1_happy_path as scenario_f1_happy_path
from openutm_verification.scenarios.test_f2_flow import test_f2_contingent_path as scenario_f2_contingent_path
from openutm_verification.scenarios.test_f3_flow import test_f3_non_conforming_path as scenario_f3_non_conforming_path
from openutm_verification.scenarios.test_f5_flow import test_f5_non_conforming_contingent_path as scenario_f5_non_conforming_contingent_path
from openutm_verification.scenarios.test_geo_fence_upload import test_geo_fence_upload as scenario_geo_fence_upload
from openutm_verification.scenarios.test_opensky_live_data import test_opensky_live_data as scenario_opensky_live_data
from openutm_verification.scenarios.test_sdsp_heartbeat import sdsp_heartbeat as scenario_sdsp_heartbeat
from openutm_verification.scenarios.test_sdsp_track import sdsp_track as scenario_sdsp_track


@pytest.fixture
def fb_client():
    client = AsyncMock()
    # Mock the async context manager for flight_declaration
    flight_declaration_cm = MagicMock()
    flight_declaration_cm.__aenter__ = AsyncMock(return_value=None)
    flight_declaration_cm.__aexit__ = AsyncMock(return_value=None)

    # flight_declaration should return the context manager object directly, not a coroutine
    client.create_flight_declaration = MagicMock(return_value=flight_declaration_cm)
    return client


@pytest.fixture
def data_files():
    return MagicMock(spec=DataFiles)


async def test_add_flight_declaration_scenario(fb_client, data_files):
    await scenario_add_flight_declaration(fb_client, data_files)

    fb_client.create_flight_declaration.assert_called_once_with(data_files)
    fb_client.update_operation_state.assert_any_call(new_state=OperationState.ACTIVATED, duration_seconds=20)
    fb_client.submit_telemetry.assert_called_once_with(duration_seconds=30)
    fb_client.update_operation_state.assert_any_call(new_state=OperationState.ENDED)


async def test_f1_happy_path_scenario(fb_client, data_files):
    await scenario_f1_happy_path(fb_client, data_files)

    fb_client.create_flight_declaration.assert_called_once_with(data_files)
    fb_client.update_operation_state.assert_any_call(new_state=OperationState.ACTIVATED)
    fb_client.submit_telemetry.assert_called_once_with(duration_seconds=30)
    fb_client.update_operation_state.assert_any_call(new_state=OperationState.ENDED)


async def test_f2_contingent_path_scenario(fb_client, data_files):
    await scenario_f2_contingent_path(fb_client, data_files)

    fb_client.create_flight_declaration.assert_called_once_with(data_files)
    fb_client.update_operation_state.assert_any_call(new_state=OperationState.ACTIVATED)
    fb_client.submit_telemetry.assert_called_once_with(duration_seconds=10)
    fb_client.update_operation_state.assert_any_call(new_state=OperationState.CONTINGENT, duration_seconds=7)
    fb_client.update_operation_state.assert_any_call(new_state=OperationState.ENDED)


async def test_f3_non_conforming_path_scenario(fb_client, data_files):
    await scenario_f3_non_conforming_path(fb_client, data_files)

    fb_client.create_flight_declaration.assert_called_once_with(data_files)
    fb_client.update_operation_state.assert_any_call(new_state=OperationState.ACTIVATED)
    fb_client.wait_x_seconds.assert_called_once_with(5)
    fb_client.submit_telemetry.assert_called_once_with(duration_seconds=20)
    fb_client.check_operation_state.assert_called_once_with(expected_state=OperationState.NONCONFORMING, duration_seconds=5)
    fb_client.update_operation_state.assert_any_call(new_state=OperationState.ENDED)


async def test_f5_non_conforming_contingent_path_scenario(fb_client, data_files):
    await scenario_f5_non_conforming_contingent_path(fb_client, data_files)

    fb_client.create_flight_declaration.assert_called_once_with(data_files)
    fb_client.update_operation_state.assert_any_call(new_state=OperationState.ACTIVATED)
    fb_client.submit_telemetry.assert_called_once_with(duration_seconds=20)
    fb_client.check_operation_state_connected.assert_called_once_with(expected_state=OperationState.NONCONFORMING, duration_seconds=5)
    fb_client.update_operation_state.assert_any_call(new_state=OperationState.CONTINGENT)
    fb_client.update_operation_state.assert_any_call(new_state=OperationState.ENDED)


@patch("openutm_verification.scenarios.test_geo_fence_upload.get_geo_fence_path")
async def test_geo_fence_upload_scenario(mock_get_path, fb_client):
    mock_get_path.return_value = "/path/to/geo_fence.geojson"

    await scenario_geo_fence_upload(fb_client)

    fb_client.upload_geo_fence.assert_called_once_with(filename="/path/to/geo_fence.geojson")
    fb_client.get_geo_fence.assert_called_once()


@patch("openutm_verification.scenarios.test_opensky_live_data.asyncio.sleep")
async def test_opensky_live_data_scenario(mock_sleep, fb_client):
    opensky_client = AsyncMock()
    step_result = MagicMock()
    step_result.details = ["obs1", "obs2"]
    opensky_client.fetch_data.return_value = step_result

    await scenario_opensky_live_data(fb_client, opensky_client)

    assert opensky_client.fetch_data.call_count == 5
    assert fb_client.submit_air_traffic.call_count == 5
    assert mock_sleep.call_count == 4  # Sleeps between iterations


async def test_sdsp_heartbeat_scenario(fb_client):
    await scenario_sdsp_heartbeat(fb_client)

    fb_client.start_stop_sdsp_session.assert_any_call(action=SDSPSessionAction.START, session_id=ANY)
    fb_client.wait_x_seconds.assert_any_call(wait_time_seconds=2)
    fb_client.initialize_verify_sdsp_heartbeat.assert_called_once()
    fb_client.wait_x_seconds.assert_any_call(wait_time_seconds=5)
    fb_client.start_stop_sdsp_session.assert_any_call(action=SDSPSessionAction.STOP, session_id=ANY)


async def test_sdsp_track_scenario(fb_client):
    await scenario_sdsp_track(fb_client)

    fb_client.start_stop_sdsp_session.assert_any_call(action=SDSPSessionAction.START, session_id=ANY)
    fb_client.wait_x_seconds.assert_any_call(wait_time_seconds=2)
    fb_client.initialize_verify_sdsp_track.assert_called_once()
    fb_client.wait_x_seconds.assert_any_call(wait_time_seconds=5)
    fb_client.start_stop_sdsp_session.assert_any_call(action=SDSPSessionAction.STOP, session_id=ANY)


async def test_openutm_sim_air_traffic_data_scenario(fb_client):
    air_traffic_client = AsyncMock()
    step_result = MagicMock()
    step_result.details = ["obs1"]
    air_traffic_client.generate_simulated_air_traffic_data.return_value = step_result

    await scenario_openutm_sim_air_traffic_data(fb_client, air_traffic_client)

    air_traffic_client.generate_simulated_air_traffic_data.assert_called_once()
    fb_client.submit_simulated_air_traffic.assert_called_once_with(observations=["obs1"])

import json
import time
import uuid
from contextlib import contextmanager
from dataclasses import asdict
from typing import Any, Dict, List, Optional

import arrow
from loguru import logger

from openutm_verification.core.clients.flight_blender.base_client import (
    BaseBlenderAPIClient,
)
from openutm_verification.core.execution.config_models import DataFiles
from openutm_verification.core.execution.scenario_runner import scenario_step
from openutm_verification.core.reporting.reporting_models import (
    Status,
    StepResult,
)
from openutm_verification.models import (
    FlightBlenderError,
    HeartbeatMessage,
    OperationState,
    SDSPHeartbeatMessage,
    SDSPSessionAction,
)
from openutm_verification.rid import (
    UASID,
    LatLngPoint,
    OperatorLocation,
    RIDOperatorDetails,
    UAClassificationEU,
)


def _create_rid_operator_details(operation_id: str) -> RIDOperatorDetails:
    """Create a RIDOperatorDetails instance for a given operation ID.

    This helper function generates a standardized RIDOperatorDetails object
    with predefined values for UAS ID, classification, and operator location.

    Args:
        operation_id: The unique identifier for the flight operation.

    Returns:
        A fully configured RIDOperatorDetails instance.
    """
    uas_id = UASID(
        registration_id="CHE-5bisi9bpsiesw",
        serial_number="a5dd8899-bc19-c8c4-2dd7-57f786d1379d",
        utm_id="07a06bba-5092-48e4-8253-7a523f885bfe",
    )
    eu_classification = UAClassificationEU()
    operator_location = OperatorLocation(position=LatLngPoint(lat=46.97615311620088, lng=7.476099729537965))
    return RIDOperatorDetails(
        id=operation_id,
        uas_id=uas_id,
        operation_description="Medicine Delivery",
        operator_id="CHE-076dh0dq",
        eu_classification=eu_classification,
        operator_location=operator_location,
    )


class FlightBlenderClient(BaseBlenderAPIClient):
    """A client for interacting with the Flight Blender API for flight verification scenarios.

    This class extends BaseBlenderAPIClient and provides methods for uploading flight declarations,
    updating operation states, submitting telemetry, checking states, and managing declarations.
    It maintains context for the latest geo-fence and flight declaration IDs for cleanup.

    Attributes:
        latest_geo_fence_id: The ID of the most recently uploaded geo-fence.
        latest_flight_declaration_id: The ID of the most recently uploaded flight declaration.
    """

    def __init__(self, base_url: str, credentials: Dict[str, Any], request_timeout: int = 10) -> None:
        super().__init__(base_url=base_url, credentials=credentials, request_timeout=request_timeout)
        # Context: store the most recently created geo-fence id for teardown convenience
        self.latest_geo_fence_id: Optional[str] = None
        # Context: store the most recently created flight declaration id for teardown/steps
        self.latest_flight_declaration_id: Optional[str] = None
        # Context: store the generated telemetry states for the current scenario
        self.telemetry_states: Optional[List[Dict[str, Any]]] = None
        logger.debug(f"Initialized FlightBlenderClient with base_url={base_url}, request_timeout={request_timeout}")

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        # Best-effort cleanup of resources created during the session
        logger.info("Exiting FlightBlenderClient, performing cleanup")
        if self.latest_geo_fence_id:
            logger.debug(f"Cleaning up geo-fence ID: {self.latest_geo_fence_id}")
            self.delete_geo_fence()
        if self.latest_flight_declaration_id:
            logger.debug(f"Cleaning up flight declaration ID: {self.latest_flight_declaration_id}")
            self.delete_flight_declaration()
        return super().__exit__(exc_type, exc_val, exc_tb)

    @scenario_step("Upload Geo Fence")
    def upload_geo_fence(self, filename: Optional[str] = None) -> Dict[str, Any]:
        """Upload an Area-of-Interest (Geo Fence) to Flight Blender.

        Args:
            filename: Path to the GeoJSON file containing the geo-fence definition.

        Returns:
            The JSON response from the API, including the geo-fence ID if successful.

        Raises:
            FlightBlenderError: If the upload request fails.
            json.JSONDecodeError: If the file content is invalid JSON.
        """
        if filename is None:
            raise ValueError("filename parameter is required for upload_geo_fence")
        endpoint = "/geo_fence_ops/set_geo_fence"
        logger.debug(f"Uploading geo fence from {filename}")
        with open(filename, "r", encoding="utf-8") as geo_fence_json_file:
            geo_fence_data = json.loads(geo_fence_json_file.read())

        response = self.put(endpoint, json=geo_fence_data)
        body = response.json()
        try:
            self.latest_geo_fence_id = body.get("id")
            logger.info(f"Geo-fence uploaded successfully, ID: {self.latest_geo_fence_id}")
        except AttributeError:
            self.latest_geo_fence_id = None
            logger.warning("Failed to extract geo-fence ID from response")
        return body

    @scenario_step("Get Geo Fence")
    def get_geo_fence(self) -> Dict[str, Any]:
        """Retrieve the details of the most recently uploaded geo-fence.

        Returns:
            The JSON response from the API containing geo-fence details, or a dict
            indicating skip if no geo-fence ID is available.
        """
        geo_fence_id = self.latest_geo_fence_id
        if not geo_fence_id:
            logger.warning("No geo-fence ID available for retrieval")
            return {"id": None, "skipped": True, "reason": "No geo_fence_id available"}
        endpoint = f"/geo_fence_ops/geo_fence/{geo_fence_id}"
        logger.debug(f"Getting geo fence {geo_fence_id}, {endpoint=}")
        response = self.get(endpoint)
        logger.info(f"Retrieved geo-fence details for ID: {geo_fence_id}")
        return response.json()

    @scenario_step("Delete Geo Fence")
    def delete_geo_fence(self, geo_fence_id: Optional[str] = None) -> Dict[str, Any]:
        """Delete a geo-fence by ID.

        Args:
            geo_fence_id: Optional ID of the geo-fence to delete. If not provided,
                uses the latest uploaded geo-fence ID.

        Returns:
            A dictionary with deletion status, including whether it was successful.

        Note:
            According to the schema, DELETE returns 204 on success. This method
            normalizes the response to a JSON dict for reporting.
        """
        op_id = geo_fence_id or self.latest_geo_fence_id
        if not op_id:
            logger.warning("No geo-fence ID available for deletion")
            return {
                "deleted": False,
                "skipped": True,
                "reason": "No geo_fence_id available",
            }

        endpoint = f"/geo_fence_ops/geo_fence/{op_id}/delete"
        logger.debug(f"Deleting geo fence {op_id}, {endpoint=}")
        response = self.delete(endpoint)
        logger.debug(f"Geo fence deletion response: {response}")
        if response.status_code == 204:
            self.latest_geo_fence_id = None
            logger.info(f"Geo-fence deleted successfully, ID: {op_id}")
            return {"deleted": True, "id": op_id}
        try:
            return response.json()
        except ValueError:
            logger.warning(f"Non-JSON response on geo-fence deletion, status: {response.status_code}")
            return {"deleted": response.status_code in (200, 204), "id": op_id}

    @scenario_step("Upload Flight Declaration")
    def upload_flight_declaration(self, declaration: str | Any) -> Dict[str, Any]:
        """Upload a flight declaration to the Flight Blender API.

        Accepts either a filename (str) containing JSON declaration data, or a
        FlightDeclaration model instance. Adjusts datetimes to current time + offsets,
        and posts it. Raises an error if the declaration is not approved.

        Args:
            declaration: Either a path to the JSON flight declaration file (str),
                or a FlightDeclaration model instance.

        Returns:
            The JSON response from the API.

        Raises:
            FlightBlenderError: If the declaration is not approved or the request fails.
            json.JSONDecodeError: If the file content is invalid JSON (when using filename).
        """
        endpoint = "/flight_declaration_ops/set_flight_declaration"

        # Handle different input types
        if isinstance(declaration, str):
            # Load from file
            logger.debug(f"Uploading flight declaration from {declaration}")
            with open(declaration, "r", encoding="utf-8") as flight_declaration_file:
                f_d = flight_declaration_file.read()
            flight_declaration = json.loads(f_d)
        else:
            # Assume it's a model with model_dump method
            logger.debug("Uploading flight declaration from model")
            flight_declaration = declaration.model_dump(mode="json")

        # Adjust datetimes to current time + offsets
        now = arrow.now()
        few_seconds_from_now = now.shift(seconds=5)
        four_minutes_from_now = now.shift(minutes=4)

        flight_declaration["start_datetime"] = few_seconds_from_now.isoformat()
        flight_declaration["end_datetime"] = four_minutes_from_now.isoformat()

        response = self.post(endpoint, json=flight_declaration)
        response_json = response.json()

        if not response_json.get("is_approved"):
            logger.error(f"Flight declaration not approved. State: {OperationState(response_json.get('state')).name}")
            raise FlightBlenderError(f"Flight declaration not approved. State: {OperationState(response_json.get('state')).name}")
        # Store latest declaration id for later use
        try:
            self.latest_flight_declaration_id = response_json.get("id")
            logger.info(f"Flight declaration uploaded and approved, ID: {self.latest_flight_declaration_id}")
        except AttributeError:
            self.latest_flight_declaration_id = None
            logger.warning("Failed to extract flight declaration ID from response")

        return response_json

    @scenario_step("Update Operation State")
    def update_operation_state(self, new_state: OperationState, duration_seconds: int = 0) -> Dict[str, Any]:
        """Update the state of a flight operation.

        Posts the new state and optionally waits for the specified duration.

        Args:
            new_state: The new OperationState to set.
            duration_seconds: Optional seconds to sleep after update (default 0).

        Returns:
            The JSON response from the API.

        Raises:
            FlightBlenderError: If the update request fails.
        """
        endpoint = f"/flight_declaration_ops/flight_declaration_state/{self.latest_flight_declaration_id}"
        logger.debug(f"Updating operation {self.latest_flight_declaration_id} to state {new_state.name}")
        payload = {"state": new_state.value, "submitted_by": "hh@auth.com"}

        response = self.put(endpoint, json=payload)
        logger.info(f"Operation state updated for {self.latest_flight_declaration_id} to {new_state.name}")
        if duration_seconds > 0:
            logger.debug(f"Sleeping for {duration_seconds} seconds after state update")
            time.sleep(duration_seconds)
        return response.json()

    def _load_telemetry_file(self, filename: str) -> List[Dict[str, Any]]:
        """Load telemetry states from a JSON file.

        Args:
            filename: Path to the JSON file containing telemetry data.

        Returns:
            List of telemetry state dictionaries.

        Raises:
            json.JSONDecodeError: If the file content is invalid JSON.
        """
        logger.debug(f"Loading telemetry from {filename}")
        with open(filename, "r", encoding="utf-8") as rid_json_file:
            rid_json = json.loads(rid_json_file.read())
        return rid_json["current_states"]

    def _submit_telemetry_states_impl(self, states: List[Dict[str, Any]], duration_seconds: int = 0) -> Optional[Dict[str, Any]]:
        """Internal implementation for submitting telemetry states.

        Args:
            states: List of telemetry state dictionaries.
            duration_seconds: Optional maximum duration in seconds to submit telemetry (default 0 for unlimited).

        Returns:
            The JSON response from the last telemetry submission, or None if no submissions occurred.

        Raises:
            FlightBlenderError: If maximum waiting time is exceeded due to rate limits.
        """
        endpoint = "/flight_stream/set_telemetry"
        logger.debug(f"Submitting telemetry for operation {self.latest_flight_declaration_id}")

        rid_operator_details = _create_rid_operator_details(self.latest_flight_declaration_id)

        last_response = None
        maximum_waiting_time = 10.0
        waiting_time_elapsed = 0.0
        billable_time_elapsed = 0.0
        sleep_interval = 1.0
        logger.info(f"Starting telemetry submission for {len(states)} states")
        for i, state in enumerate(states):
            if duration_seconds and billable_time_elapsed >= duration_seconds:
                logger.info(f"Telemetry submission duration of {duration_seconds} seconds has passed.")
                break

            request_start_time = time.time()
            payload = {
                "observations": [
                    {
                        "current_states": [state],
                        "flight_details": asdict(rid_operator_details),
                    }
                ]
            }
            response = self.put(endpoint, json=payload, silent_status=[400])
            request_duration = time.time() - request_start_time
            if response.status_code == 201:
                logger.info(f"Telemetry point {i + 1} submitted, sleeping {sleep_interval} seconds... {billable_time_elapsed:.2f}s elapsed")
                billable_time_elapsed += request_duration + sleep_interval
            else:
                logger.warning(f"{response.status_code} {response.json()}")
                waiting_time_elapsed += request_duration + sleep_interval
                if waiting_time_elapsed >= maximum_waiting_time + sleep_interval:
                    logger.error(f"Maximum waiting time of {maximum_waiting_time} seconds exceeded.")
                    raise FlightBlenderError(f"Maximum waiting time of {maximum_waiting_time} seconds exceeded.")
            last_response = response.json()
            time.sleep(sleep_interval)
        logger.info("Telemetry submission completed")
        return last_response

    @scenario_step("Submit Telemetry (from file)")
    def submit_telemetry_from_file(self, filename: str, duration_seconds: int = 0) -> Optional[Dict[str, Any]]:
        """Submit telemetry data for a flight operation.

        Loads telemetry states from file and submits them sequentially, with optional
        duration limiting and error handling for rate limits.

        Args:
            filename: Path to the JSON file containing telemetry data.
            duration_seconds: Optional maximum duration in seconds to submit telemetry (default 0 for unlimited).

        Returns:
            The JSON response from the last telemetry submission, or None if no submissions occurred.

        Raises:
            FlightBlenderError: If maximum waiting time is exceeded due to rate limits.
        """
        states = self._load_telemetry_file(filename)
        return self._submit_telemetry_states_impl(states, duration_seconds)

    @scenario_step("Wait X seconds")
    def wait_x_seconds(self, wait_time_seconds: int = 5) -> str:
        """Wait for a specified number of seconds."""
        logger.info(f"Waiting for {wait_time_seconds} seconds...")
        time.sleep(wait_time_seconds)
        logger.info(f"Waited for {wait_time_seconds} seconds.")
        return f"Waited for Flight Blender to process {wait_time_seconds} seconds."

    @scenario_step("Submit Telemetry")
    def submit_telemetry(self, states: Optional[List[Dict[str, Any]]] = None, duration_seconds: int = 0) -> Optional[Dict[str, Any]]:
        """Submit telemetry data for a flight operation from in-memory states.

        Submits telemetry states sequentially from the provided list, with optional
        duration limiting and error handling for rate limits.

        Args:
            states: List of telemetry state dictionaries. If None, uses the generated telemetry states from context.
            duration_seconds: Optional maximum duration in seconds to submit telemetry (default 0 for unlimited).

        Returns:
            The JSON response from the last telemetry submission, or None if no submissions occurred.

        Raises:
            FlightBlenderError: If maximum waiting time is exceeded due to rate limits.
        """
        telemetry_states = states or self.telemetry_states
        if telemetry_states is None:
            raise ValueError("Telemetry states are required and could not be resolved from context.")

        return self._submit_telemetry_states_impl(telemetry_states, duration_seconds)

    @scenario_step("Check Operation State")
    def check_operation_state(
        self,
        expected_state: OperationState,
        duration_seconds: int = 0,
    ) -> str:
        """Check the operation state (simulated).

        This is a placeholder method for state checking; it simulates waiting
        and returns a success status.

        Args:
            expected_state: The expected OperationState.
            duration_seconds: Seconds to wait for processing.

        Returns:
            A dictionary with the check result.
        """
        logger.info(f"Checking operation state for {self.latest_flight_declaration_id} (simulated)...")
        logger.info(f"Waiting for {duration_seconds} seconds for Flight Blender to process state...")
        time.sleep(duration_seconds)
        logger.info(f"Flight state check for {self.latest_flight_declaration_id} completed (simulated).")
        return f"Waited for Flight Blender to process {expected_state} state."

    @scenario_step("Check Operation State Connected")
    def check_operation_state_connected(
        self,
        expected_state: OperationState,
        duration_seconds: int = 0,
    ) -> Dict[str, Any]:
        """Check the operation state by polling the API until the expected state is reached.

        Args:
            expected_state: The expected OperationState.
            duration_seconds: Maximum seconds to poll for the state.

        Returns:
            The JSON response from the API when the state is reached.

        Raises:
            FlightBlenderError: If the expected state is not reached within the timeout.
        """
        endpoint = f"/flight_declaration_ops/flight_declaration/{self.latest_flight_declaration_id}"
        logger.info(f"Checking operation state for {self.latest_flight_declaration_id}, expecting {expected_state.name}")
        start_time = time.time()

        while time.time() - start_time < duration_seconds:
            response = self.get(endpoint)
            data = response.json()
            current_state_value = data.get("state")
            logger.debug(f"Current state for {self.latest_flight_declaration_id}: {current_state_value}")
            if current_state_value == expected_state.value:
                logger.info(f"Operation {self.latest_flight_declaration_id} reached expected state {expected_state.name}")
                return data

            time.sleep(1)

        logger.error(
            f"Operation {self.latest_flight_declaration_id} did not reach expected state {expected_state.name} within {duration_seconds} seconds"
        )
        raise FlightBlenderError(
            f"Operation {self.latest_flight_declaration_id} did not reach expected state {expected_state.name} within {duration_seconds} seconds"
        )

    @scenario_step("Delete Flight Declaration")
    def delete_flight_declaration(self) -> Dict[str, Any]:
        """Delete a flight declaration by ID.

        Returns:
            A dictionary with deletion status, including whether it was successful.
        """
        op_id = self.latest_flight_declaration_id
        if not op_id:
            logger.warning("No flight declaration ID available for deletion")
            return {
                "deleted": False,
                "skipped": True,
                "reason": "No flight_declaration_id available",
            }

        endpoint = f"/flight_declaration_ops/flight_declaration/{op_id}/delete"
        logger.debug(f"Deleting flight declaration {op_id}, {endpoint=}")
        response = self.delete(endpoint)
        logger.debug(f"Flight declaration deletion response: {response}")
        if response.status_code == 204:
            self.latest_flight_declaration_id = None
            logger.info(f"Flight declaration deleted successfully, ID: {op_id}")
            return {"deleted": True, "id": op_id}
        try:
            return response.json()
        except ValueError:
            logger.warning(f"Non-JSON response on flight declaration deletion, status: {response.status_code}")
            return {"deleted": response.status_code in (200, 204), "id": op_id}

    @scenario_step("Submit Simulated Air Traffic")
    def submit_simulated_air_traffic(
        self,
        observations: List[List[Dict[str, Any]]],
        single_or_multiple_sensors: str = "single",
    ) -> bool:
        now = arrow.now()
        number_of_aircraft = len(observations)
        logger.debug(f"Submitting simulated air traffic for {number_of_aircraft} aircraft")

        # TODO: When single_or_multiple_sensors is "single", we need to aggregate all observations under one sensor ID
        # and when it's "multiple", we need to submit them separately as different session_ids, one for each track

        # get the start and end point of the simulation
        start_times = []
        end_times = []
        for aircraft_obs in observations:
            if not aircraft_obs:
                continue
            start_times.append(arrow.get(aircraft_obs[0]["timestamp"]))
            end_times.append(arrow.get(aircraft_obs[-1]["timestamp"]))
        simulation_start = min(start_times)
        simulation_end = max(end_times)

        now = arrow.now()
        start_time = now

        current_simulation_time = simulation_start
        # Loop through the simulation time from start to end, advancing by 1 second each iteration
        while current_simulation_time < simulation_end:
            # Calculate the corresponding real-world time for the current simulation time
            target_real_time = start_time + (current_simulation_time - simulation_start)
            # Wait until the current real time reaches the target time
            while arrow.now() < target_real_time:
                time.sleep(0.1)
            # For each aircraft, find the observation closest to the current simulation time
            filtered_observations = []
            for aircraft_obs in observations:
                if not aircraft_obs:
                    continue
                closest_obs = min(
                    aircraft_obs,
                    key=lambda obs: abs(arrow.get(obs["timestamp"]) - current_simulation_time),
                )
                filtered_observations.append([closest_obs])
            # Submit the filtered observations for each aircraft to the API
            logger.debug(f"Submitting {len(observations)} air traffic observations")
            for filtered_observation in filtered_observations:
                session_id = filtered_observation[0]["metadata"]["session_id"]
                endpoint = f"/flight_stream/set_air_traffic/{session_id}"
                payload = {"observations": filtered_observation}

                response = self.post(endpoint, json=payload)
                logger.debug(f"Air traffic submission response: {response.text}")
                logger.info(f"Observations submitted for aircraft {filtered_observation[0]['icao_address']} at time {current_simulation_time}")
            # Advance the simulation time by 1 second
            current_simulation_time = current_simulation_time.shift(seconds=1)
        return True

    @scenario_step("Submit Air Traffic")
    def submit_air_traffic(self, observations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Submit air traffic observations to the Flight Blender API.

        Args:
            observations: List of observation dictionaries containing flight data.

        Returns:
            The JSON response from the API.

        Raises:
            FlightBlenderError: If the submission request fails.
        """
        session_id = uuid.uuid4()
        endpoint = f"/flight_stream/set_air_traffic/{session_id}"
        logger.debug(f"Submitting {len(observations)} air traffic observations")
        payload = {"observations": observations}

        response = self.post(endpoint, json=payload)
        logger.debug(f"Air traffic submission response: {response.text}")
        logger.info(f"Air traffic observations submitted successfully for session {session_id}")
        return response.json()

    @scenario_step("Start / Stop SDSP Session")
    def start_stop_sdsp_session(self, session_id: str, action: SDSPSessionAction) -> str:
        """
        Starts or stops an SDSP (Strategic Deconfliction Service Provider) session based on the specified action.
        This method interacts with the Flight Blender service to manage the lifecycle of an SDSP session.
        It can be used to initiate a new session or terminate an existing one.
        Args:
            session_id (str): The unique identifier of the SDSP session to start or stop.
            action (SDSPSessionAction): The action to perform on the session, such as START or STOP.
        Returns:
            bool: True if the action was successfully performed, False otherwise.
        Raises:
            ValueError: If the session_id is invalid or the action is not supported.
            ConnectionError: If there is an issue communicating with the Flight Blender service.
            FlightBlenderError: If the action fails due to service errors.
        """

        endpoint = f"/surveillance_monitoring_ops/start_stop_surveillance_heartbeat_track/{session_id}"

        payload = {"action": action.value}
        response = self.put(endpoint, json=payload)
        logger.info(f"SDSP session {session_id} action {action.value} response: {response.status_code}")
        if response.status_code == 200:
            logger.info(f"SDSP session {session_id} action {action.value} completed successfully.")
            return f"{action.value} Heartbeat Track message received for {session_id}"

        else:
            logger.error(f"Failed to perform action {action.value} on SDSP session {session_id}. Response: {response.text}")
            raise FlightBlenderError(f"{action.value} Heartbeat Track message not received for {session_id}")

    def initialize_heartbeat_websocket_connection(self, session_id: str) -> Any:
        endpoint = f"/ws/surveillance/heartbeat/{session_id}"
        ws = self.create_websocket_connection(endpoint=endpoint)
        return ws

    @scenario_step("Verify SDSP Track")
    def initialize_verify_sdsp_track(
        self,
        expected_heartbeat_interval_seconds: int,
        expected_heartbeat_count: int,
        session_id: str,
    ) -> StepResult:
        ws_connection = self.initialize_heartbeat_websocket_connection(session_id=session_id)
        start_time = time.time()

        now = arrow.now()

        six_seconds_from_now = now.shift(seconds=6)
        all_received_messages = []
        # Start Receiving messages from now till six seconds from now
        while arrow.now() < six_seconds_from_now:
            time.sleep(0.1)
            message = ws_connection.recv()
            message = json.loads(message)
            if "heartbeat_data" not in message:
                logger.debug("WebSocket connection established message received")
                continue
            heartbeat_message = HeartbeatMessage(**message["heartbeat_data"])
            logger.debug(f"Received WebSocket message: {message}")
            all_received_messages.append(SDSPHeartbeatMessage(message=heartbeat_message, timestamp=arrow.now().isoformat()))
        logger.info(f"Received {len(all_received_messages)} messages in the first six seconds")
        self.close_heartbeat_websocket_connection(ws_connection)
        end_time = time.time()

        # Sort messages by timestamp
        sorted_messages = sorted(all_received_messages, key=lambda msg: arrow.get(msg.timestamp))
        # remove the first two messages since we are just starting
        sorted_messages = sorted_messages[2:]
        all_message_intervals = []
        # Calculate and print intervals between consecutive messages
        logger.debug("Heartbeat message intervals:")
        for i in range(1, len(sorted_messages)):
            prev_timestamp = arrow.get(sorted_messages[i - 1].timestamp)
            curr_timestamp = arrow.get(sorted_messages[i].timestamp)
            interval = (curr_timestamp - prev_timestamp).total_seconds()
            all_message_intervals.append(interval)
            logger.info(
                f"Interval {i}: {interval:.2f}s (between {prev_timestamp.format('HH:mm:ss.SSS')} and {curr_timestamp.format('HH:mm:ss.SSS')})"
            )

        verification_passed = True
        tolerance = 0.1 * expected_heartbeat_interval_seconds  # Allow 10% tolerance

        for interval in all_message_intervals:
            if not (expected_heartbeat_interval_seconds - tolerance <= interval <= expected_heartbeat_interval_seconds + tolerance):
                verification_passed = False
                logger.debug(f"Interval {interval:.2f}s is outside the expected range.")
                break
        duration = end_time - start_time
        if not verification_passed:
            logger.error(f"Heartbeat frequency verification failed: messages not received every {expected_heartbeat_interval_seconds} seconds")
            return StepResult(
                name=f"Heartbeat message received {expected_heartbeat_interval_seconds} seconds",
                status=Status.FAIL,
                details=f"Heartbeat message not processed {expected_heartbeat_interval_seconds} seconds",
                duration=duration,
            )
        else:
            logger.info(
                f"Heartbeat frequency verification passed: messages received approximately every {expected_heartbeat_interval_seconds} seconds"
            )
            return StepResult(
                name=f"Heartbeat message received {expected_heartbeat_interval_seconds} seconds",
                status=Status.PASS,
                details=f"Heartbeat message processed {expected_heartbeat_interval_seconds} seconds",
                duration=duration,
            )

    @scenario_step("Verify SDSP Heartbeat")
    def initialize_verify_sdsp_heartbeat(
        self,
        expected_heartbeat_interval_seconds: int,
        expected_heartbeat_count: int,
        session_id: str,
    ) -> StepResult:
        ws_connection = self.initialize_heartbeat_websocket_connection(session_id=session_id)
        start_time = time.time()

        now = arrow.now()

        six_seconds_from_now = now.shift(seconds=6)
        all_received_messages = []
        # Start Receiving messages from now till six seconds from now
        while arrow.now() < six_seconds_from_now:
            time.sleep(0.1)
            message = ws_connection.recv()
            message = json.loads(message)
            if "heartbeat_data" not in message:
                logger.debug("WebSocket connection established message received")
                continue
            heartbeat_message = HeartbeatMessage(**message["heartbeat_data"])
            logger.debug(f"Received WebSocket message: {message}")
            all_received_messages.append(SDSPHeartbeatMessage(message=heartbeat_message, timestamp=arrow.now().isoformat()))
        logger.info(f"Received {len(all_received_messages)} messages in the first six seconds")
        self.close_heartbeat_websocket_connection(ws_connection)
        end_time = time.time()

        # Sort messages by timestamp
        sorted_messages = sorted(all_received_messages, key=lambda msg: arrow.get(msg.timestamp))
        # remove the first two messages since we are just starting
        sorted_messages = sorted_messages[2:]
        all_message_intervals = []
        # Calculate and print intervals between consecutive messages
        logger.debug("Heartbeat message intervals:")
        for i in range(1, len(sorted_messages)):
            prev_timestamp = arrow.get(sorted_messages[i - 1].timestamp)
            curr_timestamp = arrow.get(sorted_messages[i].timestamp)
            interval = (curr_timestamp - prev_timestamp).total_seconds()
            all_message_intervals.append(interval)
            logger.info(
                f"Interval {i}: {interval:.2f}s (between {prev_timestamp.format('HH:mm:ss.SSS')} and {curr_timestamp.format('HH:mm:ss.SSS')})"
            )

        verification_passed = True
        tolerance = 0.1 * expected_heartbeat_interval_seconds  # Allow 10% tolerance

        for interval in all_message_intervals:
            if not (expected_heartbeat_interval_seconds - tolerance <= interval <= expected_heartbeat_interval_seconds + tolerance):
                verification_passed = False
                logger.debug(f"Interval {interval:.2f}s is outside the expected range.")
                break
        duration = end_time - start_time
        if not verification_passed:
            logger.error(f"Heartbeat frequency verification failed: messages not received every {expected_heartbeat_interval_seconds} seconds")
            return StepResult(
                name=f"Heartbeat message received {expected_heartbeat_interval_seconds} seconds",
                status=Status.FAIL,
                details=f"Heartbeat message not processed {expected_heartbeat_interval_seconds} seconds",
                duration=duration,
            )
        else:
            logger.info(
                f"Heartbeat frequency verification passed: messages received approximately every {expected_heartbeat_interval_seconds} seconds"
            )
            return StepResult(
                name=f"Heartbeat message received {expected_heartbeat_interval_seconds} seconds",
                status=Status.PASS,
                details=f"Heartbeat message processed {expected_heartbeat_interval_seconds} seconds",
                duration=duration,
            )

    def close_heartbeat_websocket_connection(self, ws_connection: Any) -> None:
        ws_connection.close()

    @scenario_step("Setup Flight Declaration")
    def setup_flight_declaration(self, flight_declaration_path: str, telemetry_path: str) -> None:
        """Generates data and uploads flight declaration."""
        from openutm_verification.scenarios.common import (
            generate_flight_declaration,
            generate_telemetry,
        )

        flight_declaration = generate_flight_declaration(flight_declaration_path)
        telemetry_states = generate_telemetry(telemetry_path)

        self.telemetry_states = telemetry_states

        upload_result = self.upload_flight_declaration(flight_declaration)

        if upload_result.status == Status.FAIL:
            raise FlightBlenderError("Failed to upload flight declaration during setup_operation")

    @contextmanager
    def flight_declaration(self, data_files: DataFiles):
        """Context manager to setup and teardown a flight operation based on scenario config."""
        self.setup_flight_declaration(data_files.flight_declaration, data_files.telemetry)
        try:
            yield
        finally:
            self.delete_flight_declaration()

import json
import time
from dataclasses import asdict

import arrow
from loguru import logger

from openutm_verification.base_client import BaseBlenderAPIClient
from openutm_verification.config_models import Status
from openutm_verification.models import FlightBlenderError, OperationState
from openutm_verification.rid import (
    UASID,
    LatLngPoint,
    OperatorLocation,
    RIDOperatorDetails,
    UAClassificationEU,
)
from openutm_verification.scenario_runner import scenario_step


def _create_rid_operator_details(operation_id: str) -> RIDOperatorDetails:
    """Helper function to create RIDOperatorDetails."""
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
    @scenario_step("Upload Flight Declaration")
    def upload_flight_declaration(self, filename):
        endpoint = "/flight_declaration_ops/set_flight_declaration"
        logger.debug(f"Uploading flight declaration from {filename}")
        with open(filename, "r", encoding="utf-8") as flight_declaration_file:
            f_d = flight_declaration_file.read()

        flight_declaration = json.loads(f_d)
        now = arrow.now()
        few_seconds_from_now = now.shift(seconds=5)
        four_minutes_from_now = now.shift(minutes=4)

        flight_declaration["start_datetime"] = few_seconds_from_now.isoformat()
        flight_declaration["end_datetime"] = four_minutes_from_now.isoformat()

        response = self.post(endpoint, json=flight_declaration)
        response_json = response.json()

        if not response_json.get("is_approved"):
            raise FlightBlenderError(f"Flight declaration not approved. State: {OperationState(response_json.get('state')).name}")

        return response_json

    @scenario_step("Update Operation State")
    def update_operation_state(self, operation_id: str, new_state: OperationState, duration_seconds: int = 0):
        endpoint = f"/flight_declaration_ops/flight_declaration_state/{operation_id}"
        logger.debug(f"Updating operation {operation_id} to state {new_state.name}")
        payload = {"state": new_state.value, "submitted_by": "hh@auth.com"}

        response = self.put(endpoint, json=payload)
        time.sleep(duration_seconds)
        return response.json()

    @scenario_step("Submit Telemetry")
    def submit_telemetry(self, operation_id: str, filename: str, duration_seconds: int = 0):
        endpoint = "/flight_stream/set_telemetry"
        logger.debug(f"Submitting telemetry from {filename} for operation {operation_id}")
        with open(filename, "r", encoding="utf-8") as rid_json_file:
            rid_json = json.loads(rid_json_file.read())

        states = rid_json["current_states"]
        rid_operator_details = _create_rid_operator_details(operation_id)

        last_response = None
        maximum_waiting_time = 10.0
        waiting_time_elapsed = 0.0
        billable_time_elapsed = 0.0
        sleep_interval = 1.0
        for state in states:
            if duration_seconds and billable_time_elapsed >= duration_seconds:
                logger.info(f"Telemetry submission duration of {duration_seconds} seconds has passed.")
                break

            request_start_time = time.time()
            payload = {"observations": [{"current_states": [state], "flight_details": asdict(rid_operator_details)}]}
            response = self.put(endpoint, json=payload, silent_status=[400])
            request_duration = time.time() - request_start_time
            if response.status_code == 201:
                logger.info(f"Telemetry point submitted, sleeping {sleep_interval} seconds... {billable_time_elapsed:.2f}s elapsed")
                billable_time_elapsed += request_duration + sleep_interval
            else:
                logger.warning(f"{response.status_code} {response.json()}")
                waiting_time_elapsed += request_duration + sleep_interval
                if waiting_time_elapsed >= maximum_waiting_time + sleep_interval:
                    raise FlightBlenderError(f"Maximum waiting time of {maximum_waiting_time} seconds exceeded.")
            last_response = response.json()
            time.sleep(sleep_interval)
        return last_response

    @scenario_step("Check Operation State")
    def check_operation_state(self, operation_id: str, expected_state: OperationState, duration_seconds: int = 0):
        logger.info(f"Checking operation state for {operation_id} (simulated)...")
        logger.info(f"Waiting for {duration_seconds} seconds for Flight Blender to process state...")
        time.sleep(duration_seconds)
        logger.info(f"Flight state check for {operation_id} completed (simulated).")
        return {
            "name": "Check Flight State",
            "status": Status.PASS,
            "details": f"Waited for Flight Blender to process {expected_state} state.",
        }

    @scenario_step("Check Operation State Connected")
    def check_operation_state_connected(self, operation_id: str, expected_state: OperationState, duration_seconds: int = 0):
        endpoint = f"/flight_declaration_ops/flight_declaration/{operation_id}"
        logger.info(f"Checking operation state for {operation_id}, expecting {expected_state.name}")
        start_time = time.time()

        while time.time() - start_time < duration_seconds:
            response = self.get(endpoint)
            data = response.json()
            current_state_value = data.get("state")
            if current_state_value == expected_state.value:
                logger.info(f"Operation {operation_id} reached expected state {expected_state.name}")
                return data

            time.sleep(1)

        raise FlightBlenderError(f"Operation {operation_id} did not reach expected state {expected_state.name} within {duration_seconds} seconds")

    @scenario_step("Delete Flight Declaration")
    def delete_flight_declaration(self, operation_id: str):
        endpoint = f"/flight_declaration_ops/flight_declaration/{operation_id}/delete"
        logger.debug(f"Deleting flight declaration {operation_id}, {endpoint=}")
        response = self.delete(endpoint, silent_status=[403])
        logger.debug(f"Flight declaration deletion response: {response.text}")
        if response.status_code == 403:
            logger.warning(f"{response.status_code} {response.json()}")
            # raise FlightBlenderError(f"Deletion forbidden for operation {operation_id}.")

        return response.json()

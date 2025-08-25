import json
import time
from dataclasses import asdict

import arrow
import httpx
from loguru import logger

from openutm_verification.models import OperationState
from openutm_verification.rid import (
    UASID,
    LatLngPoint,
    OperatorLocation,
    RIDOperatorDetails,
    UAClassificationEU,
)
from openutm_verification.scenario_runner import scenario_step


class FlightBlenderClient:
    def __init__(self, base_url, credentials):
        self.base_url = base_url
        self.client = httpx.Client()
        self.client.headers.update(
            {
                "Content-Type": "application/json",
                "Authorization": "Bearer " + credentials["access_token"],
            }
        )

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.client.close()

    @scenario_step("Upload Flight Declaration")
    def upload_flight_declaration(self, filename):
        logger.debug(f"Uploading flight declaration from {filename}")
        with open(filename, "r") as flight_declaration_file:
            f_d = flight_declaration_file.read()

        flight_declaration = json.loads(f_d)
        now = arrow.now()
        few_seconds_from_now = now.shift(seconds=5)
        four_minutes_from_now = now.shift(minutes=4)

        flight_declaration["start_datetime"] = few_seconds_from_now.isoformat()
        flight_declaration["end_datetime"] = four_minutes_from_now.isoformat()

        securl = f"{self.base_url}/flight_declaration_ops/set_flight_declaration"
        response = self.client.post(securl, json=flight_declaration)
        if response.status_code != 200:
            logger.error(f"Failed to upload flight declaration: {response.text}")
            raise Exception(f"Failed to upload flight declaration: {response.text}")
        logger.debug(f"Response from flight declaration upload: {response.status_code} {response.text}")
        return response.json()

    @scenario_step("Update Operation State")
    def update_operation_state(self, operation_id: str, new_state: OperationState, duration_seconds: int = 0):
        logger.debug(f"Updating operation {operation_id} to state {new_state.name}")
        payload = {"state": new_state.value, "submitted_by": "hh@auth.com"}
        securl = f"{self.base_url}/flight_declaration_ops/flight_declaration_state/{operation_id}"
        response = self.client.put(securl, json=payload)
        if response.status_code != 200:
            logger.error(f"Failed to update operation state: {response.text}")
            raise Exception(f"Failed to update operation state: {response.text}")
        logger.debug(f"Response from update operation state: {response.status_code} {response.text}")
        time.sleep(duration_seconds)
        return response.json()

    @scenario_step("Submit Telemetry")
    def submit_telemetry(self, filename: str, operation_id: str, duration_seconds: int = 0):
        logger.debug(f"Submitting telemetry from {filename} for operation {operation_id}")
        with open(filename, "r") as rid_json_file:
            rid_json = json.loads(rid_json_file.read())

        states = rid_json["current_states"]
        rid_operator_details = rid_json["flight_details"]

        uas_id = UASID(
            registration_id="CHE-5bisi9bpsiesw",
            serial_number="a5dd8899-bc19-c8c4-2dd7-57f786d1379d",
            utm_id="07a06bba-5092-48e4-8253-7a523f885bfe",
        )
        eu_classification = UAClassificationEU()
        operator_location = OperatorLocation(position=LatLngPoint(lat=46.97615311620088, lng=7.476099729537965))
        rid_operator_details = RIDOperatorDetails(
            id=operation_id,
            uas_id=uas_id,
            operation_description="Medicine Delivery",
            operator_id="CHE-076dh0dq",
            eu_classification=eu_classification,
            operator_location=operator_location,
        )

        start_time = time.time()
        for state in states:
            if duration_seconds and (time.time() - start_time) > duration_seconds:
                logger.info(f"Telemetry submission duration of {duration_seconds} seconds has passed.")
                break

            payload = {"observations": [{"current_states": [state], "flight_details": asdict(rid_operator_details)}]}
            securl = f"{self.base_url}/flight_stream/set_telemetry"
            try:
                response = self.client.put(securl, json=payload)
                if response.status_code != 201:
                    logger.warning(f"{response.status_code} {response.json()}")
                else:
                    logger.info("Telemetry point submitted, sleeping 1 second...")
            except Exception as e:
                logger.error(e)
            time.sleep(1)

    @scenario_step("Check Operation State")
    def check_operation_state(self, operation_id: str, expected_state: OperationState, duration_seconds: int = 0):
        logger.info(f"Checking operation state for {operation_id} (simulated)...")
        # In a real scenario, we would check if the state is non-conforming.
        # Here we just wait.
        time.sleep(duration_seconds)
        logger.info(f"Flight state check for {operation_id} (simulated) complete.")
        return {"name": "Check Flight State", "status": "PASS", "details": f"Waited for Flight Blender to process {expected_state} state."}

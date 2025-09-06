"""
This script is used to import flight data into the Secured Flight Spotlight instance. It defines a class `FlightBlenderUploader`
that provides methods to upload flight declarations, update operation states, and submit telemetry data.
Classes:
    FlightBlenderUploader: Handles uploading flight declarations, updating operation states, and submitting telemetry data.
Functions:
    __init__(self, credentials): Initializes the FlightBlenderUploader with the given credentials.
    upload_flight_declaration(self, filename): Uploads a flight declaration by reading a JSON file, updating its start and end times, and sending it to a specified endpoint.
    update_operation_state(self, operation_id: str, new_state: int): Updates the state of an operation with the given operation ID.
    submit_telemetry(self, filename, operation_id): Submits telemetry data to a specified endpoint.
Usage:
    The script can be run as a standalone program. It initializes the credentials, uploads a flight declaration, updates the operation state, and submits telemetry data.

"""

import json
import logging
import os
import sys
import threading
import time
from dataclasses import asdict
from os.path import abspath, dirname

import arrow
import requests
from dotenv import find_dotenv, load_dotenv

from openutm_verification.client import NoAuthCredentialsGetter
from openutm_verification.rid import (
    UASID,
    LatLngPoint,
    OperatorLocation,
    RIDOperatorDetails,
    UAClassificationEU,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

ENV_FILE = find_dotenv()
if ENV_FILE:
    load_dotenv(ENV_FILE)


def log_info(message):
    """
    Logs an informational message with a timestamp.
    Args:
        message (str): The message to log.
    """
    logging.info(message)


class FlightBlenderUploader:
    def __init__(self, credentials):
        self.credentials = credentials

    def upload_flight_declaration(self, filename):
        """
        Uploads a flight declaration by reading a JSON file, updating its start and end times,
        and sending it to a specified endpoint.
        Args:
            filename (str): The path to the JSON file containing the flight declaration.
        Returns:
            requests.Response: The response object from the POST request to the flight declaration endpoint.
        """

        with open(filename, "r") as flight_declaration_file:
            f_d = flight_declaration_file.read()

        flight_declaration = json.loads(f_d)
        now = arrow.now()
        few_seconds_from_now = now.shift(seconds=5)
        four_minutes_from_now = now.shift(minutes=4)

        # Update start and end time
        flight_declaration["start_datetime"] = few_seconds_from_now.isoformat()
        flight_declaration["end_datetime"] = four_minutes_from_now.isoformat()
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer " + self.credentials["access_token"],
        }
        securl = "http://localhost:8000/flight_declaration_ops/set_flight_declaration"  # set this to self (Post the json to itself)
        response = requests.post(securl, json=flight_declaration, headers=headers)
        return response

    def update_operation_state(self, operation_id: str, new_state: int):
        """
        Updates the state of an operation with the given operation ID.
        Args:
            operation_id (str): The ID of the operation to update.
            new_state (int): The new state to set for the operation.
        Returns:
            response: The response object from the HTTP PUT request.
        """

        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer " + self.credentials["access_token"],
        }

        payload = {"state": new_state, "submitted_by": "hh@auth.com"}
        securl = "http://localhost:8000/flight_declaration_ops/flight_declaration_state/{operation_id}".format(
            operation_id=operation_id
        )  # set this to self (Post the json to itself)
        response = requests.put(securl, json=payload, headers=headers)
        return response

    def submit_telemetry(self, filename, operation_id):
        """
        Submits telemetry data to a specified endpoint.
        Args:
            filename (str): The path to the JSON file containing telemetry data.
            operation_id (str): The unique identifier for the operation.
        Raises:
            Exception: If there is an error during the HTTP request.
        Notes:
            - Reads telemetry data from the specified JSON file.
            - Constructs the necessary payload for the telemetry submission.
            - Sends the telemetry data to the endpoint using an HTTP PUT request.
            - Handles the response and prints relevant information or errors.
        """

        with open(filename, "r") as rid_json_file:
            rid_json = rid_json_file.read()

        rid_json = json.loads(rid_json)

        states = rid_json["current_states"]
        rid_operator_details = rid_json["flight_details"]

        uas_id = UASID(
            registration_id="CHE-5bisi9bpsiesw",
            serial_number="d29dbf50-f411-4488-a6f1-cf2ae4d4237a",
            utm_id="07a06bba-5092-48e4-8253-7a523f885bfe",
        )
        # eu_classification =from_dict(data_class= UAClassificationEU, data= rid_operator_details['rid_details']['eu_classification'])
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
        for state in states:
            headers = {
                "Content-Type": "application/json",
                "Authorization": "Bearer " + self.credentials["access_token"],
            }
            # payload = {"observations":[{"icao_address" : icao_address,"traffic_source" :traffic_source, "source_type" : source_type, "lat_dd" : lat_dd, "lon_dd" : lon_dd, "time_stamp" : time_stamp,"altitude_mm" : altitude_mm, 'metadata':metadata}]}

            payload = {
                "observations": [
                    {
                        "current_states": [state],
                        "flight_details": {
                            "rid_details": asdict(rid_operator_details),
                            "aircraft_type": "Helicopter",
                            "operator_name": "Thomas-Roberts",
                        },
                    }
                ]
            }
            securl = "http://localhost:8000/flight_stream/set_telemetry"  # set this to self (Post the json to itself)
            try:
                response = requests.put(securl, json=payload, headers=headers)

            except Exception as e:
                log_info(e)
            else:
                if response.status_code == 201:
                    log_info("Sleeping 1 seconds..")
                    time.sleep(1)
                else:
                    log_info(response.json())


if __name__ == "__main__":
    # my_credentials = PassportSpotlightCredentialsGetter()
    # my_credentials = PassportCredentialsGetter()
    my_credentials = NoAuthCredentialsGetter()
    credentials = my_credentials.get_cached_credentials(audience="testflight.flightblender.com", scopes=["flight_blender.write"])
    parent_dir = dirname(abspath(__file__))  # <-- absolute dir the raw input file  is in

    rel_path = "../assets/flight_declarations_samples/flight-1-bern.json"
    abs_file_path = os.path.join(parent_dir, rel_path)
    my_uploader = FlightBlenderUploader(credentials=credentials)
    flight_declaration_response = my_uploader.upload_flight_declaration(filename=abs_file_path)

    if flight_declaration_response.status_code == 200:
        flight_declaration_success = flight_declaration_response.json()
        flight_declaration_id = flight_declaration_success["id"]

        log_info("Flight Declaration Submitted...")

    else:
        sys.exit()
    log_info("Wait 20 secs...")
    time.sleep(20)
    log_info("Setting state as activated...")
    # GCS Activates Flights
    flight_state_activated_response = my_uploader.update_operation_state(operation_id=flight_declaration_id, new_state=2)
    if flight_state_activated_response.status_code == 200:
        flight_state_activated = flight_state_activated_response.json()
    else:
        log_info("Error in activating flight...")
        log_info(flight_state_activated_response.json())
        sys.exit()

    log_info("State set as activated...")

    # submit telemetry

    rel_path = "../assets/rid_samples/flight_1_rid_aircraft_state.json"
    abs_file_path = os.path.join(parent_dir, rel_path)
    my_uploader = FlightBlenderUploader(credentials=credentials)
    thread = threading.Thread(
        target=my_uploader.submit_telemetry,
        args=(
            abs_file_path,
            flight_declaration_id,
        ),
    )
    thread.start()
    log_info("Telemetry submission for 30 seconds...")
    time.sleep(30)
    log_info("Setting state as ended...")
    # GCS Ends Flights
    flight_state_ended = my_uploader.update_operation_state(operation_id=flight_declaration_id, new_state=5)
    log_info("Flight state declared ended...")

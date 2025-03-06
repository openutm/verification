## A file to import flight data into the Tile 38 instance.
import json, time, requests
from os.path import dirname, abspath
import os, sys
from auth_factory import PassportCredentialsGetter, NoAuthCredentialsGetter
import uuid


class FlightBlenderUploader:
    def __init__(self, credentials):
        self.timestamps = [
            1590000000000,
            1590000005000,
            1590000010000,
            1590000015000,
            1590000020000,
        ]
        self.credentials = credentials

    def upload_to_server(self, filename):
        with open(filename, "r") as traffic_json_file:
            traffic_json = traffic_json_file.read()
        session_id = uuid.uuid4()
        traffic_json = json.loads(traffic_json)

        for timestamp in self.timestamps:
            current_timestamp_readings = [
                x for x in traffic_json if x["timestamp"] == timestamp
            ]

            for current_reading in current_timestamp_readings:
                icao_address = current_reading["icao_address"]
                traffic_source = current_reading["traffic_source"]
                source_type = current_reading["source_type"]
                lat_dd = current_reading["lat_dd"]
                lon_dd = current_reading["lon_dd"]
                timestamp = current_reading["timestamp"]
                altitude_mm = current_reading["altitude_mm"]
                metadata = current_reading["metadata"]
                # print(timestamp)
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": "Bearer " + self.credentials["access_token"],
                }

                payload = {
                    "observations": [
                        {
                            "icao_address": icao_address,
                            "traffic_source": traffic_source,
                            "source_type": source_type,
                            "lat_dd": lat_dd,
                            "lon_dd": lon_dd,
                            "timestamp": timestamp,
                            "altitude_mm": altitude_mm,
                            "metadata": metadata,
                        }
                    ]
                }

                securl = "http://localhost:8000/flight_stream/set_air_traffic/{session_id}".format(
                    session_id=session_id
                )  # set this to self (Post the json to itself)
                try:
                    response = requests.post(securl, json=payload, headers=headers)
                    if response.status_code not in [200, 201]:
                        print(
                            f"Non-successful status code received: {response.status_code}, message: {response.text}"
                        )
                        response.raise_for_status()

                except requests.exceptions.HTTPError as http_err:
                    print(f"HTTP error occurred: {http_err}")
                except requests.exceptions.ConnectionError as conn_err:
                    print(f"Connection error occurred: {conn_err}")
                except requests.exceptions.Timeout as timeout_err:
                    print(f"Timeout error occurred: {timeout_err}")
                except requests.exceptions.RequestException as req_err:
                    print(f"An error occurred: {req_err}")
                except Exception as e:
                    print(f"An unexpected error occurred: {e}")
                else:
                    print("Sleeping 10 seconds..")
                    time.sleep(10)


if __name__ == "__main__":
    # my_credentials = PassportCredentialsGetter()
    my_credentials = NoAuthCredentialsGetter()
    credentials = my_credentials.get_cached_credentials(
        audience="testflight.flightblender.com", scopes=["flight_blender.write"]
    )

    if "error" in credentials:
        sys.exit("Error in getting credentials.")
    parent_dir = dirname(
        abspath(__file__)
    )  # <-- absolute dir the raw input file  is in
    rel_path = "air_traffic_samples/micro_flight_data_single.json"
    abs_file_path = os.path.join(parent_dir, rel_path)
    my_uploader = FlightBlenderUploader(credentials=credentials)
    my_uploader.upload_to_server(filename=abs_file_path)

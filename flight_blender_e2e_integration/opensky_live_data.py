import os
import requests
from typing import Optional
import pandas as pd
import logging
from auth_factory import PassportCredentialsGetter, NoAuthCredentialsGetter
from dataclasses import dataclass
import time

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


@dataclass
class SingleObservation:
    """This is the object stores details of the observation"""

    timestamp: int
    lat_dd: float
    lon_dd: float
    altitude_mm: float
    traffic_source: int
    source_type: int
    icao_address: str
    metadata: Optional[dict]


if __name__ == "__main__":
    # my_credentials = PassportCredentialsGetter()
    my_credentials = NoAuthCredentialsGetter()
    credentials = my_credentials.get_cached_credentials(
        audience="testflight.flightblender.com", scopes=["flight_blender.write"]
    )

    username = os.environ.get("OPENSKY_NETWORK_USERNAME")
    password = os.environ.get("OPENSKY_NETWORK_PASSWORD")

    # bbox = (min latitude, max latitude, min longitude, max longitude)

    view_port = (45.8389, 47.8229, 5.9962, 10.5226)
    lat_min = min(view_port[0], view_port[2])
    lat_max = max(view_port[0], view_port[2])
    lng_min = min(view_port[1], view_port[3])
    lng_max = max(view_port[1], view_port[3])

    url_data = (
        "https://opensky-network.org/api/states/all?"
        + "lamin="
        + str(lat_min)
        + "&lomin="
        + str(lng_min)
        + "&lamax="
        + str(lat_max)
        + "&lomax="
        + str(lng_max)
    )

    # LOAD TO PANDAS DATAFRAME
    col_name = [
        "icao24",
        "callsign",
        "origin_country",
        "time_position",
        "last_contact",
        "long",
        "lat",
        "baro_altitude",
        "on_ground",
        "velocity",
        "true_track",
        "vertical_rate",
        "sensors",
        "geo_altitude",
        "squawk",
        "spi",
        "position_source",
    ]
    end_time = time.time() + 30
    while time.time() < end_time:
        loops_left = int((end_time - time.time()) // 3)
        logger.info(f"Starting data fetch loop, {loops_left} loops left.")
        response = requests.get(url_data, auth=(username, password)).json()

        if response.get("states") is None:
            logger.error("No states data found in the response")
            exit(1)
        flight_df = pd.DataFrame(response["states"], columns=col_name)
        flight_df = flight_df.fillna("No Data")

        all_observations = []
        for index, row in flight_df.iterrows():
            metadata = {"velocity": row["velocity"]}
            altitude = 0.0 if row["baro_altitude"] == "No Data" else row["baro_altitude"]
            observation = SingleObservation(
                timestamp=row["time_position"],
                icao_address=row["icao24"],
                traffic_source=2,
                source_type=1,
                lat_dd=row["lat"],
                lon_dd=row["long"],
                altitude_mm=altitude,
                metadata=metadata,
            )
            all_observations.append(observation.__dict__)
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer " + credentials["access_token"],
        }

        altitudes = [obs["altitude_mm"] for obs in all_observations]

        payload = {"observations": all_observations}
        securl = "http://localhost:8000/flight_stream/set_air_traffic"  # set this to self (Post the json to itself)

        response = requests.post(securl, json=payload, headers=headers)
        logger.info(f"Server response: {response.json()}")

        time.sleep(3)

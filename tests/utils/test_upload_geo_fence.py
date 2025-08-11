## A file to import flight data into the Secured Flight Spotlight instance.
import requests
from dotenv import load_dotenv, find_dotenv
import json
from os import environ as env
from os.path import dirname, abspath
import geojson
import sys
from geojson import Polygon

from openutm_verification.client import (
    NoAuthCredentialsGetter,
)

ENV_FILE = find_dotenv()
if ENV_FILE:
    load_dotenv(ENV_FILE)


class FlightBlenderUploader:
    def __init__(self, credentials):
        self.credentials = credentials

    def upload_to_server(self, filename):
        with open(filename, "r") as geo_fence_json_file:
            geo_fence_json = geo_fence_json_file.read()

        geo_fence_data = json.loads(geo_fence_json)

        headers = {
            "Authorization": "Bearer " + self.credentials["access_token"],
            "Content-Type": "application/json",
        }

        securl = "http://localhost:8000/geo_fence_ops/set_geo_fence"
        try:
            response = requests.put(securl, data=json.dumps(geo_fence_data), headers=headers)
            print(response.content)
        except Exception as e:
            print(e)
        else:
            print("Uploaded Geo Fence")


if __name__ == "__main__":
    # my_credentials = PassportSpotlightCredentialsGetter()\

    my_credentials = NoAuthCredentialsGetter()
    credentials = my_credentials.get_cached_credentials(
        audience="testflight.flightblender.com", scopes=["flight_blender.write"]
    )

    if "error" in credentials:
        sys.exit("Error in getting credentials.")
    parent_dir = dirname(
        abspath(__file__)
    )  # <-- absolute dir the raw input file  is in

    my_uploader = FlightBlenderUploader(credentials=credentials)
    my_uploader.upload_to_server(filename="aoi_geo_fence_samples/geo_fence.geojson")

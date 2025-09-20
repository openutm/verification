import json
import os
from dataclasses import dataclass
from shapely.geometry import box
import arrow


@dataclass
class FlightDeclarationBounds:
    min_x: float
    max_x: float
    min_y: float
    max_y: float


class FlightDeclarationGenerator:
    def __init__(
        self,
        flight_declaration_bounds: FlightDeclarationBounds = FlightDeclarationBounds(
            min_x=7.4719589491516558,
            max_x=7.4870457729811619,
            min_y=46.9799127188803993,
            max_y=46.9865389634242945,
        ),
    ):
        # current_dir = os.path.dirname(os.path.abspath(__file__))
        template_path = os.path.join(
            "..",
            "assets",
            "simulator_templates",
            "flight_declaration_template.json",
        )
        template_path = os.path.abspath(template_path)

        # Load the JSON template
        with open(template_path, "r") as f:
            flight_declaration_template = json.load(f)

        self.template = flight_declaration_template
        self.bounds = flight_declaration_bounds

    def generate(self, **kwargs):
        # build a bounding box for the flight declaration
        bbox = box(
            self.bounds.min_x, self.bounds.min_y, self.bounds.max_x, self.bounds.max_y
        )
        # write the bos as a geojson feature collection
        geojson_bbox = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [list(bbox.exterior.coords)],
                    },
                    "properties": {},
                }
            ],
        }
        # update the start and end time of the flight
        now = arrow.now()
        few_seconds_from_now = now.shift(seconds=5)
        four_minutes_from_now = now.shift(minutes=4)

        flight_declaration = self.template.copy()
        # Update start and end time
        flight_declaration["start_datetime"] = few_seconds_from_now.isoformat()
        flight_declaration["end_datetime"] = four_minutes_from_now.isoformat()
        flight_declaration["flight_declaration_geo_json"] = geojson_bbox
        return flight_declaration


if __name__ == "__main__":  # Define the path to the template file
    generator = FlightDeclarationGenerator()
    sample_declaration = generator.generate(
        flight_id="FL123",
        operator_id="OP456",
        departure_time="2024-01-01T10:00:00Z",
        arrival_time="2024-01-01T10:30:00Z",
        origin="POINT(1.0 2.0)",
        destination="POINT(3.0 4.0)",
    )
    print(json.dumps(sample_declaration, indent=2))

from dataclasses import dataclass
from geojson import Point
@dataclass
class GeoJSONFlightPoints: 
    bounds: tuple[float, float, float, float]
    flight_path_points: list[Point]
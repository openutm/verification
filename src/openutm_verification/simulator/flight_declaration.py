from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final

import arrow
from loguru import logger
from shapely.geometry import Polygon

from openutm_verification.simulator.models.declaration_models import (
    BaseUpdates,
    Feature,
    FeatureCollection,
    FlightDeclaration,
    FlightDeclarationBounds,
    FlightDeclarationOverrides,
    PolygonGeometry,
)

START_TIME_OFFSET_S = 5  # Seconds from now for flight start
END_TIME_OFFSET_S = 4 * 60  # Seconds from now for flight end

DEFAULT_TEMPLATE_PATH: Final[Path] = Path(__file__).resolve().parent.parent / "assets" / "simulator_templates" / "flight_declaration_template.json"
BOUNDS_FILE_PATH: Final[Path] = Path(__file__).resolve().parents[3] / "config" / "bern" / "flight_declaration.json"


class FlightDeclarationGenerator:
    """Simplified generator for flight declarations."""

    def __init__(
        self,
        *,
        template_path: Path = DEFAULT_TEMPLATE_PATH,
        bounds_path: Path = BOUNDS_FILE_PATH,
    ):
        self.bounds = self._load_bounds(bounds_path)
        self.template = self._load_template(template_path)

    @staticmethod
    def _validate_template_path(template_path: Path) -> Path:
        if not template_path.is_file():
            raise FileNotFoundError(f"Template not found: {template_path}")
        return template_path

    def _load_template(self, template_path: Path) -> dict[str, Any]:
        """Load template as raw dict."""
        path = self._validate_template_path(template_path)
        logger.debug(f"Loading flight declaration template from {path}")
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def _load_bounds(self, bounds_path: Path) -> FlightDeclarationBounds:
        """Load bounds from sample file."""
        logger.debug(f"Loading flight declaration bounds from {bounds_path}")
        with bounds_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return FlightDeclarationBounds(
            min_x=data["minx"],
            max_x=data["maxx"],
            min_y=data["miny"],
            max_y=data["maxy"],
        )

    @staticmethod
    def _normalize_coordinates(polygon: Polygon) -> list[list[tuple[float, float]]]:
        coords = [[(float(x), float(y)) for x, y in polygon.exterior.coords]]
        for interior in polygon.interiors:
            coords.append([(float(x), float(y)) for x, y in interior.coords])
        return coords

    def _build_geojson_bbox(self, bbox: Polygon) -> FeatureCollection:
        coordinates = self._normalize_coordinates(bbox)
        geometry = PolygonGeometry(coordinates=coordinates)
        # TODO: verify if this should be somewhere else
        # Add required properties for Flight Blender API
        properties = {"min_altitude": {"meters": 50, "datum": "w84"}, "max_altitude": {"meters": 120, "datum": "w84"}}
        feature = Feature(geometry=geometry, properties=properties)
        return FeatureCollection(features=[feature])

    def generate(self) -> FlightDeclaration:
        """Generate validated flight declaration as pydantic model."""
        bbox = self.bounds.polygon
        logger.info(f"Diagonal: {self.bounds.diagonal_length_m:.2f} m")

        now = arrow.utcnow()
        base_updates = BaseUpdates(
            start_datetime=now.shift(seconds=START_TIME_OFFSET_S).isoformat(),
            end_datetime=now.shift(seconds=END_TIME_OFFSET_S).isoformat(),
            flight_declaration_geo_json=self._build_geojson_bbox(bbox),
        )

        final_payload = self.template.copy()
        final_payload.update(base_updates.model_dump())
        final_payload.update(FlightDeclarationOverrides().model_dump())

        # Validate and return as FlightDeclaration model
        return FlightDeclaration.model_validate(final_payload)

    def get_flight_declaration_model(self) -> FlightDeclaration:
        """Helper function to get output as FlightDeclaration model."""
        return self.generate()

    def get_flight_declaration_dict(self) -> dict[str, Any]:
        """Helper function to get output as dictionary."""
        return self.generate().model_dump(mode="json")


if __name__ == "__main__":
    generator = FlightDeclarationGenerator(template_path=DEFAULT_TEMPLATE_PATH, bounds_path=BOUNDS_FILE_PATH)
    sample = generator.generate()
    print(json.dumps(sample.model_dump(), indent=2))

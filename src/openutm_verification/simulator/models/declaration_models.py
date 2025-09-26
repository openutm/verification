from __future__ import annotations

from typing import Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pyproj import Geod
from shapely.geometry import Polygon, box

MINIMUM_DIAGONAL_LENGTH_M = 500  # Minimum bounding box diagonal in meters


class FlightDeclaration(BaseModel):
    """Final validated flight declaration model."""

    start_datetime: str
    end_datetime: str
    flight_declaration_geo_json: "FeatureCollection"

    model_config = ConfigDict(extra="allow")


class FeatureCollection(BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[Feature]

    model_config = ConfigDict(frozen=True)


class Feature(BaseModel):
    type: Literal["Feature"] = "Feature"
    geometry: PolygonGeometry
    properties: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True)


class PolygonGeometry(BaseModel):
    type: Literal["Polygon"] = "Polygon"
    coordinates: list[list[tuple[float, float]]]

    model_config = ConfigDict(frozen=True)


class FlightDeclarationBounds(BaseModel):
    """Validated bounding box for flight declarations."""

    min_x: float
    max_x: float
    min_y: float
    max_y: float

    model_config = ConfigDict(arbitrary_types_allowed=True)

    _geod: ClassVar[Geod] = Geod(ellps="WGS84")

    @model_validator(mode="after")
    def _validate_bounds(self) -> FlightDeclarationBounds:
        if self.min_x >= self.max_x:
            raise ValueError("min_x must be less than max_x")
        if self.min_y >= self.max_y:
            raise ValueError("min_y must be less than max_y")
        if self.diagonal_length_m <= MINIMUM_DIAGONAL_LENGTH_M:
            raise ValueError(f"Bounding box diagonal must exceed {MINIMUM_DIAGONAL_LENGTH_M} meters.")
        return self

    @property
    def polygon(self) -> Polygon:
        return box(self.min_x, self.min_y, self.max_x, self.max_y)

    @property
    def diagonal_length_m(self) -> float:
        return self._geod.inv(self.min_x, self.min_y, self.max_x, self.max_y)[2]


class BaseUpdates(BaseModel):
    """Model for base updates in flight declaration generation."""

    start_datetime: str
    end_datetime: str
    flight_declaration_geo_json: "FeatureCollection"


class FlightDeclarationOverrides(BaseModel):
    """Model for overrides in flight declaration generation."""

    flight_id: str = "FL123"
    operator_id: str = "OP456"
    # TODO: verify if these fields are needed
    # departure_time: str = "2024-01-01T10:00:00Z"
    # arrival_time: str = "2024-01-01T10:30:00Z"
    # origin: str = "POINT(1.0 2.0)"
    # destination: str = "POINT(3.0 4.0)"

    model_config = ConfigDict(extra="allow")

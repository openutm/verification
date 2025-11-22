"""
Pydantic models for validating simulator config.json and GeoJSON content for telemetry.

These models validate that the provided FeatureCollection contains at least one
Feature with a LineString geometry of at least 300 meters, and compute useful
derived values used by the simulator (bounds, center, half-box, and a set of
interpolated flight path points).
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Tuple

import shapely.geometry
from pydantic import BaseModel, Field, ValidationError, field_validator
from pyproj import Geod

LngLat = Tuple[float, float]

MINIMUM_LINESTRING_LENGTH_M = 300.0  # meters


class GeoJSONLineString(BaseModel):
    type: Literal["LineString"]
    coordinates: List[LngLat]

    @field_validator("coordinates")
    @classmethod
    def _validate_coords(cls, v: List[LngLat]) -> List[LngLat]:
        if len(v) < 2:
            raise ValueError("LineString must have at least two coordinates")
        for lon, lat in v:
            if not (-180.0 <= lon <= 180.0 and -90.0 <= lat <= 90.0):
                raise ValueError("Coordinates must be [lon, lat] with valid ranges")
        return v


class GeoJSONFeature(BaseModel):
    type: Literal["Feature"] = "Feature"
    properties: Dict[str, Any] = Field(default_factory=dict)
    geometry: GeoJSONLineString


class GeoJSONFeatureCollection(BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: List[GeoJSONFeature]

    @field_validator("features")
    @classmethod
    def _validate_features(cls, v: List[GeoJSONFeature]) -> List[GeoJSONFeature]:
        if not v:
            raise ValueError("FeatureCollection must contain at least one feature")
        return v


class ValidatedFlightPath(BaseModel):
    """Validated and preprocessed flight path derived from a GeoJSON LineString.

    Fields:
    - start: (lon, lat)
    - end: (lon, lat)
    - bounds: (minx, miny, maxx, maxy)
    - box_bounds: same as bounds (convenience)
    - half_box_bounds: (minx, miny, midx, maxy)
    - center: (lon, lat)
    - line_length_m: total length in meters
    - path_points: list of (lon, lat) interpolated along the LineString
    """

    start: LngLat
    end: LngLat
    bounds: Tuple[float, float, float, float]
    box_bounds: Tuple[float, float, float, float]
    half_box_bounds: Tuple[float, float, float, float]
    center: LngLat
    line_length_m: float
    path_points: List[LngLat]

    @classmethod
    def from_feature_collection(cls, fc: Dict[str, Any] | GeoJSONFeatureCollection) -> "ValidatedFlightPath":
        """Validate the provided FeatureCollection and compute derived fields.

        Accepts either a raw dict (GeoJSON) or a typed GeoJSONFeatureCollection.
        """
        if not isinstance(fc, GeoJSONFeatureCollection):
            try:
                fc_model = GeoJSONFeatureCollection.model_validate(fc)
            except ValidationError as e:
                raise ValueError(f"Invalid GeoJSON FeatureCollection: {e}") from e
        else:
            fc_model = fc

        feature = fc_model.features[0]
        coords = feature.geometry.coordinates

        # Build a Shapely LineString for geometric operations
        shapely_line = shapely.geometry.LineString(coords)

        # Compute geodesic length using WGS84 ellipsoid
        geod = Geod(ellps="WGS84")
        length_m = 0.0
        for i in range(len(coords) - 1):
            lon1, lat1 = coords[i]
            lon2, lat2 = coords[i + 1]
            _, _, d = geod.inv(lon1, lat1, lon2, lat2)
            length_m += d

        if length_m < MINIMUM_LINESTRING_LENGTH_M:
            raise ValueError(f"LineString must be at least {MINIMUM_LINESTRING_LENGTH_M} meters long. Found length: {length_m:.2f} meters")

        # Bounds and center
        minx, miny, maxx, maxy = shapely_line.bounds
        midx = (minx + maxx) / 2.0
        center = ((coords[0][0] + coords[-1][0]) / 2.0, (coords[0][1] + coords[-1][1]) / 2.0)

        # Generate path points akin to the legacy implementation
        # num_points approximates 1 point per 2 meters of length
        num_points = max(int(length_m / 2), 2)
        # Legacy used normalized steps of 0.004; keep same cadence and clamp to [0,1]
        fractions = (min(0.004 * i, 1.0) for i in range(num_points))
        path_points: List[LngLat] = []
        for f in fractions:
            p = shapely_line.interpolate(f, normalized=True)
            path_points.append((float(p.x), float(p.y)))

        return cls(
            start=coords[0],
            end=coords[-1],
            bounds=(minx, miny, maxx, maxy),
            box_bounds=(minx, miny, maxx, maxy),
            half_box_bounds=(minx, miny, midx, maxy),
            center=center,
            line_length_m=length_m,
            path_points=path_points,
        )

"""Helpers to convert between PostGIS geometry columns and plain lon/lat
floats for API serialization. Kept isolated so route/service code never
has to import shapely/geoalchemy2 directly."""

from typing import Any

from geoalchemy2.shape import to_shape
from pyproj import Geod

# WGS84 ellipsoid — standard-accuracy geodesic distance, same accuracy
# class already used for the ED50->WGS84 datum transform in ingestion.
_GEOD = Geod(ellps="WGS84")


def point_to_lonlat(geom: Any | None) -> tuple[float, float] | None:
    if geom is None:
        return None
    point = to_shape(geom)
    return point.x, point.y


def linestring_endpoints(geom: Any | None) -> tuple[tuple[float, float], tuple[float, float]] | None:
    """First and last (lon, lat) point of a LineString, or None if there
    isn't at least one point to form an endpoint pair."""
    if geom is None:
        return None
    line = to_shape(geom)
    coords = list(line.coords)
    if len(coords) < 2:
        return None
    return coords[0], coords[-1]


def geodesic_distance_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Great-circle distance in km between two (lon, lat) points."""
    _, _, distance_m = _GEOD.inv(a[0], a[1], b[0], b[1])
    return distance_m / 1000.0

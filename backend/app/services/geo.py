"""Helpers to convert between PostGIS geometry columns and plain lon/lat
floats for API serialization. Kept isolated so route/service code never
has to import shapely/geoalchemy2 directly."""

from typing import Any

from geoalchemy2.shape import to_shape


def point_to_lonlat(geom: Any | None) -> tuple[float, float] | None:
    if geom is None:
        return None
    point = to_shape(geom)
    return point.x, point.y

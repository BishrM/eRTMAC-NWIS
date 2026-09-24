"""Coordinate datum transforms.

SODIR wellbore positions are reported in ED50 (EPSG:4230), not WGS84 —
confirmed against real SODIR export data and the Directorate's own field
docs ("wlbGeodeticDatum ... Example of legal values: ED50"), not an edge
case. We store everything as WGS84 (EPSG:4326, matching PostGIS SRID
4326 used throughout the schema), so ED50 positions are transformed on
the way in.

pyproj's default ED50->WGS84 transform is a standard-accuracy Helmert/
grid transform (~1-3m in NW Europe) — more than sufficient for map-scale
visualization; a hackathon prototype has no need for survey-grade
accuracy here.
"""

from pyproj import Transformer

_ED50_TO_WGS84 = Transformer.from_crs("EPSG:4230", "EPSG:4326", always_xy=True)


def ed50_to_wgs84(latitude: float, longitude: float) -> tuple[float, float]:
    """Returns (latitude, longitude) in WGS84 given ED50 inputs."""
    lon_wgs84, lat_wgs84 = _ED50_TO_WGS84.transform(longitude, latitude)
    return lat_wgs84, lon_wgs84

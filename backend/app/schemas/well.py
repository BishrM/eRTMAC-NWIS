import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class WellRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    well_id: str
    name: str
    operator: str | None
    field: str | None
    country: str | None

    longitude: float | None
    latitude: float | None

    water_depth_m: float | None
    total_depth_md_m: float | None
    total_depth_tvd_m: float | None
    formation: str | None

    spud_date: date | None
    completion_date: date | None

    source: str

    created_at: datetime
    updated_at: datetime


class WellListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[WellRead]

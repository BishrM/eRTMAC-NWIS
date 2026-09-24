import uuid
from datetime import date, datetime
from typing import Any

from geoalchemy2 import Geometry
from sqlalchemy import Date, DateTime, Float, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Well(Base):
    """A drilling well (current or historical), identified by a
    stable external `well_id` (e.g. Volve/SODIR well name)."""

    __tablename__ = "wells"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    well_id: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)

    name: Mapped[str] = mapped_column(String(256), nullable=False)
    operator: Mapped[str | None] = mapped_column(String(256), nullable=True)
    field: Mapped[str | None] = mapped_column(String(256), nullable=True)
    country: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # Surface location, WGS84 (lon, lat)
    location: Mapped[Any | None] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326), nullable=True
    )

    water_depth_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_depth_md_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_depth_tvd_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    formation: Mapped[str | None] = mapped_column(String(256), nullable=True)

    spud_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    completion_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Data provenance, e.g. "volve", "sodir", "demo". Required so results
    # never appear to be validated on confidential OIL data.
    source: Mapped[str] = mapped_column(String(64), nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    wellbores: Mapped[list["Wellbore"]] = relationship(
        back_populates="well", cascade="all, delete-orphan"
    )
    events: Mapped[list["Event"]] = relationship(
        back_populates="well", cascade="all, delete-orphan"
    )
    documents: Mapped[list["SourceDocument"]] = relationship(
        back_populates="well", cascade="all, delete-orphan"
    )

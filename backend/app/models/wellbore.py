import uuid
from datetime import datetime
from typing import Any

from geoalchemy2 import Geometry
from sqlalchemy import DateTime, Float, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Wellbore(Base):
    """A drilled wellbore belonging to a well. Trajectory is stored as a
    surface-projected LineString for now (2D); full MD/Inc/Azi survey
    stations can be added later without breaking this shape."""

    __tablename__ = "wellbores"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    well_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("wells.id", ondelete="CASCADE"), nullable=False, index=True
    )

    name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)

    # Stable external ID from the source registry (e.g. SODIR's wlbNpdidWellbore),
    # used as the upsert/dedup key for re-running ingestion idempotently.
    npdid_wellbore: Mapped[str | None] = mapped_column(
        String(32), unique=True, index=True, nullable=True
    )

    trajectory: Mapped[Any | None] = mapped_column(
        Geometry(geometry_type="LINESTRING", srid=4326), nullable=True
    )

    md_top_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    md_bottom_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    tvd_bottom_m: Mapped[float | None] = mapped_column(Float, nullable=True)

    source: Mapped[str] = mapped_column(String(64), nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    well: Mapped["Well"] = relationship(back_populates="wellbores")
    events: Mapped[list["Event"]] = relationship(back_populates="wellbore")

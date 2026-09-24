import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, Float, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class EventType(str, enum.Enum):
    STUCK_PIPE = "stuck_pipe"
    LOST_CIRCULATION = "lost_circulation"
    KICK_INFLUX = "kick_influx"
    WELLBORE_INSTABILITY = "wellbore_instability"
    BHA_EQUIPMENT_ISSUE = "bha_equipment_issue"
    NPT = "npt"
    OTHER = "other"


class Event(Base):
    """A historical drilling event extracted for a well. Every row
    preserves well_id, event_type, depth, source document, and a
    location within that source plus an extraction confidence —
    per CLAUDE.md's evidence/provenance requirement."""

    __tablename__ = "events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    well_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("wells.id", ondelete="CASCADE"), nullable=False, index=True
    )
    wellbore_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("wellbores.id", ondelete="SET NULL"), nullable=True
    )
    source_document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("source_documents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    event_type: Mapped[EventType] = mapped_column(Enum(EventType, name="event_type"), nullable=False)
    depth_md_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    depth_tvd_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    occurred_at: Mapped[date | None] = mapped_column(Date, nullable=True)

    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Where in the source document this was extracted from, e.g. "p.12" or
    # a character offset range. Free text since source formats vary.
    source_location: Mapped[str | None] = mapped_column(String(256), nullable=True)

    # Extraction confidence in [0, 1]. Null means "not scored" (e.g. manual entry).
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    well: Mapped["Well"] = relationship(back_populates="events")
    wellbore: Mapped["Wellbore"] = relationship(back_populates="events")
    source_document: Mapped["SourceDocument"] = relationship(back_populates="events")

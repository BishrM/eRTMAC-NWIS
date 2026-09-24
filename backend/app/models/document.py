import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class DocumentType(str, enum.Enum):
    DAILY_REPORT = "daily_report"
    END_OF_WELL_REPORT = "end_of_well_report"
    COMPLETION_REPORT = "completion_report"
    OTHER = "other"


class SourceDocument(Base):
    """A source document (e.g. a well report PDF) that events and
    evidence snippets are extracted from. Provenance is mandatory."""

    __tablename__ = "source_documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    well_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("wells.id", ondelete="SET NULL"), nullable=True, index=True
    )

    title: Mapped[str] = mapped_column(String(512), nullable=False)
    doc_type: Mapped[DocumentType] = mapped_column(
        Enum(DocumentType, name="document_type"), nullable=False, default=DocumentType.OTHER
    )

    # Where the raw file lives (local path or URL) — not the extracted text.
    uri: Mapped[str] = mapped_column(String(1024), nullable=False)

    source: Mapped[str] = mapped_column(String(64), nullable=False)
    ocr_applied: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    well: Mapped["Well"] = relationship(back_populates="documents")
    events: Mapped[list["Event"]] = relationship(back_populates="source_document")

"""Import all models so `Base.metadata` (and Alembic autogenerate) sees them."""

from app.models.document import SourceDocument  # noqa: F401
from app.models.event import Event, EventType  # noqa: F401
from app.models.well import Well  # noqa: F401
from app.models.wellbore import Wellbore  # noqa: F401

__all__ = ["Well", "Wellbore", "Event", "EventType", "SourceDocument"]

from qdrant_client import QdrantClient

from app.config import settings

_client: QdrantClient | None = None


def get_qdrant_client() -> QdrantClient:
    global _client
    if _client is None:
        _client = QdrantClient(host=settings.qdrant_host, port=settings.qdrant_http_port)
    return _client


def qdrant_is_healthy() -> bool:
    try:
        get_qdrant_client().get_collections()
        return True
    except Exception:
        return False

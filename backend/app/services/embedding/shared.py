from ...core.config import settings
from .service import EmbeddingService


shared_embedding_service = EmbeddingService(
    settings.EMBEDDING_MODEL,
    batch_size=settings.EMBEDDING_BATCH_SIZE,
)

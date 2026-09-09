import asyncio
import io
from uuid import UUID, uuid4

import pytest
from fastapi import UploadFile

from backend.app.db.models import CodeChunkRecord
from backend.app.services.code_upload import CodeUploadService
from backend.app.services.embedding import InMemoryEmbedding
from backend.app.services.repository_ingestion import (
    RepositoryIngestionException,
    RepositoryIngestionService,
)


class FakeEmbeddingService:
    def embed_chunks(self, chunks):
        return [
            InMemoryEmbedding(chunk.chunk_id, 384, [0.0] * 384)
            for chunk in chunks
        ]


class FakeSession:
    def __init__(self) -> None:
        self.records = []
        self.committed = False

    def add(self, record) -> None:
        self.records.append(record)

    async def flush(self) -> None:
        if getattr(self.records[-1], "id", None) is None:
            self.records[-1].id = uuid4()

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.records.clear()


def upload(filename: str, content: bytes) -> UploadFile:
    return UploadFile(filename=filename, file=io.BytesIO(content))


def service() -> RepositoryIngestionService:
    return RepositoryIngestionService(
        upload_service=CodeUploadService(5),
        embedding_service=FakeEmbeddingService(),
    )


def test_ingest_persists_project_files_chunks_and_embeddings() -> None:
    session = FakeSession()

    result = asyncio.run(
        service().ingest(
            "demo-project",
            [
                upload("src/auth.py", b"def login():\n    return True\n"),
                upload("src/config.py", b"DEBUG = False\n"),
            ],
            session,
        )
    )

    assert isinstance(result.project_id, UUID)
    assert result.project_name == "demo-project"
    assert result.files_processed == 2
    assert result.files_failed == 0
    assert result.chunks_created == 2
    assert result.embeddings_created == 2
    assert result.errors == []
    assert session.committed is True
    assert len(session.records) == 5
    assert session.records[0].name == "demo-project"
    chunk_records = [
        record for record in session.records if isinstance(record, CodeChunkRecord)
    ]
    assert len(chunk_records) == 2
    assert all(record.embedding is not None for record in chunk_records)
    assert all(len(record.embedding) == 384 for record in chunk_records)


def test_ingest_continues_after_unsupported_file() -> None:
    session = FakeSession()

    result = asyncio.run(
        service().ingest(
            "partial-project",
            [
                upload("README.md", b"not parsed"),
                upload("valid.py", b"value = 1\n"),
            ],
            session,
        )
    )

    assert result.files_processed == 1
    assert result.files_failed == 1
    assert result.chunks_created == 1
    assert result.embeddings_created == 1
    assert result.errors[0].code == "UNSUPPORTED_FILE_TYPE"
    assert session.committed is True


def test_ingest_empty_input_is_rejected() -> None:
    with pytest.raises(RepositoryIngestionException) as error:
        asyncio.run(service().ingest("empty-project", [], FakeSession()))

    assert error.value.code == "EMPTY_BATCH"
    assert error.value.status_code == 400


def test_ingest_requires_project_name() -> None:
    with pytest.raises(RepositoryIngestionException) as error:
        asyncio.run(service().ingest("  ", [upload("valid.py", b"x = 1\n")], FakeSession()))

    assert error.value.code == "INVALID_PROJECT_NAME"
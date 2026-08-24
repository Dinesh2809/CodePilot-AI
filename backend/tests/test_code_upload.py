import pytest
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)
UPLOAD_URL = "/api/v1/code/upload"


@pytest.mark.parametrize(
    ("filename", "language"),
    [
        ("example.py", "python"),
        ("example.js", "javascript"),
        ("example.ts", "typescript"),
        ("Example.java", "java"),
        ("component.jsx", "javascript"),
        ("component.tsx", "typescript"),
    ],
)
def test_supported_code_files(filename: str, language: str) -> None:
    source = "line one\nline two\n"

    response = client.post(
        UPLOAD_URL,
        files={"file": (filename, source.encode("utf-8"), "text/plain")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["file"] == {
        "filename": filename,
        "extension": "." + filename.rsplit(".", 1)[1].lower(),
        "language": language,
        "size_bytes": len(source.encode("utf-8")),
        "line_count": 2,
    }


def test_unsupported_file_type() -> None:
    response = client.post(UPLOAD_URL, files={"file": ("document.pdf", b"data", "application/pdf")})

    assert response.status_code == 415
    assert response.json() == {
        "success": False,
        "error": {
            "code": "UNSUPPORTED_FILE_TYPE",
            "message": "Unsupported file type: .pdf",
        },
    }


def test_empty_file() -> None:
    response = client.post(UPLOAD_URL, files={"file": ("empty.py", b"", "text/plain")})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "EMPTY_FILE"


def test_file_larger_than_configured_limit() -> None:
    response = client.post(
        UPLOAD_URL,
        files={"file": ("large.py", b"x" * (5 * 1024 * 1024 + 1), "text/plain")},
    )

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "FILE_TOO_LARGE"


def test_invalid_utf8() -> None:
    response = client.post(UPLOAD_URL, files={"file": ("invalid.py", b"\xff", "text/plain")})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_ENCODING"


def test_missing_file() -> None:
    response = client.post(UPLOAD_URL)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "MISSING_FILE"
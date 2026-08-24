from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)
BATCH_URL = "/api/v1/code/upload-batch"


def multipart_files(*files: tuple[str, bytes]) -> list[tuple[str, tuple[str, bytes, str]]]:
    return [("files", (filename, content, "text/plain")) for filename, content in files]


def test_single_python_file_is_ingested_and_chunked() -> None:
    response = client.post(
        BATCH_URL,
        files=multipart_files(("src/auth.py", b"def login():\n    return True\n")),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["repository"] == {"file_count": 1, "chunk_count": 1}
    assert body["files"] == [
        {
            "filename": "src/auth.py",
            "language": "python",
            "extension": ".py",
            "size_bytes": 29,
            "line_count": 2,
            "chunk_count": 1,
            "parser_status": "completed",
            "chunker_status": "completed",
        }
    ]
    assert body["chunks"][0]["filename"] == "src/auth.py"


def test_multiple_python_files_and_nested_paths() -> None:
    response = client.post(
        BATCH_URL,
        files=multipart_files(
            ("src/auth.py", b"def login():\n    return True\n"),
            ("src/services/user.py", b"class User:\n    pass\n"),
        ),
    )

    body = response.json()
    assert response.status_code == 200
    assert body["repository"]["file_count"] == 2
    assert {file["filename"] for file in body["files"]} == {
        "src/auth.py",
        "src/services/user.py",
    }
    assert body["statistics"]["languages"] == {"python": 2}


def test_mixed_supported_languages_report_unimplemented_parsers() -> None:
    response = client.post(
        BATCH_URL,
        files=multipart_files(
            ("main.py", b"x = 1\n"),
            ("app.js", b"const x = 1;\n"),
            ("types.ts", b"const x: number = 1;\n"),
            ("App.java", b"class App {}\n"),
            ("component.jsx", b"export default {};\n"),
            ("component.tsx", b"export default {};\n"),
        ),
    )

    body = response.json()
    assert response.status_code == 200
    assert body["statistics"]["languages"] == {
        "python": 1,
        "javascript": 2,
        "typescript": 2,
        "java": 1,
    }
    non_python = [file for file in body["files"] if file["language"] != "python"]
    assert all(file["parser_status"] == "not_implemented" for file in non_python)
    assert all(file["chunker_status"] == "not_implemented" for file in non_python)


def test_unsupported_empty_oversized_and_invalid_encoding_files_are_reported() -> None:
    response = client.post(
        BATCH_URL,
        files=multipart_files(
            ("bad.pdf", b"pdf"),
            ("empty.py", b""),
            ("large.py", b"x" * (5 * 1024 * 1024 + 1)),
            ("invalid.py", b"\xff"),
            ("good.py", b"x = 1\n"),
        ),
    )

    body = response.json()
    assert response.status_code == 200
    assert body["success"] is True
    assert body["repository"]["file_count"] == 1
    assert {error["code"] for error in body["errors"]} == {
        "UNSUPPORTED_FILE_TYPE",
        "EMPTY_FILE",
        "FILE_TOO_LARGE",
        "INVALID_ENCODING",
    }
    assert body["statistics"]["failed_files"] == 4


def test_syntax_error_is_partial_failure() -> None:
    response = client.post(
        BATCH_URL,
        files=multipart_files(
            ("good.py", b"def good():\n    return True\n"),
            ("bad.py", b"def broken(:\n"),
        ),
    )

    body = response.json()
    assert response.status_code == 200
    assert body["success"] is True
    assert body["statistics"]["successful_files"] == 1
    assert body["statistics"]["failed_files"] == 1
    assert body["errors"][0]["code"] == "SYNTAX_ERROR"


def test_unsafe_and_ignored_paths_are_rejected() -> None:
    response = client.post(
        BATCH_URL,
        files=multipart_files(
            ("../malicious.py", b"x = 1\n"),
            (r"..\malicious2.py", b"x = 1\n"),
            ("C:/outside.py", b"x = 1\n"),
            (".github/workflows/check.py", b"x = 1\n"),
            ("safe.py", b"x = 1\n"),
        ),
    )

    body = response.json()
    assert response.status_code == 200
    assert body["repository"]["file_count"] == 1
    assert {error["code"] for error in body["errors"]} == {
        "UNSAFE_FILENAME",
        "IGNORED_PATH",
    }


def test_empty_batch_is_rejected() -> None:
    response = client.post(BATCH_URL)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "EMPTY_BATCH"


def test_batch_file_limit_is_enforced() -> None:
    files = [(f"file_{index}.py", b"x = 1\n") for index in range(51)]
    response = client.post(BATCH_URL, files=multipart_files(*files))

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "TOO_MANY_FILES"


def test_statistics_include_lines_sizes_chunks_and_total_files() -> None:
    first = b"x = 1\n\ny = 2\n"
    second = b"def run():\n    return 1\n"
    response = client.post(
        BATCH_URL,
        files=multipart_files(("first.py", first), ("second.py", second)),
    )

    statistics = response.json()["statistics"]
    assert statistics["total_files"] == 2
    assert statistics["successful_files"] == 2
    assert statistics["failed_files"] == 0
    assert statistics["total_lines"] == 5
    assert statistics["total_size_bytes"] == len(first) + len(second)
    assert statistics["total_chunks"] == 2


def test_existing_endpoints_still_work() -> None:
    assert client.get("/health").json() == {"status": "healthy"}
    assert client.post(
        "/api/v1/code/upload",
        files={"file": ("file.py", b"x = 1\n", "text/plain")},
    ).status_code == 200
    assert client.post(
        "/api/v1/code/parse",
        files={"file": ("file.py", b"x = 1\n", "text/plain")},
    ).status_code == 200
    assert client.post(
        "/api/v1/code/chunk",
        files={"file": ("file.py", b"x = 1\n", "text/plain")},
    ).status_code == 200

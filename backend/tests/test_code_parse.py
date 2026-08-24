from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)
PARSE_URL = "/api/v1/code/parse"


SOURCE = (
    '"""Example module."""\n'
    "import os\n"
    "from pathlib import Path\n"
    "\n"
    "MAX_RETRIES = 3\n"
    "\n"
    '@decorator.route("/discount")\n'
    "def calculate_discount(price: float, discount: float) -> float:\n"
    "    def clamp(value: float) -> float:\n"
    "        return value\n"
    "    return clamp(price - discount)\n"
    "\n"
    "async def fetch_data(url: str) -> bytes:\n"
    "    return b\"\"\n"
    "\n"
    "class UserService(BaseService):\n"
    "    @classmethod\n"
    '    def create(cls, name: str) -> "UserService":\n'
    "        return cls()\n"
    "\n"
    "class Empty:\n"
    "    pass\n"
)


def test_python_parse_extracts_structure() -> None:
    response = client.post(
        PARSE_URL,
        files={"file": ("example.py", SOURCE.encode("utf-8"), "text/x-python")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["language"] == "python"
    assert body["file"] == {"filename": "example.py", "line_count": 22}
    assert body["imports"] == [
        {"module": "os", "type": "import"},
        {"module": "pathlib", "name": "Path", "type": "from_import"},
    ]
    assert body["variables"] == [{"name": "MAX_RETRIES", "line": 5}]

    functions = {function["name"]: function for function in body["functions"]}
    assert functions["calculate_discount"]["line"] == 8
    assert functions["calculate_discount"]["end_line"] == 11
    assert functions["calculate_discount"]["arguments"] == [
        {"name": "price", "annotation": "float"},
        {"name": "discount", "annotation": "float"},
    ]
    assert functions["calculate_discount"]["return_annotation"] == "float"
    assert functions["calculate_discount"]["decorators"] == ["decorator.route('/discount')"]
    assert functions["calculate_discount"]["is_async"] is False
    assert functions["clamp"]["arguments"] == [{"name": "value", "annotation": "float"}]
    assert functions["fetch_data"]["is_async"] is True

    classes = {klass["name"]: klass for klass in body["classes"]}
    assert classes["UserService"]["bases"] == ["BaseService"]
    assert classes["UserService"]["methods"][0]["name"] == "create"
    assert classes["UserService"]["methods"][0]["return_annotation"] == "'UserService'"
    assert classes["Empty"]["methods"] == []


def test_empty_python_file_is_rejected_by_upload_validation() -> None:
    response = client.post(PARSE_URL, files={"file": ("empty.py", b"", "text/x-python")})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "EMPTY_FILE"


def test_comments_and_docstrings_do_not_create_structure() -> None:
    response = client.post(
        PARSE_URL,
        files={"file": ("comments.py", b'"""docs"""\n# comment\n', "text/x-python")},
    )

    assert response.status_code == 200
    assert response.json()["functions"] == []
    assert response.json()["classes"] == []
    assert response.json()["variables"] == []


def test_python_syntax_error_is_structured() -> None:
    response = client.post(PARSE_URL, files={"file": ("broken.py", b"def broken(:\n", "text/x-python")})

    assert response.status_code == 422
    assert response.json() == {
        "success": False,
        "error": {
            "code": "SYNTAX_ERROR",
            "message": "Unable to parse Python source code at line 1",
        },
    }


def test_non_python_parser_is_not_implemented() -> None:
    response = client.post(PARSE_URL, files={"file": ("script.js", b"function main() {}", "text/javascript")})

    assert response.status_code == 501
    assert response.json() == {
        "success": False,
        "error": {
            "code": "PARSER_NOT_IMPLEMENTED",
            "message": "Parsing is currently supported only for Python files.",
        },
    }


def test_health_endpoint_still_works() -> None:
    response = client.get("/health")

    assert response.status_code == 200
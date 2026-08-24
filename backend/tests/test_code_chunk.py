from fastapi.testclient import TestClient

from app.main import app
from app.services.code_chunker import PythonCodeChunker


client = TestClient(app)
CHUNK_URL = "/api/v1/code/chunk"


SOURCE = (
    '"""Example module."""\n'
    "import os\n"
    "from pathlib import Path\n"
    "\n"
    "MAX_RETRIES = 3\n"
    "\n"
    "def calculate_discount(price, discount):\n"
    "    def clamp(value):\n"
    "        return value\n"
    "    return clamp(price - discount)\n"
    "\n"
    "async def fetch_data(url):\n"
    "    return b\"\"\n"
    "\n"
    "class UserService(BaseService):\n"
    "    def create(self, name):\n"
    "        return name\n"
    "\n"
    "    async def delete(self, name):\n"
    "        return name\n"
    "\n"
    "def main():\n"
    "    return None\n"
    "\n"
    "main()\n"
)


def test_chunker_emits_semantic_chunks_and_preserves_source() -> None:
    result = PythonCodeChunker().chunk(SOURCE, "example.py")
    chunks = {chunk.chunk_id: chunk for chunk in result.chunks}

    assert result.success is True
    assert result.language == "python"
    assert chunks["example.py:imports:imports"].content == (
        "import os\nfrom pathlib import Path"
    )
    assert chunks["example.py:variables:variables"].content == "MAX_RETRIES = 3"
    function = chunks["example.py:function:calculate_discount"]
    assert function.start_line == 7
    assert function.end_line == 10
    assert function.content == "\n".join(SOURCE.splitlines()[6:10])
    assert function.chunk_type == "function"
    assert chunks["example.py:async_function:fetch_data"].chunk_type == "async_function"
    nested = chunks["example.py:nested_function:calculate_discount.clamp"]
    assert nested.parent == "calculate_discount"
    assert nested.function_name == "clamp"

    klass = chunks["example.py:class:UserService"]
    assert klass.class_name == "UserService"
    assert klass.start_line == 15
    assert klass.end_line == 20
    assert "class UserService(BaseService):" in klass.content
    method = chunks["example.py:method:UserService.create"]
    assert method.class_name == "UserService"
    assert method.function_name == "create"
    assert chunks["example.py:method:UserService.delete"].chunk_type == "method"
    assert chunks["example.py:module:module"].content == '"""Example module."""'
    assert chunks["example.py:module:module_2"].content == "main()"


def test_chunk_ids_are_deterministic() -> None:
    chunker = PythonCodeChunker()
    first = chunker.chunk(SOURCE, "example.py").model_dump()
    second = chunker.chunk(SOURCE, "example.py").model_dump()

    assert first == second


def test_empty_source_has_no_chunks() -> None:
    result = PythonCodeChunker().chunk("", "empty.py")

    assert result.success is True
    assert result.chunks == []


def test_chunk_endpoint_returns_chunks() -> None:
    response = client.post(
        CHUNK_URL,
        files={"file": ("example.py", SOURCE.encode("utf-8"), "text/x-python")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["filename"] == "example.py"
    assert any(chunk["name"] == "calculate_discount" for chunk in body["chunks"])
    assert any(chunk["name"] == "main" for chunk in body["chunks"])


def test_chunk_endpoint_rejects_syntax_errors() -> None:
    response = client.post(CHUNK_URL, files={"file": ("broken.py", b"def broken(:\n", "text/x-python")})

    assert response.status_code == 422
    assert response.json()["error"] == {
        "code": "SYNTAX_ERROR",
        "message": "Unable to parse Python source code at line 1",
    }


def test_chunk_endpoint_rejects_non_python_files() -> None:
    response = client.post(CHUNK_URL, files={"file": ("script.js", b"const x = 1", "text/javascript")})

    assert response.status_code == 501
    assert response.json()["error"]["code"] == "CHUNKER_NOT_IMPLEMENTED"

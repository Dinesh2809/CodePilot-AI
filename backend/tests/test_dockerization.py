from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DOCKERFILE = ROOT / "Dockerfile"
DOCKERIGNORE = ROOT / ".dockerignore"


def test_dockerfile_uses_production_asgi_startup() -> None:
    content = DOCKERFILE.read_text(encoding="utf-8")

    assert "FROM python:3.12-slim" in content
    assert "COPY backend/requirements.txt" in content
    assert "COPY backend /app/backend" in content
    assert "USER appuser" in content
    assert "backend.app.main:app" in content
    assert "--host 0.0.0.0" in content
    assert "${PORT:-8000}" in content
    assert ".env" not in content


def test_dockerignore_excludes_secrets_local_state_and_unneeded_files() -> None:
    content = DOCKERIGNORE.read_text(encoding="utf-8").splitlines()

    for entry in (".env", ".env.*", ".venv", "__pycache__", ".git", "backend/tests"):
        assert entry in content
    assert "!.env.example" not in content


def test_runtime_application_files_are_present() -> None:
    assert (ROOT / "backend" / "requirements.txt").is_file()
    assert (ROOT / "backend" / "app" / "main.py").is_file()
    assert (ROOT / "backend" / "app" / "core" / "config.py").is_file()


def test_docker_build_context_does_not_include_env_file() -> None:
    dockerignore = DOCKERIGNORE.read_text(encoding="utf-8")
    assert ".env" in dockerignore
    assert (ROOT / ".env").is_file()
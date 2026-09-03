from dataclasses import dataclass
from pathlib import PurePath, PureWindowsPath

from fastapi import UploadFile

from ..schemas.code import CodeFileMetadata


SUPPORTED_EXTENSIONS = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".java": "java",
    ".jsx": "javascript",
    ".tsx": "typescript",
}
IGNORED_DIRECTORIES = {".git", ".github", "node_modules", "__pycache__", ".venv", "dist", "build"}


@dataclass
class CodeUploadException(Exception):
    code: str
    message: str
    status_code: int


class CodeUploadService:
    def __init__(self, max_upload_size_mb: int) -> None:
        self.max_upload_size_bytes = max_upload_size_mb * 1024 * 1024

    async def process(self, upload: UploadFile | None) -> CodeFileMetadata:
        metadata, _ = await self.read_source(upload)
        return metadata

    async def read_source(
        self, upload: UploadFile | None, preserve_filename: bool = False
    ) -> tuple[CodeFileMetadata, str]:
        if upload is None or not upload.filename:
            raise CodeUploadException(
                "MISSING_FILE", "A file is required.", 400
            )

        raw_filename = upload.filename.replace("\\", "/")
        path_parts = [part for part in raw_filename.split("/") if part]
        if preserve_filename and (
            raw_filename.startswith("/")
            or PureWindowsPath(upload.filename).drive
            or ".." in path_parts
        ):
            raise CodeUploadException(
                "UNSAFE_FILENAME", "Uploaded filenames must use safe relative paths.", 400
            )

        filename = (
            "/".join(part for part in path_parts if part != ".")
            if preserve_filename
            else PurePath(upload.filename).name
        )
        if preserve_filename and any(part in IGNORED_DIRECTORIES for part in path_parts):
            raise CodeUploadException(
                "IGNORED_PATH", "Files in ignored repository directories are skipped.", 400
            )
        extension = PurePath(filename).suffix.lower()
        if extension not in SUPPORTED_EXTENSIONS:
            raise CodeUploadException(
                "UNSUPPORTED_FILE_TYPE",
                f"Unsupported file type: {extension or '[none]'}",
                415,
            )

        upload.file.seek(0, 2)
        size_bytes = upload.file.tell()
        upload.file.seek(0)
        if size_bytes == 0:
            raise CodeUploadException("EMPTY_FILE", "The uploaded file is empty.", 400)
        if size_bytes > self.max_upload_size_bytes:
            raise CodeUploadException(
                "FILE_TOO_LARGE",
                "The uploaded file exceeds the maximum allowed size.",
                413,
            )

        content = await upload.read()
        try:
            source = content.decode("utf-8")
        except UnicodeDecodeError:
            raise CodeUploadException(
                "INVALID_ENCODING", "The uploaded file must use UTF-8 encoding.", 400
            ) from None

        metadata = CodeFileMetadata(
            filename=filename,
            extension=extension,
            language=SUPPORTED_EXTENSIONS[extension],
            size_bytes=size_bytes,
            line_count=len(source.splitlines()),
        )
        return metadata, source
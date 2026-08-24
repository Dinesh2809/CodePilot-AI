from pydantic import BaseModel, Field


class CodeFileMetadata(BaseModel):
    filename: str
    extension: str
    language: str
    size_bytes: int
    line_count: int


class CodeUploadError(BaseModel):
    code: str
    message: str


class CodeUploadResponse(BaseModel):
    success: bool
    file: CodeFileMetadata | None = None
    error: CodeUploadError | None = None


class CodeImport(BaseModel):
    module: str
    name: str | None = None
    type: str


class FunctionArgument(BaseModel):
    name: str
    annotation: str | None = None


class CodeFunction(BaseModel):
    name: str
    line: int
    end_line: int | None = None
    arguments: list[FunctionArgument]
    return_annotation: str | None = None
    decorators: list[str]
    is_async: bool


class CodeClass(BaseModel):
    name: str
    line: int
    end_line: int | None = None
    bases: list[str]
    methods: list[CodeFunction]
    decorators: list[str]


class CodeVariable(BaseModel):
    name: str
    line: int


class CodeParseFile(BaseModel):
    filename: str
    line_count: int


class CodeParseResult(BaseModel):
    success: bool
    language: str | None = None
    file: CodeParseFile | None = None
    imports: list[CodeImport] = Field(default_factory=list)
    functions: list[CodeFunction] = Field(default_factory=list)
    classes: list[CodeClass] = Field(default_factory=list)
    variables: list[CodeVariable] = Field(default_factory=list)
    error: CodeUploadError | None = None


class CodeChunk(BaseModel):
    chunk_id: str
    filename: str
    language: str
    chunk_type: str
    name: str
    start_line: int
    end_line: int
    content: str
    parent: str | None = None
    class_name: str | None = None
    function_name: str | None = None


class CodeChunkResult(BaseModel):
    success: bool
    filename: str | None = None
    language: str | None = None
    chunks: list[CodeChunk] = Field(default_factory=list)
    error: CodeUploadError | None = None


class RepositoryChunk(BaseModel):
    chunk_id: str
    filename: str
    language: str
    chunk_type: str
    name: str
    start_line: int
    end_line: int
    parent: str | None = None
    class_name: str | None = None
    function_name: str | None = None


class RepositoryFile(BaseModel):
    filename: str
    language: str | None = None
    extension: str | None = None
    size_bytes: int = 0
    line_count: int = 0
    chunk_count: int = 0
    parser_status: str
    chunker_status: str


class RepositoryFileError(BaseModel):
    filename: str
    code: str
    message: str


class RepositorySummary(BaseModel):
    file_count: int
    chunk_count: int


class RepositoryStatistics(BaseModel):
    total_files: int
    successful_files: int
    failed_files: int
    total_lines: int
    total_size_bytes: int
    total_chunks: int
    languages: dict[str, int] = Field(default_factory=dict)


class RepositoryIngestionResponse(BaseModel):
    success: bool
    repository: RepositorySummary
    files: list[RepositoryFile] = Field(default_factory=list)
    chunks: list[RepositoryChunk] = Field(default_factory=list)
    statistics: RepositoryStatistics
    errors: list[RepositoryFileError] = Field(default_factory=list)


class EmbeddingMetadata(BaseModel):
    chunk_id: str
    dimension: int


class EmbeddingResponse(BaseModel):
    success: bool
    embedding_model: str
    embedding_dimension: int | None = None
    filename: str | None = None
    chunks: list[EmbeddingMetadata] = Field(default_factory=list)
    errors: list[RepositoryFileError] = Field(default_factory=list)
    error: CodeUploadError | None = None
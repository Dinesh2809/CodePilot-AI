export type UploadStatus = "idle" | "selected" | "uploading" | "success" | "error";

export type SelectedFile = {
  id: string;
  file: File;
};

export type RepositoryFile = {
  filename: string;
  language: string | null;
  extension: string | null;
  size_bytes: number;
  line_count: number;
  chunk_count: number;
  parser_status: string;
  chunker_status: string;
};

export type RepositoryFileError = {
  filename: string;
  code: string;
  message: string;
};

export type RepositoryIngestionResponse = {
  success: boolean;
  repository: {
    file_count: number;
    chunk_count: number;
  };
  files: RepositoryFile[];
  chunks: Array<{
    chunk_id: string;
    filename: string;
    language: string;
    chunk_type: string;
    name: string;
    start_line: number;
    end_line: number;
    parent?: string | null;
    class_name?: string | null;
    function_name?: string | null;
  }>;
  statistics: {
    total_files: number;
    successful_files: number;
    failed_files: number;
    total_lines: number;
    total_size_bytes: number;
    total_chunks: number;
    languages: Record<string, number>;
  };
  errors: RepositoryFileError[];
};

export type ApiErrorResponse = {
  success?: boolean;
  error?: {
    code?: string;
    message?: string;
  };
};

export type SearchResult = {
  project_id: string;
  file_id: string;
  filename: string;
  chunk_id: string;
  chunk_type: string;
  name: string;
  start_line: number;
  end_line: number;
  language: string;
  content: string;
  similarity: number;
};

export type SearchResponse = {
  success: boolean;
  query: string;
  results: SearchResult[];
  result_count: number;
  error?: { code?: string; message?: string };
};

export type AskResponse = {
  success: boolean;
  query: string;
  answer: string | null;
  retrieved_results: SearchResult[];
  error?: { code?: string; message?: string };
};

export type ReviewFinding = {
  category: "security" | "quality" | "performance";
  severity: "critical" | "high" | "medium" | "low" | "info";
  title: string;
  description: string;
  filename: string;
  start_line: number;
  end_line: number;
  recommendation: string;
};

export type ReviewResponse = {
  success: boolean;
  query: string;
  summary: string | null;
  findings: ReviewFinding[];
  total_findings: number;
  critical_count: number;
  high_count: number;
  medium_count: number;
  low_count: number;
  info_count: number;
  categories: string[];
  agents_completed: string[];
  agents_failed: string[];
  error?: { code?: string; message?: string };
};

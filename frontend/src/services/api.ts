import type {
  ApiErrorResponse,
  AskResponse,
  RepositoryIngestionResponse,
  ReviewResponse,
  SearchResponse,
} from "../types/repository";

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, "");

export class ApiRequestError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiRequestError";
    this.status = status;
  }
}

export async function uploadRepository(files: File[]): Promise<RepositoryIngestionResponse> {
  const body = new FormData();
  files.forEach((file) => body.append("files", file, file.name));

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/v1/code/upload-batch`, {
      method: "POST",
      body,
    });
  } catch {
    throw new ApiRequestError(
      "We could not reach CodePilot. Check the connection and try again.",
      0,
    );
  }

  const payload = await readPayload(response);
  if (!response.ok) {
    throw new ApiRequestError(getErrorMessage(response.status, payload), response.status);
  }

  if (!isRepositoryResponse(payload)) {
    throw new ApiRequestError("The server returned an invalid analysis response.", response.status);
  }

  return payload;
}

export function searchRepository(query: string, topK = 5): Promise<SearchResponse> {
  return postJson<SearchResponse>("/api/v1/code/search", { query, top_k: topK }, isSearchResponse);
}

export function askRepository(query: string, topK = 5): Promise<AskResponse> {
  return postJson<AskResponse>("/api/v1/code/ask", { query, top_k: topK }, isAskResponse);
}

export function reviewRepository(query: string, topK = 10): Promise<ReviewResponse> {
  return postJson<ReviewResponse>("/api/v1/code/review", { query, top_k: topK }, isReviewResponse);
}

async function postJson<T>(
  path: string,
  body: object,
  isValid: (payload: unknown) => payload is T,
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch {
    throw new ApiRequestError("We could not reach CodePilot. Check the connection and try again.", 0);
  }

  const payload = await readPayload(response);
  if (!response.ok) throw new ApiRequestError(getAnalysisErrorMessage(response.status, payload), response.status);
  if (!isValid(payload)) throw new ApiRequestError("The server returned an invalid analysis response.", response.status);
  return payload;
}

async function readPayload(response: Response): Promise<unknown> {
  try {
    return (await response.json()) as unknown;
  } catch {
    return null;
  }
}

function getErrorMessage(status: number, payload: unknown): string {
  const apiMessage = getApiMessage(payload);
  if (apiMessage) return apiMessage;
  if (status >= 500) {
    return "Repository analysis could not be completed. The server may be temporarily out of resources. Please try a smaller repository or try again.";
  }
  if (status === 413) return "This upload is too large. Try fewer or smaller Python files.";
  return "The repository could not be analyzed. Check the selected files and try again.";
}

function getAnalysisErrorMessage(status: number, payload: unknown): string {
  const apiMessage = getApiMessage(payload);
  if (status >= 500) {
    return status === 502 || status === 503
      ? "The analysis service is temporarily out of resources. Please try again or use a smaller repository."
      : "The analysis could not be completed. Please try again.";
  }
  return apiMessage ?? "The analysis request could not be completed. Check your repository and try again.";
}

function getApiMessage(payload: unknown): string | null {
  if (!payload || typeof payload !== "object") return null;
  const error = (payload as ApiErrorResponse).error;
  return typeof error?.message === "string" ? error.message : null;
}

function isRepositoryResponse(payload: unknown): payload is RepositoryIngestionResponse {
  if (!payload || typeof payload !== "object") return false;
  const response = payload as Partial<RepositoryIngestionResponse>;
  return (
    typeof response.success === "boolean" &&
    typeof response.repository?.file_count === "number" &&
    typeof response.repository?.chunk_count === "number" &&
    Array.isArray(response.files) &&
    Array.isArray(response.chunks) &&
    typeof response.statistics?.total_files === "number" &&
    Array.isArray(response.errors)
  );
}

function isSearchResponse(payload: unknown): payload is SearchResponse {
  return isObject(payload) && typeof payload.success === "boolean" && typeof payload.query === "string" && Array.isArray(payload.results) && typeof payload.result_count === "number";
}

function isAskResponse(payload: unknown): payload is AskResponse {
  return isObject(payload) && typeof payload.success === "boolean" && typeof payload.query === "string" && (typeof payload.answer === "string" || payload.answer === null) && Array.isArray(payload.retrieved_results);
}

function isReviewResponse(payload: unknown): payload is ReviewResponse {
  return isObject(payload) && typeof payload.success === "boolean" && typeof payload.query === "string" && Array.isArray(payload.findings) && typeof payload.total_findings === "number" && (typeof payload.summary === "string" || payload.summary === null);
}

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

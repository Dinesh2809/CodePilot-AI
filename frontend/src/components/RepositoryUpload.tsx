import { ChangeEvent, DragEvent, useRef, useState } from "react";
import {
  AlertTriangle,
  Check,
  FileCode2,
  FilePlus2,
  LoaderCircle,
  Trash2,
  UploadCloud,
  X,
} from "lucide-react";
import { ApiRequestError, uploadRepository } from "../services/api";
import type {
  RepositoryIngestionResponse,
  SelectedFile,
  UploadStatus,
} from "../types/repository";

type RepositoryUploadProps = {
  onComplete: (response: RepositoryIngestionResponse) => void;
};

const MAX_FILES = 50;
const MAX_FILE_SIZE = 5 * 1024 * 1024;

export function RepositoryUpload({ onComplete }: RepositoryUploadProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [selectedFiles, setSelectedFiles] = useState<SelectedFile[]>([]);
  const [status, setStatus] = useState<UploadStatus>("idle");
  const [message, setMessage] = useState<string | null>(null);
  const [result, setResult] = useState<RepositoryIngestionResponse | null>(null);
  const [isDragging, setIsDragging] = useState(false);

  function acceptFiles(files: File[]) {
    const nextFiles: SelectedFile[] = [];
    const rejected: string[] = [];
    const existingNames = new Set(selectedFiles.map(({ file }) => file.name));

    for (const file of files) {
      if (!file.name.toLowerCase().endsWith(".py")) {
        rejected.push(`${file.name}: Python files only`);
        continue;
      }
      if (file.size === 0) {
        rejected.push(`${file.name}: file is empty`);
        continue;
      }
      if (file.size > MAX_FILE_SIZE) {
        rejected.push(`${file.name}: exceeds the 5 MB file limit`);
        continue;
      }
      if (existingNames.has(file.name) || nextFiles.some(({ file: item }) => item.name === file.name)) {
        rejected.push(`${file.name}: already selected`);
        continue;
      }
      nextFiles.push({ id: `${file.name}-${file.size}-${file.lastModified}`, file });
    }

    const combined = [...selectedFiles, ...nextFiles];
    if (combined.length > MAX_FILES) {
      setSelectedFiles(combined.slice(0, MAX_FILES));
      rejected.push(`Only the first ${MAX_FILES} files were kept.`);
    } else {
      setSelectedFiles(combined);
    }

    setResult(null);
    setStatus(combined.length > 0 ? "selected" : "idle");
    setMessage(rejected.length > 0 ? rejected.join("\n") : null);
  }

  function handleInput(event: ChangeEvent<HTMLInputElement>) {
    acceptFiles(Array.from(event.target.files ?? []));
    event.target.value = "";
  }

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setIsDragging(false);
    acceptFiles(Array.from(event.dataTransfer.files));
  }

  function removeFile(id: string) {
    const remaining = selectedFiles.filter((item) => item.id !== id);
    setSelectedFiles(remaining);
    setStatus(remaining.length > 0 ? "selected" : "idle");
    setMessage(null);
    setResult(null);
  }

  async function submit() {
    if (selectedFiles.length === 0 || status === "uploading") return;
    setStatus("uploading");
    setMessage(null);
    setResult(null);

    try {
      const response = await uploadRepository(selectedFiles.map(({ file }) => file));
      setResult(response);
      setStatus(response.success ? "success" : "error");
      if (response.success) onComplete(response);
      else setMessage("The repository was not analyzed. Review the file errors below.");
    } catch (error) {
      setStatus("error");
      setMessage(
        error instanceof ApiRequestError
          ? error.message
          : "Repository analysis could not be completed. Please try again.",
      );
    }
  }

  return (
    <section className="repository-upload" aria-labelledby="upload-title">
      <div className="upload-intro">
        <div>
          <span className="section-label">Repository intake</span>
          <h2 id="upload-title">Upload Python files to analyze</h2>
          <p>Start with up to 50 files. CodePilot will parse, chunk, embed, and index them for the next steps.</p>
        </div>
        <div className="upload-constraint"><FileCode2 size={16} /><span>Python · 5 MB per file</span></div>
      </div>

      <div
        className={`drop-zone ${isDragging ? "is-dragging" : ""}`}
        onDragEnter={(event) => { event.preventDefault(); setIsDragging(true); }}
        onDragOver={(event) => event.preventDefault()}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
        role="button"
        tabIndex={0}
        onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") inputRef.current?.click(); }}
        onClick={() => inputRef.current?.click()}
      >
        <input ref={inputRef} type="file" accept=".py,text/x-python" multiple onChange={handleInput} hidden />
        <div className="drop-icon"><UploadCloud size={24} /></div>
        <strong>Drop Python files here</strong>
        <span>or browse from your computer</span>
        <small>Duplicate filenames are skipped · {MAX_FILES} files maximum</small>
      </div>

      {message && <div className="upload-alert" role="alert"><AlertTriangle size={17} /><span>{message}</span><button type="button" aria-label="Dismiss message" onClick={() => setMessage(null)}><X size={15} /></button></div>}

      {selectedFiles.length > 0 && (
        <div className="selected-files">
          <div className="selected-header"><div><span className="section-label">Selected files</span><strong>{selectedFiles.length} {selectedFiles.length === 1 ? "file" : "files"}</strong></div><button className="text-button" type="button" onClick={() => { setSelectedFiles([]); setStatus("idle"); setResult(null); }}>Clear all</button></div>
          <div className="file-list">
            {selectedFiles.map(({ id, file }) => <div className="selected-file" key={id}><div className="file-icon"><FileCode2 size={17} /></div><div className="file-details"><strong>{file.name}</strong><span>{formatFileSize(file.size)}</span></div><button className="remove-file" type="button" aria-label={`Remove ${file.name}`} title={`Remove ${file.name}`} onClick={() => removeFile(id)}><Trash2 size={16} /></button></div>)}
          </div>
        </div>
      )}

      <div className="upload-footer">
        <div className={`upload-status status-${status}`} aria-live="polite">
          {status === "uploading" && <><LoaderCircle className="spin" size={16} /> Analyzing repository...</>}
          {status === "success" && <><Check size={16} /> Repository indexed</>}
          {status === "error" && <><AlertTriangle size={16} /> Analysis needs attention</>}
          {(status === "idle" || status === "selected") && <><FilePlus2 size={16} /> {status === "selected" ? "Ready to analyze" : "No files selected"}</>}
        </div>
        <button className="primary-button" type="button" disabled={selectedFiles.length === 0 || status === "uploading"} onClick={submit}>
          {status === "uploading" ? <LoaderCircle className="spin" size={17} /> : <UploadCloud size={17} />}
          {status === "uploading" ? "Analyzing..." : "Analyze repository"}
        </button>
      </div>

      {result && <UploadResult response={result} />}
    </section>
  );
}

function UploadResult({ response }: { response: RepositoryIngestionResponse }) {
  const { statistics } = response;
  return <div className="upload-result" role="status"><div className="result-heading"><div className="result-check"><Check size={17} /></div><div><strong>Analysis complete</strong><span>{statistics.successful_files} of {statistics.total_files} files processed successfully</span></div></div><div className="result-stats"><span><strong>{response.repository.chunk_count}</strong> chunks</span><span><strong>{statistics.total_lines}</strong> lines</span><span><strong>{Object.keys(statistics.languages).length}</strong> languages</span></div>{response.errors.length > 0 && <div className="result-errors"><AlertTriangle size={15} /><span>{response.errors.length} file issue{response.errors.length === 1 ? "" : "s"} reported</span></div>}</div>;
}

function formatFileSize(size: number) {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

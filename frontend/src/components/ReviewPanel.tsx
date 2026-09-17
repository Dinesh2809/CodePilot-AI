import { useMemo, useState } from "react";
import { AlertTriangle, CheckCircle2, Filter, LoaderCircle, ShieldCheck } from "lucide-react";
import { ApiRequestError, reviewRepository } from "../services/api";
import type { RepositoryIngestionResponse, ReviewFinding, ReviewResponse } from "../types/repository";

type ReviewPanelProps = { repository: RepositoryIngestionResponse | null; result: ReviewResponse | null; onResult: (result: ReviewResponse) => void };
type FilterValue = "all" | string;

export function ReviewPanel({ repository, result, onResult }: ReviewPanelProps) {
  const [status, setStatus] = useState<"idle" | "loading" | "error">("idle");
  const [message, setMessage] = useState<string | null>(null);
  const [query, setQuery] = useState("Review the uploaded repository for security, quality, and performance issues.");
  const [severity, setSeverity] = useState<FilterValue>("all");
  const [category, setCategory] = useState<FilterValue>("all");
  const [file, setFile] = useState<FilterValue>("all");

  const findings = result?.findings ?? [];
  const filteredFindings = useMemo(() => findings.filter((finding) => (severity === "all" || finding.severity === severity) && (category === "all" || finding.category === category) && (file === "all" || finding.filename === file)), [findings, severity, category, file]);
  const files = [...new Set(findings.map((finding) => finding.filename))];

  async function runReview() {
    if (!repository || status === "loading") return;
    setStatus("loading");
    setMessage(null);
    try {
      const response = await reviewRepository(query);
      onResult(response);
      setStatus("idle");
    } catch (error) {
      setStatus("error");
      setMessage(error instanceof ApiRequestError ? error.message : "The code review could not be completed. Please try again.");
    }
  }

  return <section className="review-panel">
    <div className="analysis-toolbar">
      <div><span className="section-label">Review command</span><h2>Ask the agents what matters.</h2><p>Security, quality, and performance agents will review the indexed repository context.</p></div>
      <button className="primary-button" type="button" disabled={!repository || status === "loading"} onClick={runReview}>{status === "loading" ? <LoaderCircle className="spin" size={17} /> : <ShieldCheck size={17} />}{status === "loading" ? "Reviewing..." : "Run AI code review"}</button>
    </div>
    {!repository && <div className="context-note"><AlertTriangle size={16} /> Upload a repository before running a review.</div>}
    <label className="review-query-label" htmlFor="review-query">Review focus</label>
    <textarea id="review-query" className="review-query" value={query} onChange={(event) => setQuery(event.target.value)} disabled={status === "loading"} rows={3} />
    {message && <div className="analysis-error" role="alert"><AlertTriangle size={16} />{message}</div>}
    {result && <ReviewResults result={result} findings={filteredFindings} files={files} severity={severity} category={category} file={file} onSeverity={setSeverity} onCategory={setCategory} onFile={setFile} />}
  </section>;
}

function ReviewResults({ result, findings, files, severity, category, file, onSeverity, onCategory, onFile }: { result: ReviewResponse; findings: ReviewFinding[]; files: string[]; severity: FilterValue; category: FilterValue; file: FilterValue; onSeverity: (value: string) => void; onCategory: (value: string) => void; onFile: (value: string) => void }) {
  return <div className="review-results">
    <div className="review-summary"><div className="review-summary-copy"><span className="section-label">Review result</span><h2>{result.total_findings === 0 ? "No issues were identified by the configured review agents." : result.summary}</h2><span>{result.agents_completed.length} agent{result.agents_completed.length === 1 ? "" : "s"} completed · {result.agents_failed.length} failed</span></div><div className="finding-total"><strong>{result.total_findings}</strong><span>findings</span></div></div>
    <div className="severity-grid"><SummaryCard label="Critical" value={result.critical_count} tone="critical" /><SummaryCard label="High" value={result.high_count} tone="high" /><SummaryCard label="Medium" value={result.medium_count} tone="medium" /><SummaryCard label="Low" value={result.low_count} tone="low" /><SummaryCard label="Info" value={result.info_count} tone="info" /></div>
    {result.total_findings > 0 && <div className="review-filterbar"><Filter size={15} /><Select label="Severity" value={severity} values={["all", "critical", "high", "medium", "low", "info"]} onChange={onSeverity} /><Select label="Category" value={category} values={["all", "security", "quality", "performance"]} onChange={onCategory} /><Select label="File" value={file} values={["all", ...files]} onChange={onFile} /></div>}
    <div className="finding-list">{findings.length === 0 && result.total_findings > 0 ? <div className="filtered-empty">No findings match the current filters.</div> : findings.map((finding, index) => <FindingCard finding={finding} key={`${finding.filename}-${finding.start_line}-${finding.title}-${index}`} />)}</div>
  </div>;
}

function SummaryCard({ label, value, tone }: { label: string; value: number; tone: string }) { return <div className={`summary-card ${tone}`}><strong>{value}</strong><span>{label}</span></div>; }
function Select({ label, value, values, onChange }: { label: string; value: string; values: string[]; onChange: (value: string) => void }) { return <label className="filter-select"><span>{label}</span><select value={value} onChange={(event) => onChange(event.target.value)}>{values.map((option) => <option value={option} key={option}>{option === "all" ? `All ${label.toLowerCase()}s` : option}</option>)}</select></label>; }
function FindingCard({ finding }: { finding: ReviewFinding }) { return <article className="finding-card"><div className="finding-card-top"><div className="finding-tags"><span className={`severity-badge ${finding.severity}`}>{finding.severity}</span><span className="category-tag">{finding.category}</span></div><span className="finding-location">{finding.filename}:{finding.start_line}-{finding.end_line}</span></div><h3>{finding.title}</h3><p>{finding.description}</p><div className="recommendation"><CheckCircle2 size={15} /><span><strong>Recommendation</strong>{finding.recommendation}</span></div></article>; }

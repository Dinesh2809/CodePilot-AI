import { FormEvent, useState } from "react";
import { AlertTriangle, ArrowUpRight, LoaderCircle, Search } from "lucide-react";
import { ApiRequestError, searchRepository } from "../services/api";
import type { RepositoryIngestionResponse, SearchResponse } from "../types/repository";

type SearchPanelProps = { repository: RepositoryIngestionResponse | null };

export function SearchPanel({ repository }: SearchPanelProps) {
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<"idle" | "loading" | "error">("idle");
  const [message, setMessage] = useState<string | null>(null);
  const [result, setResult] = useState<SearchResponse | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!repository || !query.trim() || status === "loading") return;
    setStatus("loading"); setMessage(null);
    try { setResult(await searchRepository(query.trim())); setStatus("idle"); }
    catch (error) { setStatus("error"); setMessage(error instanceof ApiRequestError ? error.message : "The code search could not be completed. Please try again."); }
  }

  return <section className="analysis-panel search-panel"><form className="search-form" onSubmit={submit}><div className="search-input-wrap"><Search size={18} /><input aria-label="Search indexed code" placeholder="Where is authentication handled?" value={query} onChange={(event) => setQuery(event.target.value)} /><button type="submit" disabled={!repository || !query.trim() || status === "loading"} aria-label="Search code">{status === "loading" ? <LoaderCircle className="spin" size={17} /> : <ArrowUpRight size={17} />}</button></div></form>{!repository && <div className="context-note"><AlertTriangle size={16} /> Upload a repository before searching its code.</div>}{message && <div className="analysis-error" role="alert"><AlertTriangle size={16} />{message}</div>}{result && <div className="search-results"><div className="results-heading"><div><span className="section-label">Semantic matches</span><h2>{result.result_count === 0 ? "No matching code was found for this query." : `${result.result_count} relevant result${result.result_count === 1 ? "" : "s"}`}</h2></div><span className="query-pill">{result.query}</span></div>{result.results.map((item) => <article className="search-result-card" key={item.chunk_id}><div className="result-meta"><strong>{item.filename}</strong><span>{item.chunk_type} · {item.name} · lines {item.start_line}-{item.end_line}</span><span className="similarity">Similarity: {item.similarity.toFixed(2)}</span></div><pre><code>{item.content}</code></pre></article>)}</div>}</section>;
}

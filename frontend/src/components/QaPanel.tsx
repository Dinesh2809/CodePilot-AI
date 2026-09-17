import { FormEvent, useState } from "react";
import { AlertTriangle, ArrowUpRight, BrainCircuit, LoaderCircle, RotateCcw } from "lucide-react";
import { ApiRequestError, askRepository } from "../services/api";
import type { AskResponse, RepositoryIngestionResponse } from "../types/repository";

type QaPanelProps = { repository: RepositoryIngestionResponse | null };
type Message = { question: string; response: AskResponse };

export function QaPanel({ repository }: QaPanelProps) {
  const [question, setQuestion] = useState("");
  const [status, setStatus] = useState<"idle" | "loading" | "error">("idle");
  const [message, setMessage] = useState<string | null>(null);
  const [history, setHistory] = useState<Message[]>([]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!repository || !question.trim() || status === "loading") return;
    const currentQuestion = question.trim();
    setStatus("loading"); setMessage(null);
    try { const response = await askRepository(currentQuestion); setHistory((items) => [...items, { question: currentQuestion, response }]); setQuestion(""); setStatus("idle"); }
    catch (error) { setStatus("error"); setMessage(error instanceof ApiRequestError ? error.message : "The AI assistant is temporarily unavailable. Please try again."); }
  }

  return <section className="analysis-panel qa-panel"><div className="qa-intro"><div className="qa-icon"><BrainCircuit size={21} /></div><div><span className="section-label">Grounded assistant</span><h2>Ask about the indexed code.</h2><p>Answers are generated from the repository context available to CodePilot.</p></div></div>{!repository && <div className="context-note"><AlertTriangle size={16} /> Upload a repository before asking questions about its code.</div>}<form className="qa-form" onSubmit={submit}><textarea aria-label="Ask about your code" placeholder="How does authentication work?" value={question} onChange={(event) => setQuestion(event.target.value)} disabled={!repository || status === "loading"} rows={4} /><div className="qa-form-footer"><span>{status === "loading" ? <><LoaderCircle className="spin" size={15} /> Analyzing your repository...</> : "Answers stay grounded in indexed context."}</span><button className="primary-button" type="submit" disabled={!repository || !question.trim() || status === "loading"}>{status === "loading" ? "Thinking..." : "Ask CodePilot"}<ArrowUpRight size={16} /></button></div></form>{message && <div className="analysis-error" role="alert"><AlertTriangle size={16} />{message}</div>}<div className="qa-history">{history.map((item, index) => <article className="qa-message" key={`${item.question}-${index}`}><div className="question-bubble">{item.question}</div><div className="answer-bubble"><span className="answer-label">CodePilot answer</span><p>{item.response.answer || "No answer was returned for this question."}</p>{item.response.retrieved_results.length > 0 && <div className="answer-sources"><span>Retrieved context</span>{item.response.retrieved_results.map((source) => <small key={source.chunk_id}>{source.filename} · lines {source.start_line}-{source.end_line}</small>)}</div>}</div></article>)}</div>{history.length > 0 && <button className="text-button reset-qa" type="button" onClick={() => setHistory([])}><RotateCcw size={14} /> Clear conversation</button>}</section>;
}

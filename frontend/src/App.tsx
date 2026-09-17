import { useState } from "react";
import {
  Activity,
  ArrowUpRight,
  BrainCircuit,
  ChevronRight,
  CircleHelp,
  Code2,
  FileCode2,
  FolderGit2,
  LayoutDashboard,
  Search,
  Settings2,
  ShieldCheck,
  Sparkles,
  UploadCloud,
} from "lucide-react";
import { RepositoryUpload } from "./components/RepositoryUpload";
import { ReviewPanel } from "./components/ReviewPanel";
import { SearchPanel } from "./components/SearchPanel";
import { QaPanel } from "./components/QaPanel";
import type { RepositoryIngestionResponse, ReviewResponse } from "./types/repository";

type View = "overview" | "repository" | "search" | "qa" | "review";

type NavItem = {
  id: View;
  label: string;
  hint: string;
  icon: typeof LayoutDashboard;
};

const navigation: NavItem[] = [
  { id: "overview", label: "Overview", hint: "Workspace pulse", icon: LayoutDashboard },
  { id: "repository", label: "Repository", hint: "Upload and index", icon: FolderGit2 },
  { id: "search", label: "Code search", hint: "Find by meaning", icon: Search },
  { id: "qa", label: "Ask CodePilot", hint: "Grounded answers", icon: BrainCircuit },
  { id: "review", label: "Code review", hint: "Quality signals", icon: ShieldCheck },
];

const signals = [
  { label: "Indexed files", value: "0", detail: "Upload a repository to begin", tone: "mint" },
  { label: "Searchable chunks", value: "0", detail: "Semantic index is waiting", tone: "lavender" },
  { label: "Open findings", value: "—", detail: "No review has been run", tone: "peach" },
];

function App() {
  const [activeView, setActiveView] = useState<View>("overview");
  const [repositoryResult, setRepositoryResult] = useState<RepositoryIngestionResponse | null>(null);
  const [reviewResult, setReviewResult] = useState<ReviewResponse | null>(null);
  const activeItem = navigation.find((item) => item.id === activeView) ?? navigation[0];
  const ActiveIcon = activeItem.icon;

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-lockup">
          <div className="brand-mark"><Code2 size={19} strokeWidth={2.4} /></div>
          <div>
            <strong>CodePilot</strong>
            <span>AI workbench</span>
          </div>
        </div>

        <div className="workspace-switcher" aria-label="Current workspace">
          <div className="workspace-avatar">CP</div>
          <div className="workspace-copy">
            <strong>Personal workspace</strong>
            <span>Local project</span>
          </div>
          <ChevronRight size={15} />
        </div>

        <nav className="primary-nav" aria-label="Primary navigation">
          <span className="nav-label">Workspace</span>
          {navigation.map((item) => {
            const Icon = item.icon;
            return (
              <button
                className={`nav-item ${activeView === item.id ? "is-active" : ""}`}
                key={item.id}
                onClick={() => setActiveView(item.id)}
                type="button"
              >
                <Icon size={17} />
                <span>{item.label}</span>
                {activeView === item.id && <span className="active-dot" />}
              </button>
            );
          })}
        </nav>

        <div className="sidebar-footer">
          <div className="system-status"><span className="status-dot" />Backend ready</div>
          <button className="nav-item" type="button"><Settings2 size={17} /><span>Settings</span></button>
          <button className="nav-item" type="button"><CircleHelp size={17} /><span>Help center</span></button>
        </div>
      </aside>

      <main className="main-content">
        <header className="topbar">
          <div className="breadcrumb"><span>Workspace</span><ChevronRight size={14} /><strong>{activeItem.label}</strong></div>
          <div className="topbar-actions">
            <span className="environment-pill"><span className="status-dot" />Development</span>
            <button className="icon-button" aria-label="Open help" title="Open help" type="button"><CircleHelp size={18} /></button>
            <div className="profile-chip"><span>AS</span><strong>AS</strong></div>
          </div>
        </header>

        <div className="content-wrap">
          <section className="page-heading">
            <div>
              <div className="eyebrow"><ActiveIcon size={14} /> {activeItem.hint}</div>
              <h1>{activeView === "overview" ? "Good code starts with context." : activeItem.label}</h1>
              <p>{getPageDescription(activeView)}</p>
            </div>
            <button className="secondary-button" type="button" onClick={() => setActiveView("repository")}>
              <UploadCloud size={16} /> Add repository
            </button>
          </section>

          {activeView === "overview" ? (
            <Overview onNavigate={setActiveView} repositoryResult={repositoryResult} />
          ) : activeView === "repository" ? (
            <RepositoryUpload onComplete={setRepositoryResult} />
          ) : activeView === "review" ? (
            <ReviewPanel repository={repositoryResult} result={reviewResult} onResult={setReviewResult} />
          ) : activeView === "search" ? (
            <SearchPanel repository={repositoryResult} />
          ) : activeView === "qa" ? (
            <QaPanel repository={repositoryResult} />
          ) : (
            <EmptyWorkspace view={activeView} onNavigate={setActiveView} />
          )}
        </div>
      </main>
    </div>
  );
}

function Overview({
  onNavigate,
  repositoryResult,
}: {
  onNavigate: (view: View) => void;
  repositoryResult: RepositoryIngestionResponse | null;
}) {
  const indexedFiles = repositoryResult?.statistics.successful_files ?? 0;
  const indexedChunks = repositoryResult?.repository.chunk_count ?? 0;
  return (
    <>
      <section className="signal-grid" aria-label="Workspace signals">
        {signals.map((signal) => (
          <article className={`signal-card ${signal.tone}`} key={signal.label}>
            <div className="signal-card-top"><span>{signal.label}</span><ArrowUpRight size={16} /></div>
            <strong>{signal.label === "Indexed files" && indexedFiles > 0 ? indexedFiles : signal.label === "Searchable chunks" && indexedChunks > 0 ? indexedChunks : signal.value}</strong>
            <small>{signal.label === "Indexed files" && indexedFiles > 0 ? "Ready for exploration" : signal.label === "Searchable chunks" && indexedChunks > 0 ? "Semantic index is ready" : signal.detail}</small>
          </article>
        ))}
      </section>

      <section className="dashboard-grid">
        <article className="welcome-panel">
          <div className="panel-kicker"><Sparkles size={16} /> Your analysis desk</div>
          <h2>Bring a codebase into focus.</h2>
          <p>Upload a few files or a repository, then move from structure to meaning with semantic search, grounded Q&A, and focused review.</p>
          <button className="primary-button" type="button" onClick={() => onNavigate("repository")}><UploadCloud size={17} /> Upload files</button>
          <div className="panel-stamp"><Activity size={15} /> Analysis pipeline ready</div>
        </article>

        <article className="activity-panel">
          <div className="section-heading"><div><span className="section-label">Recent activity</span><h2>Nothing here yet</h2></div><Activity size={19} /></div>
          <div className="empty-activity"><div className="empty-icon"><FileCode2 size={21} /></div><p>Upload your first repository to see processing activity here.</p><button type="button" onClick={() => onNavigate("repository")}>Get started <ArrowUpRight size={14} /></button></div>
        </article>
      </section>

      <section className="workflow-strip">
        <div><span className="section-label">A quiet path from code to clarity</span><h2>One workspace, four useful moves.</h2></div>
        <div className="workflow-steps">
          <WorkflowStep number="01" title="Index" detail="Parse and embed" />
          <WorkflowStep number="02" title="Explore" detail="Search by intent" />
          <WorkflowStep number="03" title="Ask" detail="Stay grounded" />
          <WorkflowStep number="04" title="Review" detail="Find what matters" />
        </div>
      </section>
    </>
  );
}

function WorkflowStep({ number, title, detail }: { number: string; title: string; detail: string }) {
  return <div className="workflow-step"><span>{number}</span><strong>{title}</strong><small>{detail}</small></div>;
}

function EmptyWorkspace({ view, onNavigate }: { view: View; onNavigate: (view: View) => void }) {
  const isRepository = view === "repository";
  return <section className="empty-workspace"><div className="empty-workspace-icon">{isRepository ? <UploadCloud size={25} /> : <Sparkles size={25} />}</div><h2>{isRepository ? "Your repository has a blank canvas." : "This view is ready for your code."}</h2><p>{isRepository ? "The upload flow will turn Python files into a searchable, reviewable workspace." : "Upload and index a repository first, then this workspace will fill with useful context."}</p><button className="primary-button" type="button" onClick={() => onNavigate(isRepository ? "overview" : "repository")}>{isRepository ? "Back to overview" : "Upload a repository"} <ArrowUpRight size={16} /></button></section>;
}

function getPageDescription(view: View) {
  switch (view) {
    case "repository": return "Bring files into a project and prepare them for analysis.";
    case "search": return "Find the exact context you need without guessing filenames.";
    case "qa": return "Ask questions and keep every answer grounded in your indexed code.";
    case "review": return "See security, quality, and performance signals in one place.";
    default: return "A focused space for indexing, exploring, and reviewing your codebase.";
  }
}

export default App;

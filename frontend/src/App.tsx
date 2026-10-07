import { useState } from "react";
import {
  Activity,
  ArrowUpRight,
  Bell,
  BrainCircuit,
  ChevronDown,
  ChevronRight,
  CircleHelp,
  Code2,
  FileCode2,
  FolderGit2,
  LayoutDashboard,
  Plus,
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

type View = "home" | "projects" | "repository" | "search" | "qa" | "review";

type NavItem = {
  id: View;
  label: string;
  hint: string;
  icon: typeof LayoutDashboard;
};

const navigation: NavItem[] = [
  { id: "home", label: "Home", hint: "Workspace dashboard", icon: LayoutDashboard },
  { id: "projects", label: "Projects", hint: "Repositories", icon: FolderGit2 },
  { id: "search", label: "Code Search", hint: "Find by meaning", icon: Search },
  { id: "qa", label: "Ask Code", hint: "Grounded answers", icon: BrainCircuit },
  { id: "review", label: "Reviews", hint: "Quality signals", icon: ShieldCheck },
];

const capabilityItems = [
  { title: "Security analysis", detail: "Flag unsafe patterns and risky dependencies", icon: ShieldCheck },
  { title: "Code quality", detail: "Surface maintainability and consistency issues", icon: Activity },
  { title: "Performance analysis", detail: "Spot hot paths and inefficiencies", icon: Sparkles },
  { title: "Code understanding", detail: "Map architecture and ownership quickly", icon: Code2 },
  { title: "Semantic code search", detail: "Find the right context by intent", icon: Search },
  { title: "RAG-powered answers", detail: "Ground answers in the indexed repository", icon: BrainCircuit },
];

const signals = [
  { label: "Indexed files", value: "0", detail: "Upload a repository to begin", tone: "mint" },
  { label: "Searchable chunks", value: "0", detail: "Semantic index is waiting", tone: "lavender" },
  { label: "Open findings", value: "—", detail: "No review has been run", tone: "peach" },
];

function App() {
  const [activeView, setActiveView] = useState<View>("home");
  const [repositoryResult, setRepositoryResult] = useState<RepositoryIngestionResponse | null>(null);
  const [reviewResult, setReviewResult] = useState<ReviewResponse | null>(null);
  const activeItem = navigation.find((item) => item.id === activeView) ?? navigation[0];
  const ActiveIcon = activeItem.icon;

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-lockup">
          <div className="brand-mark"><Code2 size={18} strokeWidth={2.4} /></div>
          <div>
            <strong>CodePilot</strong>
            <span>AI workbench</span>
          </div>
        </div>

        <button className="new-review-button" type="button" onClick={() => setActiveView("repository")}>
          <Plus size={16} /> New Review
        </button>

        <div className="workspace-switcher" aria-label="Current workspace">
          <div className="workspace-avatar">CP</div>
          <div className="workspace-copy">
            <strong>Personal workspace</strong>
            <span>Local project</span>
          </div>
          <ChevronDown size={15} />
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
          <div className="breadcrumb">
            <span>Workspace</span>
            <ChevronRight size={14} />
            <strong>{activeItem.label}</strong>
          </div>

          <div className="topbar-actions">
            <div className="project-pill">
              <span className="status-dot" />
              {repositoryResult ? "Repository ready" : "No project selected"}
            </div>
            <button className="search-pill" type="button">
              <Search size={14} /> Search workspace
            </button>
            <button className="icon-button" aria-label="Notifications" title="Notifications" type="button">
              <Bell size={17} />
            </button>
            <div className="profile-chip"><span>AS</span><strong>AS</strong></div>
          </div>
        </header>

        <div className="content-wrap">
          <section className="page-heading">
            <div>
              <div className="eyebrow"><ActiveIcon size={14} /> {activeItem.hint}</div>
              <h1>{activeView === "home" ? "Understand your codebase.\nReview it with AI." : activeItem.label}</h1>
              <p>{getPageDescription(activeView)}</p>
            </div>
            <button className="secondary-button" type="button" onClick={() => setActiveView("repository")}>
              <UploadCloud size={16} /> New project
            </button>
          </section>

          {activeView === "home" ? (
            <HomePage onNavigate={setActiveView} repositoryResult={repositoryResult} />
          ) : activeView === "projects" ? (
            <ProjectsPage onNavigate={setActiveView} repositoryResult={repositoryResult} />
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

function HomePage({
  onNavigate,
  repositoryResult,
}: {
  onNavigate: (view: View) => void;
  repositoryResult: RepositoryIngestionResponse | null;
}) {
  const indexedFiles = repositoryResult?.statistics.successful_files ?? 0;
  const indexedChunks = repositoryResult?.repository.chunk_count ?? 0;

  return (
    <div className="home-page">
      <section className="hero-panel">
        <div className="hero-copy">
          <div className="eyebrow"><Sparkles size={14} /> Developer workspace</div>
          <h1>Understand your codebase.<br />Review it with AI.</h1>
          <p>
            CodePilot adds structure, semantics, and review context to your repository so you can move
            from code understanding to code quality without losing engineering flow.
          </p>

          <div className="hero-actions">
            <button className="primary-button" type="button" onClick={() => onNavigate("repository")}>
              <UploadCloud size={17} /> New Code Review
            </button>
            <button className="secondary-button" type="button" onClick={() => onNavigate("projects")}>
              Explore Projects
            </button>
          </div>
        </div>

        <div className="hero-metrics">
          <div className="metric-box">
            <span>Indexed files</span>
            <strong>{indexedFiles}</strong>
            <small>{indexedFiles > 0 ? "Ready for analysis" : "Waiting for upload"}</small>
          </div>
          <div className="metric-box">
            <span>Searchable chunks</span>
            <strong>{indexedChunks}</strong>
            <small>{indexedChunks > 0 ? "Semantic index live" : "No indexed data yet"}</small>
          </div>
        </div>
      </section>

      <section className="signal-grid" aria-label="Workspace signals">
        {signals.map((signal) => (
          <article className={`signal-card ${signal.tone}`} key={signal.label}>
            <div className="signal-card-top">
              <span>{signal.label}</span>
              <ArrowUpRight size={16} />
            </div>
            <strong>
              {signal.label === "Indexed files" && indexedFiles > 0
                ? indexedFiles
                : signal.label === "Searchable chunks" && indexedChunks > 0
                  ? indexedChunks
                  : signal.value}
            </strong>
            <small>
              {signal.label === "Indexed files" && indexedFiles > 0
                ? "Ready for exploration"
                : signal.label === "Searchable chunks" && indexedChunks > 0
                  ? "Semantic index is ready"
                  : signal.detail}
            </small>
          </article>
        ))}
      </section>

      <section className="capability-grid" aria-label="Product capabilities">
        {capabilityItems.map(({ title, detail, icon: Icon }) => (
          <article className="capability-card" key={title}>
            <div className="capability-icon"><Icon size={16} /></div>
            <strong>{title}</strong>
            <p>{detail}</p>
          </article>
        ))}
      </section>
    </div>
  );
}

function ProjectsPage({
  onNavigate,
  repositoryResult,
}: {
  onNavigate: (view: View) => void;
  repositoryResult: RepositoryIngestionResponse | null;
}) {
  const projectRows = repositoryResult
    ? [
        {
          name: "Current repository",
          language: "Python",
          files: repositoryResult.statistics.successful_files,
          chunks: repositoryResult.repository.chunk_count,
          lastAnalyzed: repositoryResult.success ? "Just now" : "Waiting",
          status: repositoryResult.success ? "Indexed" : "Processing",
        },
      ]
    : [];

  return (
    <section className="projects-page">
      <div className="section-header">
        <div>
          <span className="section-label">Projects</span>
          <h2>Repository workspace</h2>
        </div>
        <button className="primary-button" type="button" onClick={() => onNavigate("repository")}>
          <Plus size={15} /> New Project
        </button>
      </div>

      {projectRows.length === 0 ? (
        <div className="empty-projects">
          <div className="empty-projects-icon"><FolderGit2 size={24} /></div>
          <h3>No projects yet</h3>
          <p>Upload a repository to start understanding your codebase.</p>
          <button className="primary-button" type="button" onClick={() => onNavigate("repository")}>
            Create Project
          </button>
        </div>
      ) : (
        <div className="project-table-wrap">
          <table className="project-table">
            <thead>
              <tr>
                <th>Project</th>
                <th>Files</th>
                <th>Chunks</th>
                <th>Last analyzed</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {projectRows.map((project) => (
                <tr key={project.name} onClick={() => onNavigate("search")}>
                  <td>
                    <div className="project-info">
                      <div className="project-badge">PY</div>
                      <div>
                        <strong>{project.name}</strong>
                        <span>{project.language}</span>
                      </div>
                    </div>
                  </td>
                  <td>{project.files}</td>
                  <td>{project.chunks}</td>
                  <td>{project.lastAnalyzed}</td>
                  <td>
                    <span className={`status-pill ${project.status === "Indexed" ? "success" : "muted"}`}>
                      {project.status}
                    </span>
                  </td>
                  <td>
                    <button className="table-action" type="button">
                      Open
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function EmptyWorkspace({ view, onNavigate }: { view: View; onNavigate: (view: View) => void }) {
  const isRepository = view === "repository";
  return (
    <section className="empty-workspace">
      <div className="empty-workspace-icon">{isRepository ? <UploadCloud size={25} /> : <Sparkles size={25} />}</div>
      <h2>{isRepository ? "Your repository has a blank canvas." : "This view is ready for your code."}</h2>
      <p>
        {isRepository
          ? "The upload flow will turn Python files into a searchable, reviewable workspace."
          : "Upload and index a repository first, then this workspace will fill with useful context."}
      </p>
      <button className="primary-button" type="button" onClick={() => onNavigate(isRepository ? "home" : "repository")}>
        {isRepository ? "Back to overview" : "Upload a repository"} <ArrowUpRight size={16} />
      </button>
    </section>
  );
}

function getPageDescription(view: View) {
  switch (view) {
    case "home":
      return "A focused space for indexing, exploring, and reviewing your codebase.";
    case "projects":
      return "Manage repositories, review activity, and keep your engineering context organized.";
    case "repository":
      return "Bring files into a project and prepare them for analysis.";
    case "search":
      return "Find the exact context you need without guessing filenames.";
    case "qa":
      return "Ask questions and keep every answer grounded in your indexed code.";
    case "review":
      return "See security, quality, and performance signals in one place.";
    default:
      return "A focused space for indexing, exploring, and reviewing your codebase.";
  }
}

export default App;

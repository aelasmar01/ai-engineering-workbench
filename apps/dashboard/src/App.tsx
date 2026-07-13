const foundationItems = [
  "Local API health endpoint",
  "CLI foundation commands",
  "Dashboard application shell",
  "Backend and frontend test harnesses",
  "CI-ready quality checks"
];

const futureWorkflow = [
  "Project registry",
  "Task backlog",
  "Git worktrees",
  "Agent sessions",
  "Validation evidence",
  "PR readiness",
  "Portfolio export"
];

export function App() {
  return (
    <main className="shell" aria-labelledby="page-title">
      <section className="header-band">
        <div>
          <p className="eyebrow">Milestone 0</p>
          <h1 id="page-title">AI Engineering Workbench</h1>
          <p className="summary">
            Local-first foundation for a deterministic engineering delivery control plane.
          </p>
        </div>
        <div className="status-panel" aria-label="Current implementation status">
          <span className="status-label">Current scope</span>
          <strong>Foundation only</strong>
        </div>
      </section>

      <section className="grid" aria-label="Workbench foundation status">
        <article>
          <h2>Implemented foundation</h2>
          <ul>
            {foundationItems.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </article>

        <article>
          <h2>Not implemented yet</h2>
          <ul>
            {futureWorkflow.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </article>
      </section>
    </main>
  );
}

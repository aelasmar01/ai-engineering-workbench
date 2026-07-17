import { QueryClient, QueryClientProvider, useMutation, useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";

const queryClient = new QueryClient();
const apiBaseUrl = "http://127.0.0.1:8787";

type TodaySummary = {
  daily_pr_target: number;
  pull_requests_created_today: number;
  pull_requests_merged_today: number;
  tasks_ready_to_start: number;
  active_tasks: number;
  tasks_requiring_human_action: number;
  failed_checks: number;
  blocked_tasks: number;
};

type ProjectSummary = {
  id: string;
  name: string;
  status: string;
  health_status: string;
  active_task_count: number;
  open_pr_count: number;
  last_validation: string | null;
  portfolio_categories: string[];
};

type AcceptanceRow = {
  id: string;
  criterion_text: string;
  status: string;
  evidence_type: string;
  evidence_reference: string;
};

type WorktreeSummary = {
  id: string;
  path: string;
  branch: string;
  base_branch: string;
  status: string;
  date_created: string | null;
};

type PullRequestSummary = {
  id: string;
  task_id: string;
  repository: string;
  branch: string;
  number: number;
  url: string;
  status: string;
  created_time: string | null;
};

type TaskSummary = {
  id: string;
  project_id: string;
  title: string;
  objective: string;
  type: string;
  priority: string;
  status: string;
  constraints: string[];
  expected_paths: string[];
  required_checks: string[];
  acceptance_criteria: AcceptanceRow[];
  worktree: WorktreeSummary | null;
  branch: string | null;
  assigned_agent: string | null;
  agent_session_count: number;
  validation_status: string;
  diff_summary: {
    review_finding_count: number;
    unresolved_finding_count: number;
  };
  pull_request: PullRequestSummary | null;
  available_actions: string[];
};

type SessionSummary = {
  id: string;
  agent: string;
  role: string;
  task_id: string;
  task_title: string;
  start_time: string | null;
  last_activity: string | null;
  status: string;
  worktree_id: string;
  changed_file_count: number | null;
  latest_event: string;
};

type ValidationSummary = {
  id: string;
  task_id: string;
  run_group_id: string | null;
  task_title: string;
  check_name: string;
  status: string;
  duration_seconds: number | null;
  exit_code: number | null;
  output_path: string;
};

type FindingSummary = {
  id: string;
  task_id: string;
  task_title: string;
  severity: string;
  category: string;
  file: string;
  line: number | null;
  description: string;
  recommendation: string;
  status: string;
};

type MetricValue = number | string | null | { value: number | null; status: string };

type DashboardState = {
  generated_at: string;
  today: TodaySummary;
  projects: ProjectSummary[];
  tasks: TaskSummary[];
  sessions: SessionSummary[];
  validation: ValidationSummary[];
  review: {
    findings: FindingSummary[];
    acceptance: AcceptanceRow[];
  };
  metrics: Record<string, MetricValue>;
};

type View = "today" | "projects" | "task" | "sessions" | "validation" | "review" | "metrics";

const views: Array<{ id: View; label: string }> = [
  { id: "today", label: "Today" },
  { id: "projects", label: "Projects" },
  { id: "task", label: "Task Detail" },
  { id: "sessions", label: "Sessions" },
  { id: "validation", label: "Validation" },
  { id: "review", label: "Review" },
  { id: "metrics", label: "Metrics" }
];

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <Dashboard />
    </QueryClientProvider>
  );
}

function Dashboard() {
  const [view, setView] = useState<View>("today");
  const [selectedTaskId, setSelectedTaskId] = useState<string>("");
  const stateQuery = useQuery({
    queryKey: ["dashboard-state"],
    queryFn: fetchDashboardState,
    refetchInterval: 10_000
  });
  const state = stateQuery.data;
  const selectedTask = useMemo(() => {
    if (!state) {
      return null;
    }
    return state.tasks.find((task) => task.id === selectedTaskId) ?? state.tasks[0] ?? null;
  }, [selectedTaskId, state]);

  return (
    <main className="shell" aria-labelledby="page-title">
      <header className="topbar">
        <div>
          <p className="eyebrow">Milestone 9</p>
          <h1 id="page-title">AI Engineering Workbench</h1>
        </div>
        <div className="api-status" data-state={stateQuery.status}>
          <span>{stateQuery.isFetching ? "Refreshing" : stateQuery.status}</span>
          <strong>{state ? formatDate(state.generated_at) : "Local API"}</strong>
        </div>
      </header>

      <nav className="tabs" aria-label="Dashboard views">
        {views.map((item) => (
          <button
            aria-current={view === item.id ? "page" : undefined}
            className="tab"
            key={item.id}
            onClick={() => setView(item.id)}
            type="button"
          >
            {item.label}
          </button>
        ))}
      </nav>

      {stateQuery.isError ? (
        <section className="empty-state" role="alert">
          <h2>API unavailable</h2>
          <p>Start the local API with make api, then refresh this dashboard.</p>
        </section>
      ) : stateQuery.isLoading || !state ? (
        <section className="empty-state">
          <h2>Loading dashboard</h2>
        </section>
      ) : (
        <section className="content">
          {view === "today" && <TodayView today={state.today} tasks={state.tasks} />}
          {view === "projects" && <ProjectsView projects={state.projects} />}
          {view === "task" && (
            <TaskView
              onSelectedTaskChange={setSelectedTaskId}
              selectedTask={selectedTask}
              tasks={state.tasks}
            />
          )}
          {view === "sessions" && <SessionsView sessions={state.sessions} />}
          {view === "validation" && <ValidationView validation={state.validation} />}
          {view === "review" && (
            <ReviewView findings={state.review.findings} selectedTask={selectedTask} />
          )}
          {view === "metrics" && <MetricsView metrics={state.metrics} />}
        </section>
      )}
    </main>
  );
}

function TodayView({ today, tasks }: { today: TodaySummary; tasks: TaskSummary[] }) {
  const humanActionTasks = tasks.filter(
    (task) => task.status === "blocked" || task.validation_status === "failed"
  );
  return (
    <>
      <section className="metric-grid" aria-label="Today metrics">
        <Metric label="Daily PR target" value={today.daily_pr_target} />
        <Metric label="PRs created today" value={today.pull_requests_created_today} />
        <Metric label="PRs merged today" value={today.pull_requests_merged_today} />
        <Metric label="Ready tasks" value={today.tasks_ready_to_start} />
        <Metric label="Active tasks" value={today.active_tasks} />
        <Metric label="Human action" value={today.tasks_requiring_human_action} />
        <Metric label="Failed checks" value={today.failed_checks} tone="danger" />
        <Metric label="Blocked tasks" value={today.blocked_tasks} tone="warning" />
      </section>
      <DataTable
        columns={["Task", "Project", "Status", "Validation", "Priority"]}
        rows={humanActionTasks.map((task) => [
          task.title,
          task.project_id,
          task.status,
          task.validation_status,
          task.priority
        ])}
        title="Needs attention"
      />
    </>
  );
}

function ProjectsView({ projects }: { projects: ProjectSummary[] }) {
  return (
    <DataTable
      columns={["Project", "Health", "Active tasks", "Open PRs", "Last validation", "Categories"]}
      rows={projects.map((project) => [
        project.name,
        project.health_status,
        project.active_task_count.toString(),
        project.open_pr_count.toString(),
        formatDate(project.last_validation),
        project.portfolio_categories.join(", ")
      ])}
      title="Registered projects"
    />
  );
}

function TaskView({
  onSelectedTaskChange,
  selectedTask,
  tasks
}: {
  onSelectedTaskChange: (taskId: string) => void;
  selectedTask: TaskSummary | null;
  tasks: TaskSummary[];
}) {
  const actionMutation = useTaskAction();
  if (!selectedTask) {
    return <EmptyTable title="Task detail" />;
  }
  return (
    <div className="split">
      <section className="panel">
        <div className="panel-header">
          <h2>Tasks</h2>
          <select
            aria-label="Selected task"
            onChange={(event) => onSelectedTaskChange(event.target.value)}
            value={selectedTask.id}
          >
            {tasks.map((task) => (
              <option key={task.id} value={task.id}>
                {task.id} - {task.title}
              </option>
            ))}
          </select>
        </div>
        <dl className="detail-list">
          <div>
            <dt>Status</dt>
            <dd>{selectedTask.status}</dd>
          </div>
          <div>
            <dt>Branch</dt>
            <dd>{selectedTask.branch ?? "No worktree"}</dd>
          </div>
          <div>
            <dt>Agent</dt>
            <dd>{selectedTask.assigned_agent ?? "Unassigned"}</dd>
          </div>
          <div>
            <dt>Validation</dt>
            <dd>{selectedTask.validation_status}</dd>
          </div>
          <div>
            <dt>Review findings</dt>
            <dd>{selectedTask.diff_summary.unresolved_finding_count} open</dd>
          </div>
        </dl>
        <p className="objective">{selectedTask.objective}</p>
        <div className="actions" aria-label="Task actions">
          {selectedTask.available_actions.map((action) => (
            <button
              disabled={actionMutation.isPending}
              key={action}
              onClick={() => actionMutation.mutate({ action, taskId: selectedTask.id })}
              type="button"
            >
              {action}
            </button>
          ))}
        </div>
        {actionMutation.isError ? (
          <p className="muted" role="alert">
            {actionMutation.error.message}
          </p>
        ) : null}
      </section>
      <section className="panel">
        <h2>Acceptance</h2>
        <DataTable
          columns={["Criterion", "Status", "Evidence"]}
          rows={selectedTask.acceptance_criteria.map((criterion) => [
            criterion.criterion_text,
            criterion.status,
            criterion.evidence_reference
          ])}
        />
      </section>
    </div>
  );
}

function SessionsView({ sessions }: { sessions: SessionSummary[] }) {
  return (
    <DataTable
      columns={["Agent", "Role", "Task", "Start", "Activity", "Status", "Event"]}
      rows={sessions.map((session) => [
        session.agent,
        session.role,
        session.task_title || session.task_id,
        formatDate(session.start_time),
        formatDate(session.last_activity),
        session.status,
        session.latest_event
      ])}
      title="Agent sessions"
    />
  );
}

function ValidationView({ validation }: { validation: ValidationSummary[] }) {
  return (
    <DataTable
      columns={["Check", "Task", "Status", "Duration", "Exit", "Raw output"]}
      rows={validation.map((run) => [
        run.check_name,
        run.task_title || run.task_id,
        run.status,
        run.duration_seconds === null ? "" : `${run.duration_seconds}s`,
        run.exit_code === null ? "" : run.exit_code.toString(),
        run.output_path
      ])}
      title="Validation runs"
    />
  );
}

function ReviewView({
  findings,
  selectedTask
}: {
  findings: FindingSummary[];
  selectedTask: TaskSummary | null;
}) {
  const selectedFindings = selectedTask
    ? findings.filter((finding) => finding.task_id === selectedTask.id)
    : findings;
  return (
    <div className="split">
      <DataTable
        columns={["Severity", "Category", "Status", "File", "Recommendation"]}
        rows={selectedFindings.map((finding) => [
          finding.severity,
          finding.category,
          finding.status,
          finding.file,
          finding.recommendation
        ])}
        title="Review findings"
      />
      <section className="panel">
        <h2>Acceptance matrix</h2>
        {selectedTask ? (
          <DataTable
            columns={["Criterion", "Status", "Evidence"]}
            rows={selectedTask.acceptance_criteria.map((criterion) => [
              criterion.criterion_text,
              criterion.status,
              criterion.evidence_reference
            ])}
          />
        ) : (
          <EmptyTable title="Acceptance matrix" />
        )}
      </section>
    </div>
  );
}

function MetricsView({ metrics }: { metrics: Record<string, MetricValue> }) {
  return (
    <section className="metric-grid" aria-label="Portfolio metrics">
      {Object.entries(metrics).map(([name, value]) => (
        <Metric key={name} label={labelize(name)} value={metricValue(value)} />
      ))}
    </section>
  );
}

function Metric({
  label,
  tone = "default",
  value
}: {
  label: string;
  tone?: "default" | "danger" | "warning";
  value: number | string | null;
}) {
  return (
    <article className="metric" data-tone={tone}>
      <span>{label}</span>
      <strong>{value ?? "Not measured"}</strong>
    </article>
  );
}

function DataTable({
  columns,
  rows,
  title
}: {
  columns: string[];
  rows: string[][];
  title?: string;
}) {
  return (
    <section className="panel">
      {title ? <h2>{title}</h2> : null}
      {rows.length === 0 ? (
        <p className="muted">No records</p>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                {columns.map((column) => (
                  <th key={column} scope="col">
                    {column}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, rowIndex) => (
                <tr key={rowIndex}>
                  {row.map((cell, cellIndex) => (
                    <td key={cellIndex}>{cell}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function EmptyTable({ title }: { title: string }) {
  return (
    <section className="panel">
      <h2>{title}</h2>
      <p className="muted">No records</p>
    </section>
  );
}

function useTaskAction() {
  return useMutation({
    mutationFn: async ({ action, taskId }: { action: string; taskId: string }) => {
      const body =
        action === "block"
          ? JSON.stringify({ reason: window.prompt("Blocking reason") ?? "Blocked from dashboard" })
          : undefined;
      const response = await fetch(`${apiBaseUrl}/dashboard/tasks/${taskId}/${action}`, {
        body,
        headers: body ? { "Content-Type": "application/json" } : undefined,
        method: "POST"
      });
      await parseJsonResponse<unknown>(response);
      await queryClient.invalidateQueries({ queryKey: ["dashboard-state"] });
    }
  });
}

async function fetchDashboardState(): Promise<DashboardState> {
  const response = await fetch(`${apiBaseUrl}/dashboard/state`);
  return parseJsonResponse<DashboardState>(response);
}

async function parseJsonResponse<T>(response: Response): Promise<T> {
  const payload = (await response.json()) as T | { detail?: string };
  if (!response.ok) {
    const detail =
      typeof payload === "object" && payload !== null && "detail" in payload
        ? payload.detail
        : undefined;
    throw new Error(detail ?? `Dashboard request failed: ${response.status}`);
  }
  return payload as T;
}

function formatDate(value: string | null) {
  if (!value) {
    return "";
  }
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "short",
    timeStyle: "short"
  }).format(new Date(value));
}

function labelize(value: string) {
  return value.replaceAll("_", " ");
}

function metricValue(value: MetricValue): number | string | null {
  if (typeof value === "object" && value !== null) {
    return value.value ?? value.status;
  }
  if (typeof value === "number") {
    return Number.isInteger(value) ? value : value.toFixed(2);
  }
  return value;
}

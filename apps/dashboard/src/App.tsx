import { QueryClientProvider } from "@tanstack/react-query";

import { MetricsSummary } from "./components/MetricsSummary";
import { ProjectsView } from "./components/ProjectsView";
import { ReviewPanel } from "./components/ReviewPanel";
import { SessionList } from "./components/SessionList";
import { TaskDetail } from "./components/TaskTable";
import { TodayView } from "./components/TodayView";
import { ValidationPanel } from "./components/ValidationPanel";
import { queryClient, useDashboard, views } from "./hooks/useDashboard";
import type { View } from "./hooks/useDashboard";
import type { DashboardState, TaskSummary } from "./types";
import { formatDate } from "./utils/format";

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <Dashboard />
    </QueryClientProvider>
  );
}

function Dashboard() {
  const dashboard = useDashboard();
  const state = dashboard.state;

  return (
    <main className="shell" aria-labelledby="page-title">
      <header className="topbar">
        <div>
          <p className="eyebrow">Milestone 9</p>
          <h1 id="page-title">AI Engineering Workbench</h1>
        </div>
        <div className="api-status" data-state={dashboard.stateQuery.status}>
          <span>{dashboard.stateQuery.isFetching ? "Refreshing" : dashboard.stateQuery.status}</span>
          <strong>{state ? formatDate(state.generated_at) : "Local API"}</strong>
        </div>
      </header>

      <nav className="tabs" aria-label="Dashboard views">
        {views.map((item) => (
          <button
            aria-current={dashboard.view === item.id ? "page" : undefined}
            className="tab"
            key={item.id}
            onClick={() => dashboard.setView(item.id)}
            type="button"
          >
            {item.label}
          </button>
        ))}
      </nav>

      {dashboard.stateQuery.isError ? (
        <section className="empty-state" role="alert">
          <h2>API unavailable</h2>
          <p>Start the local API with make api, then refresh this dashboard.</p>
        </section>
      ) : dashboard.stateQuery.isLoading || !state ? (
        <section className="empty-state">
          <h2>Loading dashboard</h2>
        </section>
      ) : (
        <DashboardContent
          actionMutation={dashboard.actionMutation}
          onSelectedTaskChange={dashboard.setSelectedTaskId}
          selectedTask={dashboard.selectedTask}
          state={state}
          view={dashboard.view}
        />
      )}
    </main>
  );
}

export function DashboardContent({
  actionMutation,
  onSelectedTaskChange,
  selectedTask,
  state,
  view
}: {
  actionMutation: ReturnType<typeof useDashboard>["actionMutation"];
  onSelectedTaskChange: (taskId: string) => void;
  selectedTask: TaskSummary | null;
  state: DashboardState;
  view: View;
}) {
  return (
    <section className="content">
      {view === "today" && <TodayView today={state.today} tasks={state.tasks} />}
      {view === "projects" && <ProjectsView projects={state.projects} />}
      {view === "task" && (
        <TaskDetail
          actionMutation={actionMutation}
          onSelectedTaskChange={onSelectedTaskChange}
          selectedTask={selectedTask}
          tasks={state.tasks}
        />
      )}
      {view === "sessions" && <SessionList sessions={state.sessions} />}
      {view === "validation" && <ValidationPanel validation={state.validation} />}
      {view === "review" && <ReviewPanel findings={state.review.findings} selectedTask={selectedTask} />}
      {view === "metrics" && <MetricsSummary metrics={state.metrics} />}
    </section>
  );
}

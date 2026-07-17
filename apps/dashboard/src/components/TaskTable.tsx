import type { UseMutationResult } from "@tanstack/react-query";

import type { TaskActionRequest } from "../api/client";
import type { TaskSummary } from "../types";
import { DataTable, EmptyTable } from "./DataTable";
import { TaskActions } from "./TaskActions";

export function TaskTable({ tasks }: { tasks: TaskSummary[] }) {
  return (
    <DataTable
      columns={["Task", "Project", "Status", "Validation", "Priority"]}
      rows={tasks.map((task) => [
        task.title,
        task.project_id,
        task.status,
        task.validation_status,
        task.priority
      ])}
      title="Needs attention"
    />
  );
}

export function TaskDetail({
  actionMutation,
  onSelectedTaskChange,
  selectedTask,
  tasks
}: {
  actionMutation: UseMutationResult<void, Error, TaskActionRequest>;
  onSelectedTaskChange: (taskId: string) => void;
  selectedTask: TaskSummary | null;
  tasks: TaskSummary[];
}) {
  if (!selectedTask) {
    return <EmptyTable title="Task detail" />;
  }
  return (
    <div className="split">
      <section className="panel">
        <TaskHeader
          onSelectedTaskChange={onSelectedTaskChange}
          selectedTask={selectedTask}
          tasks={tasks}
        />
        <TaskFacts selectedTask={selectedTask} />
        <p className="objective">{selectedTask.objective}</p>
        <TaskActions
          actions={selectedTask.available_actions}
          isPending={actionMutation.isPending}
          mutation={actionMutation}
          taskId={selectedTask.id}
        />
      </section>
      <section className="panel">
        <h2>Acceptance</h2>
        <AcceptanceRows selectedTask={selectedTask} />
      </section>
    </div>
  );
}

function TaskHeader({
  onSelectedTaskChange,
  selectedTask,
  tasks
}: {
  onSelectedTaskChange: (taskId: string) => void;
  selectedTask: TaskSummary;
  tasks: TaskSummary[];
}) {
  return (
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
  );
}

function TaskFacts({ selectedTask }: { selectedTask: TaskSummary }) {
  return (
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
  );
}

export function AcceptanceRows({ selectedTask }: { selectedTask: TaskSummary }) {
  return (
    <DataTable
      columns={["Criterion", "Status", "Evidence"]}
      rows={selectedTask.acceptance_criteria.map((criterion) => [
        criterion.criterion_text,
        criterion.status,
        criterion.evidence_reference
      ])}
    />
  );
}

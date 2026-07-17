import type { FindingSummary, TaskSummary } from "../types";
import { DataTable, EmptyTable } from "./DataTable";
import { AcceptanceRows } from "./TaskTable";

export function ReviewPanel({
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
        {selectedTask ? <AcceptanceRows selectedTask={selectedTask} /> : <EmptyTable title="Acceptance matrix" />}
      </section>
    </div>
  );
}

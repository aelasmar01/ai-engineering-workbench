import type { ValidationSummary } from "../types";
import { DataTable } from "./DataTable";

export function ValidationPanel({ validation }: { validation: ValidationSummary[] }) {
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

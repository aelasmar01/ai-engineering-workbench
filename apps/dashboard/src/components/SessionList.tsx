import type { SessionSummary } from "../types";
import { formatDate } from "../utils/format";
import { DataTable } from "./DataTable";

export function SessionList({ sessions }: { sessions: SessionSummary[] }) {
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

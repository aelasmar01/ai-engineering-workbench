import type { TaskSummary, TodaySummary } from "../types";
import { TaskTable } from "./TaskTable";
import { TodayMetrics } from "./MetricsSummary";

export function TodayView({ today, tasks }: { today: TodaySummary; tasks: TaskSummary[] }) {
  const humanActionTasks = tasks.filter(
    (task) => task.status === "blocked" || task.validation_status === "failed"
  );
  return (
    <>
      <TodayMetrics today={today} />
      <TaskTable tasks={humanActionTasks} />
    </>
  );
}

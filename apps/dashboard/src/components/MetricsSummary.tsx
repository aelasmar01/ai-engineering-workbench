import type { MetricValue, TodaySummary } from "../types";
import { labelize, metricValue } from "../utils/format";

export function TodayMetrics({ today }: { today: TodaySummary }) {
  return (
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
  );
}

export function MetricsSummary({ metrics }: { metrics: Record<string, MetricValue> }) {
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

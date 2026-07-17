import type { ProjectSummary } from "../types";
import { formatDate } from "../utils/format";
import { DataTable } from "./DataTable";

export function ProjectsView({ projects }: { projects: ProjectSummary[] }) {
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

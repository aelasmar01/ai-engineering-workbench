export type TodaySummary = {
  daily_pr_target: number;
  pull_requests_created_today: number;
  pull_requests_merged_today: number;
  tasks_ready_to_start: number;
  active_tasks: number;
  tasks_requiring_human_action: number;
  failed_checks: number;
  blocked_tasks: number;
};

export type ProjectSummary = {
  id: string;
  name: string;
  status: string;
  health_status: string;
  active_task_count: number;
  open_pr_count: number;
  last_validation: string | null;
  portfolio_categories: string[];
};

export type AcceptanceRow = {
  id: string;
  criterion_text: string;
  status: string;
  evidence_type: string;
  evidence_reference: string;
};

export type WorktreeSummary = {
  id: string;
  path: string;
  branch: string;
  base_branch: string;
  status: string;
  date_created: string | null;
};

export type PullRequestSummary = {
  id: string;
  task_id: string;
  repository: string;
  branch: string;
  number: number;
  url: string;
  status: string;
  created_time: string | null;
};

export type TaskSummary = {
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

export type SessionSummary = {
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

export type ValidationSummary = {
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

export type FindingSummary = {
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

export type MetricValue = number | string | null | { value: number | null; status: string };

export type DashboardState = {
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

import type { DashboardState, TaskSummary } from "./types";

export const taskFixture: TaskSummary = {
  id: "TASK-001",
  project_id: "fixture-project",
  title: "Ship dashboard tests",
  objective: "Verify dashboard decomposition.",
  type: "feature",
  priority: "high",
  status: "blocked",
  constraints: [],
  expected_paths: ["apps/dashboard"],
  required_checks: ["test"],
  acceptance_criteria: [
    {
      id: "criterion-1",
      criterion_text: "Renders task rows",
      status: "automatically_verified",
      evidence_type: "test",
      evidence_reference: "TaskTable.test.tsx"
    }
  ],
  worktree: null,
  branch: null,
  assigned_agent: null,
  agent_session_count: 0,
  validation_status: "failed",
  diff_summary: {
    review_finding_count: 1,
    unresolved_finding_count: 1
  },
  pull_request: null,
  available_actions: ["unblock"]
};

export const dashboardFixture: DashboardState = {
  generated_at: "2026-07-17T12:00:00Z",
  today: {
    daily_pr_target: 3,
    pull_requests_created_today: 1,
    pull_requests_merged_today: 0,
    tasks_ready_to_start: 2,
    active_tasks: 1,
    tasks_requiring_human_action: 1,
    failed_checks: 1,
    blocked_tasks: 1
  },
  projects: [
    {
      id: "fixture-project",
      name: "Fixture Project",
      status: "active",
      health_status: "blocked",
      active_task_count: 1,
      open_pr_count: 0,
      last_validation: "2026-07-17T12:00:00Z",
      portfolio_categories: ["testing"]
    }
  ],
  tasks: [taskFixture],
  sessions: [
    {
      id: "session-1",
      agent: "codex",
      role: "implementer",
      task_id: "TASK-001",
      task_title: "Ship dashboard tests",
      start_time: "2026-07-17T12:00:00Z",
      last_activity: "2026-07-17T12:01:00Z",
      status: "running",
      worktree_id: "worktree-1",
      changed_file_count: null,
      latest_event: "running"
    }
  ],
  validation: [
    {
      id: "validation-1",
      task_id: "TASK-001",
      run_group_id: "group-1",
      task_title: "Ship dashboard tests",
      check_name: "test",
      status: "failed",
      duration_seconds: 4,
      exit_code: 1,
      output_path: "/tmp/evidence.log"
    }
  ],
  review: {
    findings: [
      {
        id: "finding-1",
        task_id: "TASK-001",
        task_title: "Ship dashboard tests",
        severity: "high",
        category: "security",
        file: "src/auth.py",
        line: null,
        description: "Review finding",
        recommendation: "Fix it",
        status: "open"
      }
    ],
    acceptance: []
  },
  metrics: {
    validation_pass_rate: 0.5,
    unattributed_validation_runs: 1
  }
};

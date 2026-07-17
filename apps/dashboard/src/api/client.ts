import type { DashboardState } from "../types";

const apiBaseUrl = "http://127.0.0.1:8787";

export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

export async function fetchDashboardState(): Promise<DashboardState> {
  const response = await fetch(`${apiBaseUrl}/dashboard/state`);
  return parseJsonResponse<DashboardState>(response);
}

export async function runTaskAction(request: TaskActionRequest): Promise<void> {
  const response = await fetch(`${apiBaseUrl}/dashboard/tasks/${request.taskId}/${request.action}`, {
    body: request.body,
    headers: request.body ? { "Content-Type": "application/json" } : undefined,
    method: "POST"
  });
  await parseJsonResponse<unknown>(response);
}

export type TaskActionRequest = {
  action: string;
  taskId: string;
  body?: string;
};

export async function parseJsonResponse<T>(response: Response): Promise<T> {
  const payload = (await response.json()) as T | { detail?: string };
  if (!response.ok) {
    const detail =
      typeof payload === "object" && payload !== null && "detail" in payload
        ? payload.detail
        : undefined;
    throw new ApiError(response.status, detail ?? `Dashboard request failed: ${response.status}`);
  }
  return payload as T;
}

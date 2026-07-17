import type { UseMutationResult } from "@tanstack/react-query";

import type { TaskActionRequest } from "../api/client";

export function TaskActions({
  actions,
  isPending,
  mutation,
  taskId
}: {
  actions: string[];
  isPending: boolean;
  mutation: UseMutationResult<void, Error, TaskActionRequest>;
  taskId: string;
}) {
  return (
    <>
      <div className="actions" aria-label="Task actions">
        {actions.map((action) => (
          <button
            disabled={isPending}
            key={action}
            onClick={() => mutation.mutate(buildTaskActionRequest(taskId, action))}
            type="button"
          >
            {action}
          </button>
        ))}
      </div>
      {mutation.isError ? (
        <p className="muted" role="alert">
          {mutation.error.message}
        </p>
      ) : null}
    </>
  );
}

export function buildTaskActionRequest(
  taskId: string,
  action: string,
  promptForReason: () => string | null = () => window.prompt("Blocking reason")
): TaskActionRequest {
  if (action !== "block") {
    return { action, taskId };
  }
  const reason = promptForReason();
  if (!reason?.trim()) {
    throw new Error("Blocking reason is required");
  }
  return {
    action,
    taskId,
    body: JSON.stringify({ reason })
  };
}

import type { UseMutationResult } from "@tanstack/react-query";
import { renderToString } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import type { TaskActionRequest } from "../api/client";
import { buildTaskActionRequest, TaskActions } from "./TaskActions";

describe("TaskActions", () => {
  it("requires a blocking reason", () => {
    expect(() => buildTaskActionRequest("TASK-001", "block", () => "")).toThrow(
      "Blocking reason is required"
    );
  });

  it("builds block request bodies", () => {
    expect(buildTaskActionRequest("TASK-001", "block", () => "Waiting on review")).toEqual({
      action: "block",
      taskId: "TASK-001",
      body: JSON.stringify({ reason: "Waiting on review" })
    });
  });

  it("renders failed action detail", () => {
    const mutation = {
      error: new Error("cannot transition task"),
      isError: true,
      mutate: vi.fn()
    } as unknown as UseMutationResult<void, Error, TaskActionRequest>;

    const html = renderToString(
      <TaskActions actions={["complete"]} isPending={false} mutation={mutation} taskId="TASK-001" />
    );

    expect(html).toContain("complete");
    expect(html).toContain("cannot transition task");
  });
});

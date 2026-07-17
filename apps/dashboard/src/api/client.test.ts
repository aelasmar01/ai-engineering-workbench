import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, parseJsonResponse, runTaskAction } from "./client";

describe("api client", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("throws ApiError with server detail for non-2xx responses", async () => {
    const detailedResponse = new Response(JSON.stringify({ detail: "cannot transition task" }), {
      status: 409
    });
    const typedResponse = new Response(JSON.stringify({ detail: "cannot transition task" }), {
      status: 409
    });

    await expect(parseJsonResponse(detailedResponse)).rejects.toMatchObject({
      detail: "cannot transition task",
      status: 409
    });
    await expect(parseJsonResponse(typedResponse)).rejects.toBeInstanceOf(ApiError);
  });

  it("returns parsed payload for 2xx responses", async () => {
    const response = new Response(JSON.stringify({ status: "ok" }), { status: 200 });

    await expect(parseJsonResponse<{ status: string }>(response)).resolves.toEqual({
      status: "ok"
    });
  });

  it("posts task action requests", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({}), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    await runTaskAction({ action: "unblock", taskId: "TASK-001" });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0][0]).toContain("/dashboard/tasks/TASK-001/unblock");
  });
});

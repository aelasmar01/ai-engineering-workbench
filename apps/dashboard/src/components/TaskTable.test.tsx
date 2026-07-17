import { renderToString } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { taskFixture } from "../test-fixtures";
import { TaskTable } from "./TaskTable";

describe("TaskTable", () => {
  it("renders task rows from a fixture payload", () => {
    const html = renderToString(<TaskTable tasks={[taskFixture]} />);

    expect(html).toContain("Ship dashboard tests");
    expect(html).toContain("fixture-project");
    expect(html).toContain("failed");
  });

  it("renders status values for each task", () => {
    const html = renderToString(
      <TaskTable
        tasks={[
          { ...taskFixture, id: "TASK-001", status: "blocked" },
          { ...taskFixture, id: "TASK-002", title: "Ready task", status: "ready" },
          { ...taskFixture, id: "TASK-003", title: "Active task", status: "in_progress" }
        ]}
      />
    );

    expect(html).toContain("blocked");
    expect(html).toContain("ready");
    expect(html).toContain("in_progress");
  });
});

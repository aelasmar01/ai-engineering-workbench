import { renderToString } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { App, DashboardContent } from "./App";
import { dashboardFixture, taskFixture } from "./test-fixtures";

describe("App", () => {
  it("renders the Milestone 9 operational dashboard shell", () => {
    const html = renderToString(<App />);

    expect(html).toContain("AI Engineering Workbench");
    expect(html).toContain("Milestone 9");
    expect(html).toContain("Today");
    expect(html).toContain("Projects");
  });

  it("renders fixture dashboard state without crashing", () => {
    const html = renderToString(
      <DashboardContent
        actionMutation={
          {
            isPending: false,
            mutate: () => undefined
          } as never
        }
        onSelectedTaskChange={() => undefined}
        selectedTask={taskFixture}
        state={dashboardFixture}
        view="task"
      />
    );

    expect(html).toContain("Ship dashboard tests");
    expect(html).toContain("Renders task rows");
  });
});

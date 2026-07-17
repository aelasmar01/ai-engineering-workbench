import { renderToString } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { App } from "./App";

describe("App", () => {
  it("renders the Milestone 9 operational dashboard shell", () => {
    const html = renderToString(<App />);

    expect(html).toContain("AI Engineering Workbench");
    expect(html).toContain("Milestone 9");
    expect(html).toContain("Today");
    expect(html).toContain("Projects");
  });
});

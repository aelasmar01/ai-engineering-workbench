import { renderToString } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { App } from "./App";

describe("App", () => {
  it("renders the Milestone 0 dashboard shell", () => {
    const html = renderToString(<App />);

    expect(html).toContain("AI Engineering Workbench");
    expect(html).toContain("Milestone 0");
  });
});

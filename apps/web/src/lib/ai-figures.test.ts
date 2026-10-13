import { describe, expect, it } from "vitest";
import { figureSpans } from "./ai-figures";

describe("figureSpans", () => {
  it("splits Gemini's text into plain text, checked figures and unchecked ones", () => {
    const spans = figureSpans("Shares are 68% of it against 60%, about $9,000 more at risk.", ["$9,000"]);
    expect(spans).toEqual([
      { text: "Shares are ", kind: "text" },
      { text: "68%", kind: "checked" },
      { text: " of it against ", kind: "text" },
      { text: "60%", kind: "checked" },
      { text: ", about ", kind: "text" },
      { text: "$9,000", kind: "unchecked" },
      { text: " more at risk.", kind: "text" },
    ]);
  });
  it("reads negative, decimal and dollar-cent figures, and leaves years and plain counts alone", () => {
    const spans = figureSpans("In 2008 it fell −18.5% to $41,230.17 over 12 months.", []);
    expect(spans.filter((s) => s.kind !== "text").map((s) => s.text)).toEqual(["−18.5%", "$41,230.17"]);
  });
  it("treats every figure as checked when nothing was flagged, and returns one text span when there are none", () => {
    expect(figureSpans("No figures here.", [])).toEqual([{ text: "No figures here.", kind: "text" }]);
  });
});

import { describe, expect, it } from "vitest";
import { formatLike, parseFigure } from "./motion-figures";

describe("parseFigure", () => {
  it("reads dollars, percentages and plain numbers with their format", () => {
    expect(parseFigure("$45,635.00")).toEqual({ prefix: "$", value: 45635, decimals: 2, suffix: "", grouped: true });
    expect(parseFigure("7.78%")).toEqual({ prefix: "", value: 7.78, decimals: 2, suffix: "%", grouped: false });
    expect(parseFigure("−$10,493")).toEqual({ prefix: "−$", value: 10493, decimals: 0, suffix: "", grouped: true });
    expect(parseFigure("6.2 / 10")).toEqual({ prefix: "", value: 6.2, decimals: 1, suffix: " / 10", grouped: false });
    expect(parseFigure("+$3,508.13")).toEqual({ prefix: "+$", value: 3508.13, decimals: 2, suffix: "", grouped: true });
  });
  it("returns null for text that is not one figure", () => {
    expect(parseFigure("Not scored")).toBeNull();
    expect(parseFigure("Band 4, Growth")).toBeNull();
    expect(parseFigure("")).toBeNull();
  });
});

describe("formatLike", () => {
  it("writes an in-between value in the figure's own format", () => {
    const spec = parseFigure("$45,635.00")!;
    expect(formatLike(12345.678, spec)).toBe("$12,345.68");
    expect(formatLike(45635, spec)).toBe("$45,635.00");
    expect(formatLike(3.1, parseFigure("7.78%")!)).toBe("3.10%");
    expect(formatLike(512, parseFigure("−$10,493")!)).toBe("−$512");
  });
});

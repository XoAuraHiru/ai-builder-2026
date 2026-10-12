import { describe, expect, it } from "vitest";
import { areaPath, linePath, linear, logTicks, nearestIndex, niceTicks } from "./scale";

describe("linear", () => {
  it("maps a domain onto a range", () => {
    expect(linear([0, 10], [0, 100])(5)).toBe(50);
    expect(linear([0, 10], [100, 0])(10)).toBe(0);
  });
  it("survives an empty domain", () => {
    expect(linear([3, 3], [0, 100])(3)).toBe(0);
  });
});

describe("niceTicks", () => {
  it("picks round steps", () => {
    expect(niceTicks(0, 1000, 4)).toEqual([0, 200, 400, 600, 800, 1000]);
    expect(niceTicks(0, 437_000, 4)).toEqual([0, 100_000, 200_000, 300_000, 400_000]);
  });
  it("returns the single value for a flat range", () => {
    expect(niceTicks(5, 5)).toEqual([5]);
  });
});

describe("paths", () => {
  it("draws lines and closed areas", () => {
    expect(linePath([[0, 0], [10, 5]])).toBe("M0,0L10,5");
    expect(areaPath([[0, 1], [1, 2]], [[0, 0], [1, 0]])).toBe("M0,1L1,2L1,0L0,0Z");
  });
  it("finds the nearest point", () => {
    expect(nearestIndex([0, 10, 20], 14)).toBe(1);
  });
});

describe("logTicks", () => {
  it("picks 1-2-5 steps across decades", () => {
    expect(logTicks(8_000, 210_000)).toEqual([10_000, 20_000, 50_000, 100_000, 200_000]);
  });
  it("returns few ticks for a narrow range, so callers can fall back", () => {
    expect(logTicks(9_500, 13_500)).toEqual([10_000]);
  });
});

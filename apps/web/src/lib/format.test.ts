import { describe, expect, it } from "vitest";
import { compactUsd, formatDate, formatMonth, formatPct, formatSignedUsd, formatUsd } from "./format";

describe("formatUsd", () => {
  it("formats with cents by default and without on request", () => {
    expect(formatUsd("12500.5")).toBe("$12,500.50");
    expect(formatUsd(12500.5, 0)).toBe("$12,501");
  });
});

describe("compactUsd", () => {
  it("shortens large amounts for chart labels", () => {
    expect(compactUsd(1_234_567)).toBe("$1.2M");
    expect(compactUsd(250_000)).toBe("$250k");
    expect(compactUsd(9_500)).toBe("$9.5k");
    expect(compactUsd(950)).toBe("$950");
    expect(compactUsd(-12_000)).toBe("-$12k");
  });
});

describe("formatPct and formatSignedUsd", () => {
  it("rounds percentages and can show a plus sign", () => {
    expect(formatPct(12.345)).toBe("12.3%");
    expect(formatPct(3, 1, true)).toBe("+3.0%");
    expect(formatPct(-3, 1, true)).toBe("-3.0%");
  });
  it("signs money with a true minus", () => {
    expect(formatSignedUsd(-1234.5)).toBe("−$1,234.50");
    expect(formatSignedUsd(10)).toBe("+$10.00");
  });
});

describe("dates", () => {
  it("formats ISO dates and months for people", () => {
    expect(formatDate("2026-10-09")).toBe("Oct 9, 2026");
    expect(formatMonth("2008-02")).toBe("Feb 2008");
  });
});

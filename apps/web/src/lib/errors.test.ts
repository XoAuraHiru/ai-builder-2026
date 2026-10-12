import { describe, expect, it } from "vitest";
import { detailMessage } from "./errors";

describe("detailMessage", () => {
  it("keeps a plain detail string", () => {
    expect(detailMessage("Only the account holder can place instructions.", "Bad Request")).toBe("Only the account holder can place instructions.");
  });
  it("turns validation errors into one readable sentence", () => {
    const detail = [
      { loc: ["body", "amount_usd"], msg: "Input should be greater than 0", type: "greater_than" },
      { loc: ["body", "day_of_month"], msg: "Input should be less than or equal to 28", type: "less_than_equal" },
    ];
    expect(detailMessage(detail, "Unprocessable Entity")).toBe(
      "Check these fields: amount usd (input should be greater than 0); day of month (input should be less than or equal to 28).");
  });
  it("falls back when there is nothing usable", () => {
    expect(detailMessage(undefined, "Service Unavailable")).toBe("Service Unavailable");
    expect(detailMessage({ odd: true }, "Bad Request")).toBe("Bad Request");
  });
});

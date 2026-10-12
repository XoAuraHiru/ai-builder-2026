import { describe, expect, it } from "vitest";
import { actionLabel, canPlace, concerns, describeOrder, estimateCost, orderBody, VERDICTS, type Draft } from "./trading";

const draft: Draft = { symbol: "KO", side: "buy", order_type: "market", quantity: "3", limit_price: "" };

describe("orderBody", () => {
  it("builds the request for a market order", () => {
    expect(orderBody(draft)).toEqual({ body: { symbol: "KO", side: "buy", order_type: "market", quantity: 3, acknowledge_warnings: false } });
  });
  it("adds the limit and the acknowledgement", () => {
    expect(orderBody({ ...draft, order_type: "limit", limit_price: "$1,055.5" }, true)).toEqual({ body: {
      symbol: "KO", side: "buy", order_type: "limit", quantity: 3, acknowledge_warnings: true, limit_price: "1055.50" } });
  });
  it("says what to fix", () => {
    expect(orderBody({ ...draft, quantity: "0" })).toEqual({ error: "Enter a whole number of shares, 1 or more." });
    expect(orderBody({ ...draft, quantity: "2.5" })).toEqual({ error: "Enter a whole number of shares, 1 or more." });
    expect(orderBody({ ...draft, quantity: "200000" })).toEqual({ error: "Orders are limited to 100,000 shares." });
    expect(orderBody({ ...draft, order_type: "limit" })).toEqual({ error: "Enter the most you'll pay for a share." });
    expect(orderBody({ ...draft, side: "sell", order_type: "limit", limit_price: "abc" }))
      .toEqual({ error: "Enter the least you'll accept for a share." });
  });
});

describe("verdicts and orders", () => {
  it("names the action each verdict allows", () => {
    expect(VERDICTS.map((v) => actionLabel(v))).toEqual(["Place order", "Place order", "Send to an advisor", "Can't place this order"]);
    expect([canPlace("warn", false), canPlace("warn", true), canPlace("hold", false), canPlace("block", true)])
      .toEqual([false, true, true, false]);
  });
  it("describes an order and estimates its cost", () => {
    expect(describeOrder({ side: "sell", quantity: 5, symbol: "AAPL", order_type: "limit", limit_price: "210" }))
      .toBe("Sell 5 AAPL with a limit of $210.00");
    expect(describeOrder({ side: "buy", quantity: 1, symbol: "KO", order_type: "market", limit_price: null })).toBe("Buy 1 KO at market");
    expect(estimateCost("61.25", "4")).toBe(245);
    expect(estimateCost("61.25", "")).toBeNull();
  });
  it("keeps only the checks worth reading", () => {
    expect(concerns([{ code: "A", title: "A", outcome: "pass", detail: "" }, { code: "B", title: "B", outcome: "info", detail: "" }])
      .map((c) => c.code)).toEqual(["B"]);
    expect(concerns(undefined)).toEqual([]);
  });
});

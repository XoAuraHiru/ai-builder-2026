import { describe, expect, it } from "vitest";
import { deviceId } from "./device";

function memory() {
  const m = new Map<string, string>();
  return { getItem: (k: string) => m.get(k) ?? null, setItem: (k: string, v: string) => void m.set(k, v) };
}

describe("deviceId", () => {
  it("creates one identifier per browser and keeps it", () => {
    const store = memory();
    const first = deviceId(store);
    expect(first).toMatch(/^[0-9a-f-]{36}$/);
    expect(deviceId(store)).toBe(first);
  });
  it("gives up quietly when storage is unavailable", () => {
    expect(deviceId(null)).toBeNull();
    expect(deviceId({ getItem: () => { throw new Error("blocked"); }, setItem: () => {} })).toBeNull();
  });
});

describe("each demo person keeps their own device", () => {
  it("gives every persona its own identifier in one browser, so switching person never looks like one shared device", () => {
    const store = memory();
    const tom = deviceId(store, "tom@atrium.demo");
    const priya = deviceId(store, "priya@atrium.demo");
    expect(tom).not.toBe(priya);
    expect(deviceId(store, "TOM@atrium.demo")).toBe(tom);
    expect(deviceId(store)).not.toBe(tom);  // real sign-in: one identifier for the browser
  });
});


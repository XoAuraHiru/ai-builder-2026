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

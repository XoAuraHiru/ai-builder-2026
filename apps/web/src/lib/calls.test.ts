import { describe, expect, it } from "vitest";
import {
  clock, demoName, droppedNote, FIELD_LABEL, figuresWarning, FLAG_LABEL, flagsHeadline, highFlags, sortFlags, updateLine,
  type CallFlag, type LeadCall,
} from "./calls";

const flag = (kind: CallFlag["kind"], severity: CallFlag["severity"], start_s: number): CallFlag =>
  ({ kind, severity, start_s, quote: "q", rule: "r", why: "w", source: "gemini" });

describe("clock", () => {
  it("shows minutes and seconds, and hours only past an hour", () => {
    expect(clock(83.4)).toBe("1:23");
    expect([clock(0), clock(9.99), clock(605), clock(3725)]).toEqual(["0:00", "0:09", "10:05", "1:02:05"]);
  });
});

describe("labels", () => {
  it("names each conduct flag in plain words", () => {
    expect(FLAG_LABEL).toEqual({
      promissory: "Guarantee or promise", unsuitable: "Unsuitable recommendation", pressure: "Pressure",
      third_party_direction: "Third party directing the client", confusion: "Client confusion",
    });
  });
  it("names each field a call can update", () => {
    expect(Object.keys(FIELD_LABEL).sort()).toEqual(["goals", "horizon_years", "investable_usd", "monthly_usd", "source_of_funds"]);
    expect(FIELD_LABEL.horizon_years).toBe("Horizon");
    expect(Object.values(FIELD_LABEL).every((label) => label.length > 0)).toBe(true);
  });
});

describe("sortFlags", () => {
  it("puts high severity first, then by the second it was said", () => {
    const sorted = sortFlags([flag("confusion", "low", 5), flag("pressure", "high", 90), flag("promissory", "high", 40),
      flag("unsuitable", "medium", 10)]);
    expect(sorted.map((f) => f.kind)).toEqual(["promissory", "pressure", "unsuitable", "confusion"]);
  });
  it("does not reorder the list it was given", () => {
    const flags = [flag("confusion", "low", 5), flag("pressure", "high", 90)];
    sortFlags(flags);
    expect(flags[0].kind).toBe("confusion");
  });
});

describe("droppedNote", () => {
  it("says how many items were dropped and why", () => {
    expect(droppedNote({ flags: 2, updates: 0, facts: 0 })).toBe("2 flags were dropped because their quotes are not in the transcript.");
    expect(droppedNote({ flags: 1, updates: 0, facts: 0 })).toBe("1 flag was dropped because its quote is not in the transcript.");
    expect(droppedNote({ flags: 2, updates: 1, facts: 0 })).toBe(
      "2 flags and 1 proposed update were dropped because their quotes are not in the transcript.");
    expect(droppedNote({ flags: 0, updates: 0, facts: 1, invalid_updates: 2 })).toBe(
      "1 stated fact was dropped because its time is outside the call. 2 proposed updates were not offered because their values are not valid.");
  });
  it("is null when nothing was dropped", () => {
    expect(droppedNote({ flags: 0, updates: 0, facts: 0 })).toBeNull();
    expect(droppedNote({ flags: 0, updates: 0, facts: 0, invalid_updates: 0 })).toBeNull();
  });
});

describe("figuresWarning", () => {
  it("names the summary's figures that the call does not support", () => {
    expect(figuresWarning(["12%"])).toBe("Check before relying on this: 12% was not said on the call and is not on the form.");
    expect(figuresWarning(["12%", "$75,000"])).toBe(
      "Check before relying on this: 12% and $75,000 were not said on the call and are not on the form.");
    expect(figuresWarning([])).toBeUndefined();
    expect(figuresWarning(undefined)).toBeUndefined();
  });
});

describe("updateLine", () => {
  it("shows the field, its current value and the proposed one", () => {
    expect(updateLine({ field: "horizon_years", current: "20", proposed: "15", quote: "", start_s: 0 })).toBe("Horizon: 20 years → 15 years");
    expect(updateLine({ field: "monthly_usd", current: "500", proposed: "800", quote: "", start_s: 0 })).toBe("Every month: $500 → $800");
    expect(updateLine({ field: "source_of_funds", current: "salary", proposed: "property_sale", quote: "", start_s: 0 }))
      .toBe("Source of funds: salary → property sale");
    expect(updateLine({ field: "horizon_years", current: null, proposed: "1", quote: "", start_s: 0 })).toBe("Horizon: not set → 1 year");
  });
});

describe("flagsHeadline", () => {
  it("says what the high-severity flags found, third party first", () => {
    const flags = [flag("promissory", "high", 75), flag("confusion", "medium", 37), flag("third_party_direction", "high", 33)];
    expect(highFlags(flags).map((f) => f.kind)).toEqual(["third_party_direction", "promissory"]);  // in the order said
    expect(flagsHeadline(flags)).toBe("A third party directed the client, and the advisor promised a return.");
    expect(flagsHeadline([flag("pressure", "high", 3)])).toBe("The client was pressed to decide.");
  });
});

describe("demoName", () => {
  it("names the demo call a reading came from, if any", () => {
    const call = (source: LeadCall["source"], filename: string) => ({ source, filename }) as LeadCall;
    expect(demoName(call("demo", "pressure.mp3"))).toBe("pressure");
    expect(demoName(call("demo", "discovery.mp3"))).toBe("discovery");
    expect(demoName(call("upload", "pressure.mp3"))).toBeNull();
    expect(demoName(call("demo", "attack.mp3"))).toBeNull();
  });
});

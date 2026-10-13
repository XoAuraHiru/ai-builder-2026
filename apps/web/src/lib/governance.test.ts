import { describe, expect, it } from "vitest";
import {
  agreementLine, asUtc, canPause, caseValue, clockUtc, driftLine, elapsedClock, headline, passShare, runLine, runMeta, runNotice, STATUS_LABEL, STATUS_TONE,
  suiteStatus, suiteTitle, type ModelRow, type RunRow,
} from "./governance";

const row = (status: ModelRow["status"], over: Partial<ModelRow> = {}): ModelRow => ({
  key: "k", name: "Case review", kind: "gemini_prompt", kind_label: "Gemini prompt", tier: "high", owner: "Omar Haddad",
  status, version: "abc", validated_version: "abc", changed_since_validation: false, last_validated_at: null,
  last_run_id: null, fallback: null, ...over,
});

describe("governance copy", () => {
  it("leads with how many models are validated and any open breaker", () => {
    expect(headline([row("validated"), row("validated"), row("breaker_open")]).title)
      .toBe("2 of 3 models validated. One breaker is open.");
    expect(headline([row("validated"), row("failing"), row("failing")]).title)
      .toBe("1 of 3 models validated. 2 are failing their checks.");
    expect(headline([row("validated")]).title).toBe("Every model is validated.");
    expect(headline([row("validated"), row("breaker_open"), row("breaker_open"), row("failing")]).title)
      .toBe("1 of 4 models validated. 2 breakers are open. One is failing its checks.");
    expect(headline([row("validated"), row("monitored_only")]).title).toBe("1 of 2 models validated.");
  });
  it("says when the last live run was in the detail", () => {
    const run = { status: "finished", trigger: "button", tier: "live", finished_at: "2026-10-14T09:14:00Z", cost_usd: "0.15" } as RunRow;
    expect(headline([row("validated")], run).detail).toMatch(/^Last live run: Live checks started from this page/);
    expect(headline([row("validated")], null).detail).toBe("No live run yet: the live checks start after each deploy.");
  });
  it("names every status and suite in plain words", () => {
    expect(STATUS_LABEL.monitored_only).toBe("Monitored only");
    expect(STATUS_LABEL.no_result).toBe("No result");
    expect(STATUS_TONE.breaker_open).toBe("loss");
    expect(suiteTitle("red_team", "live")).toBe("Red team (live)");
    expect(suiteTitle("golden", "free")).toBe("Golden cases");
    expect(suiteTitle("fairness", "free")).toBe("Fair lending");
  });
  it("shows case values compactly and runs as one line", () => {
    expect(caseValue(0.7921)).toBe("0.79");
    expect(caseValue(8)).toBe("8");
    expect(caseValue({ fires: true })).toBe("fires: true");
    expect(caseValue(null)).toBe("None");
    expect(caseValue(["a", "b"])).toBe("a, b");
    expect(caseValue({ band: "clear", signals: [] })).toBe("band: clear; signals: none");
    expect(caseValue({ dropped_citations: ["x"] })).toBe("dropped citations: x");
    expect(runLine({ status: "finished", trigger: "deploy", finished_at: "2026-10-14T09:14:00Z", cost_usd: "0.152000" } as never))
      .toMatch(/^Live checks after a deploy, finished Oct 14.*\$0\.15$/);
    expect(runLine({ status: "running", trigger: "button", tier: "live", started_at: "2026-10-14T09:14:00Z", cost_usd: "0" } as never))
      .toBe("Live checks started from this page, running since 09:14 UTC");
    expect(runLine({ status: "failed", trigger: "button", tier: "live", started_at: "2026-10-14T09:14:00Z", cost_usd: "0" } as never))
      .toMatch(/could not start/);
  });
  it("offers a pause only where a fallback can stand in", () => {
    expect(canPause(row("validated", { fallback: "The scorer proposes the strongest matches." }))).toBe(true);
    expect(canPause(row("validated", { fallback: null }))).toBe(false);
  });
  it("reads monitoring as sentences, and too few decisions as a note", () => {
    expect(agreementLine("reconciler_agent", { agreed: 28, decided: 34, rate: 28 / 34, note: "" }))
      .toBe("Operations accepted 82% of the agent's proposals (34 decisions in 30 days).");
    expect(agreementLine("case_reviewer", { agreed: 3, decided: 4, rate: null, note: "Not enough decisions yet (4 of 10)" }))
      .toBe("Case review: not enough decisions yet (4 of 10).");
    expect(driftLine({ psi: 0.08, recent: 40, warn: false, note: "stable (PSI 0.08)" }))
      .toBe("Lead scores this month compared with training: stable (PSI 0.08).");
    expect(driftLine({ psi: null, recent: 3, warn: false, note: "Not enough recently scored leads yet (3 of 20)" }))
      .toBe("Lead scores: not enough recently scored leads yet (3 of 20).");
  });
});

describe("the notice after a run", () => {
  it("says a run finished only when it did", () => {
    expect(runNotice({ status: "finished" } as never)).toEqual({ tone: "success", title: "The checks finished" });
    expect(runNotice({ status: "failed" } as never)).toEqual({ tone: "error", title: "The checks did not finish" });
    expect(runNotice({ status: "did_not_finish" } as never)).toEqual({ tone: "error", title: "The checks ran out of time" });
  });
});


describe("runs and suites at a glance", () => {
  it("reads the API's zone-less run times as UTC", () => {
    expect(asUtc("2026-10-13T10:58:11.169205").toISOString()).toBe("2026-10-13T10:58:11.169Z");
    expect(asUtc("2026-10-13T10:58:11+00:00").toISOString()).toBe("2026-10-13T10:58:11.000Z");
    expect(clockUtc("2026-10-13T10:58:11")).toBe("10:58 UTC");
  });
  it("writes a run as one mono line with its cost", () => {
    const run = { tier: "free", trigger: "local", status: "finished", started_at: "2026-10-13T10:58:11", finished_at: "2026-10-13T10:58:13",
      cost_usd: "0.000000", git_sha: "" } as RunRow;
    expect(runMeta(run)).toBe("free checks · run on this server · Oct 13 10:58 UTC · $0.0000");
    expect(runMeta({ ...run, tier: "live", trigger: "button", status: "running", cost_usd: "0.0412", git_sha: "a1b2c3d4e5" }))
      .toBe("live checks · started from this page · running since 10:58 UTC · $0.0412 · a1b2c3d");
  });
  it("colours a suite by its bar and fills its bar by the cases that passed", () => {
    expect(suiteStatus({ passed: true, counts: { pass: 4, fail: 0, error: 0 } })).toEqual({ label: "Meets its bar", tone: "gain" });
    expect(suiteStatus({ passed: false, counts: { pass: 3, fail: 1, error: 0 } })).toEqual({ label: "Misses its bar", tone: "loss" });
    expect(suiteStatus({ passed: false, counts: { pass: 0, fail: 0, error: 2 } })).toEqual({ label: "No result", tone: "caution" });
    expect(passShare({ pass: 3, fail: 1, error: 0 })).toBe(75);
    expect(passShare({ pass: 0, fail: 0, error: 0 })).toBe(0);
  });
});

describe("elapsedClock", () => {
  const start = "2026-10-13T10:00:00";
  const at = (s: number) => Date.parse("2026-10-13T10:00:00Z") + s * 1000;
  it("counts a run's time as a clock, from the API's UTC start", () => {
    expect(elapsedClock(start, at(7))).toBe("0:07");
    expect(elapsedClock(start, at(582))).toBe("9:42");
    expect(elapsedClock(start, at(3725))).toBe("1:02:05");
    expect(elapsedClock("2026-10-13T10:00:00+00:00", at(61))).toBe("1:01");
  });
  it("never runs backwards when the clocks disagree", () => {
    expect(elapsedClock(start, at(-30))).toBe("0:00");
  });
});

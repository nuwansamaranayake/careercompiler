import { describe, expect, it } from "vitest";
import { ApiError } from "./api";
import {
  BUDGET_EXHAUSTED, SESSION_EXPIRED, endsSession, errorMessage, fileSize, humanKey, overstate,
  plainDetail, plural, refusalFrom, rejectedEditFrom, score, statusTone, verdictLabel,
} from "./format";

describe("refusalFrom", () => {
  it("is null for anything that is not a typed refusal", () => {
    for (const d of [undefined, null, "a string", 42, {}, { error: "x" },
      { error: "x", violations: [] }, { violations: [{ text: "t" }] }]) {
      expect(refusalFrom(d)).toBeNull();
    }
  });

  it("uses the violation's own detail when it has one", () => {
    const r = refusalFrom({
      error: "reference_integrity",
      violations: [{ text: "Led 40 engineers.", cited: ["team_lead"],
        detail: "number 40 appears in no cited fact" }],
    });
    expect(r).toEqual({
      sentence: "Led 40 engineers.", cited: ["team_lead"],
      why: "number 40 appears in no cited fact", rounds: 1 });
  });

  it("explains an entailment refusal from the score and threshold", () => {
    const r = refusalFrom({
      error: "entailment",
      violations: [{ text: "Directed the company.", entailment: 0.0312, threshold: 0.7 }],
    });
    expect(r?.why).toBe("the evidence supports it at 0.03, below the 0.7 the gate requires");
    expect(r?.cited).toEqual([]);
  });

  it("falls back to the error name and a placeholder sentence", () => {
    const r = refusalFrom({ error: "render_failed", violations: [{}] });
    expect(r).toEqual({
      sentence: "(sentence unavailable)", cited: [], why: "render_failed", rounds: 1 });
  });

  it("counts failed rounds and never the revision_unchanged marker", () => {
    const r = refusalFrom({
      error: "entailment",
      repair: [{ stage: "entailment" }, { stage: "entailment" }, { stage: "revision_unchanged" }],
      violations: [{ text: "x", detail: "d" }],
    });
    expect(r?.rounds).toBe(2);
  });
});

describe("rejectedEditFrom", () => {
  const verdict = {
    reference_integrity: { ok: true, violations: [] },
    entailment: { checked: true, ok: false, score: 0.05, threshold: 0.7, violations: [] },
  };

  it("returns the gate verdict a rejected edit carries", () => {
    expect(rejectedEditFrom({ error: "edit_rejected", ...verdict }))
      .toEqual({ ok: false, ...verdict });
  });

  it("is null for other errors and malformed details", () => {
    expect(rejectedEditFrom(undefined)).toBeNull();
    expect(rejectedEditFrom("edit_rejected")).toBeNull();
    expect(rejectedEditFrom({ error: "entailment_unavailable", ...verdict })).toBeNull();
    expect(rejectedEditFrom({ error: "edit_rejected" })).toBeNull();
    expect(rejectedEditFrom({ error: "edit_rejected", reference_integrity: verdict.reference_integrity }))
      .toBeNull();
  });
});

describe("plainDetail", () => {
  it("passes a string detail through", () => {
    expect(plainDetail("LLM extraction requires OPENROUTER_API_KEY", "fb"))
      .toBe("LLM extraction requires OPENROUTER_API_KEY");
  });
  it("renders a typed {error, message}", () => {
    expect(plainDetail({ error: "entailment_unavailable", message: "model missing" }, "fb"))
      .toBe("entailment_unavailable: model missing");
    expect(plainDetail({ message: "model missing" }, "fb")).toBe("unavailable: model missing");
  });
  it("uses the fallback when there is nothing to show", () => {
    for (const d of [undefined, null, "", {}, { error: "x" }, 7]) {
      expect(plainDetail(d, "fallback")).toBe("fallback");
    }
  });
});

describe("errorMessage and endsSession", () => {
  it("turns session-ending codes into their fixed sentences", () => {
    const expired = new ApiError("SESSION_EXPIRED", 401, null);
    const spent = new ApiError("BUDGET_EXHAUSTED", 429, null);
    expect(errorMessage(expired)).toBe(SESSION_EXPIRED);
    expect(errorMessage(spent)).toBe(BUDGET_EXHAUSTED);
    expect(endsSession(expired)).toBe(true);
    expect(endsSession(spent)).toBe(true);
  });

  it("shows the server's detail for other HTTP errors and does not end the session", () => {
    const e = new ApiError("HTTP", 413, "file exceeds the 2 MB upload limit");
    expect(errorMessage(e)).toBe("file exceeds the 2 MB upload limit");
    expect(endsSession(e)).toBe(false);
    expect(errorMessage(new ApiError("HTTP", 500, undefined)))
      .toBe("The server answered HTTP 500.");
  });

  it("names a network failure", () => {
    expect(errorMessage(new ApiError("NETWORK", 0, "TypeError: Failed to fetch")))
      .toBe("Could not reach the API: TypeError: Failed to fetch");
    expect(errorMessage(new ApiError("NETWORK", 0, undefined)))
      .toBe("Could not reach the API: network error");
  });

  it("handles plain errors and non-errors", () => {
    expect(errorMessage(new Error("boom"))).toBe("boom");
    expect(errorMessage("just text")).toBe("just text");
    expect(endsSession(new Error("SESSION_EXPIRED"))).toBe(false);
  });
});

describe("labels", () => {
  it("verdictLabel", () => {
    expect(verdictLabel("do_not_apply")).toBe("do not apply");
    expect(verdictLabel("apply")).toBe("apply");
  });
  it("statusTone", () => {
    expect(statusTone("matched")).toBe("ok");
    expect(statusTone("apply")).toBe("ok");
    expect(statusTone("partial")).toBe("warn");
    expect(statusTone("gap")).toBe("bad");
    expect(statusTone("do_not_apply")).toBe("bad");
    expect(statusTone("anything else")).toBe("plain");
  });
  it("humanKey", () => {
    expect(humanKey("active_ts_sci_clearance")).toBe("active ts sci clearance");
    expect(humanKey("react-native__apps")).toBe("react native apps");
  });
  it("score never invents a number", () => {
    expect(score(0.9976)).toBe("0.99");
    expect(score(0.9976, 4)).toBe("0.9976");
    expect(score(0.99999, 4)).toBe("0.9999");
    expect(score(1)).toBe("1.00");
    expect(score(0.7)).toBe("0.70");
    expect(score(0.29, 2)).toBe("0.29");
    expect(score(null)).toBe("unknown");
    expect(score(undefined)).toBe("unknown");
    expect(score(0)).toBe("0.00");
  });
  it("fileSize", () => {
    expect(fileSize(512)).toBe("512 B");
    expect(fileSize(20_480)).toBe("20 KB");
    expect(fileSize(1_572_864)).toBe("1.5 MB");
  });
  it("plural", () => {
    expect(plural(1, "fact")).toBe("1 fact");
    expect(plural(0, "fact")).toBe("0 facts");
    expect(plural(2, "gap")).toBe("2 gaps");
    expect(plural(2, "match", "matches")).toBe("2 matches");
  });
});

describe("overstate", () => {
  it("multiplies the first number by ten", () => {
    expect(overstate("Led a team of 4 engineers for 3 years."))
      .toBe("Led a team of 40 engineers for 3 years.");
    expect(overstate("Migrated a 1,200 row table.")).toBe("Migrated a 12000 row table.");
  });
  it("prepends an unsupported claim when there is no number", () => {
    expect(overstate("Ran Kubernetes in production."))
      .toBe("Directed the entire engineering organisation. Ran Kubernetes in production.");
  });
});

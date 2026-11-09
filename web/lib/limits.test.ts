import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { LIMITS } from "./limits";

describe("published limits", () => {
  it("is the EVAL.md limits block, word for word", () => {
    const evalMd = readFileSync(resolve(__dirname, "..", "..", "EVAL.md"), "utf8");
    const block = evalMd.match(/<!-- LIMITS -->\s*([\s\S]+?)\s*<!-- \/LIMITS -->/);
    expect(block, "EVAL.md must carry the LIMITS markers").not.toBeNull();
    expect(LIMITS).toBe(block![1].split(/\s+/).join(" "));
  });
});

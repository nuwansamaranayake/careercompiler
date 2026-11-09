import { defineConfig } from "vitest/config";

/* Unit tests cover web/lib: every piece of frontend logic lives there. Components are
   thin and are proven in a real browser by tests/e2e against the real API. The 96 floor
   is the same number the backend holds (scripts/quality_gate.py). */
export default defineConfig({
  test: {
    environment: "node",
    include: ["lib/**/*.test.ts"],
    coverage: {
      provider: "v8",
      include: ["lib/**/*.ts"],
      exclude: ["lib/**/*.test.ts", "lib/types.ts"],
      reporter: ["text", "json-summary"],
      reportsDirectory: "coverage",
      thresholds: { lines: 96, branches: 96, functions: 96, statements: 96 },
    },
  },
});

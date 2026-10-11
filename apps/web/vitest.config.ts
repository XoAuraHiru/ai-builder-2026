import { defineConfig } from "vitest/config";

export default defineConfig({
  // Unit tests cover pure TypeScript; skip the app's Tailwind PostCSS pipeline.
  css: { postcss: { plugins: [] } },
  test: { include: ["src/**/*.test.ts"], environment: "node" },
});

import { defineConfig, mergeConfig } from "vitest/config";

import viteConfig from "./vite.config";

// Kept separate from vite.config.ts so the app build does not depend on the
// test runner's types.
export default mergeConfig(
  viteConfig,
  defineConfig({
    test: {
      environment: "jsdom",
      globals: true,
      setupFiles: ["./src/test-setup.ts"],
    },
  }),
);

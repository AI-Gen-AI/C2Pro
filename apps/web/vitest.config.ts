import path from "path";
import { fileURLToPath } from "url";

import { defineConfig } from "vitest/config";

const appRoot = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  root: appRoot,
  define: {
    "process.env.VITEST": JSON.stringify("true"),
  },
  esbuild: {
    jsxInject: "import React from 'react'",
  },
  resolve: {
    alias: [
      {
        find: /^@\/mocks\/msw$/,
        replacement: path.resolve(appRoot, "./src/tests/shims/msw.ts"),
      },
      {
        find: /^@\/mocks\/msw-browser$/,
        replacement: path.resolve(appRoot, "./src/tests/shims/msw.ts"),
      },
      {
        find: /^@\/mocks\/msw-node$/,
        replacement: path.resolve(appRoot, "./src/tests/shims/msw-node.ts"),
      },
      {
        find: /^until-async$/,
        replacement: path.resolve(appRoot, "./src/tests/shims/until-async.ts"),
      },
      {
        find: /^@$/,
        replacement: path.resolve(appRoot, "./"),
      },
      {
        find: /^@\//,
        replacement: `${path.resolve(appRoot, "./")}/`,
      },
    ],
  },
  test: {
    environment: "jsdom",
    globals: true,
    pool: "vmThreads",
    setupFiles: ["./vitest.setup.ts"],
    server: {
      deps: {
        inline: true,
        fallbackCJS: true,
      },
    },
    exclude: ["src/tests/e2e/**", "node_modules/**", ".next/**"],
    coverage: {
      provider: "v8",
      reporter: ["text", "json", "html"],
      exclude: [
        "node_modules/",
        ".next/",
        "**/*.config.*",
        "**/*.d.ts",
        "**/types/**",
      ],
    },
  },
});

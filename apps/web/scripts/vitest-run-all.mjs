import { spawn } from "node:child_process";

const commands = [
  [
    "node",
    [
      "./scripts/vitest-no-warn.mjs",
      "run",
      "--exclude",
      "src/tests/integration/**",
      "--config",
      "vitest.config.ts",
    ],
  ],
  [
    "node",
    [
      "./scripts/vitest-no-warn.mjs",
      "run",
      "src/tests/integration",
      "--config",
      "vitest.integration.config.ts",
    ],
  ],
];

for (const [command, args] of commands) {
  const exitCode = await new Promise((resolve) => {
    const child = spawn(command, args, {
      stdio: "inherit",
      shell: true,
    });

    child.on("exit", (code) => resolve(code ?? 1));
  });

  if (exitCode !== 0) {
    process.exit(exitCode);
  }
}

import { spawn } from "node:child_process";
import { resolve } from "node:path";

const vitestPath = resolve("node_modules", "vitest", "vitest.mjs");
const args = process.argv.slice(2);
const suppress = "The CJS build of Vite's Node API is deprecated";

const child = spawn(process.execPath, ["--no-warnings", vitestPath, ...args], {
  stdio: ["inherit", "pipe", "pipe"],
});

const writeFiltered = (chunk, target) => {
  const text = chunk.toString();
  if (text.includes(suppress)) {
    const lines = text.split(/\r?\n/).filter((line) => !line.includes(suppress));
    if (lines.length === 0) return;
    target.write(lines.join("\n"));
    if (text.endsWith("\n")) target.write("\n");
    return;
  }
  target.write(chunk);
};

child.stdout?.on("data", (chunk) => writeFiltered(chunk, process.stdout));
child.stderr?.on("data", (chunk) => writeFiltered(chunk, process.stderr));

child.on("exit", (code) => {
  process.exit(code ?? 1);
});

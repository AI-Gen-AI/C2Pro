import { existsSync, rmSync } from "node:fs";
import { resolve } from "node:path";

const nextDir = resolve(process.cwd(), ".next");

if (existsSync(nextDir)) {
  rmSync(nextDir, { force: true, recursive: true });
}

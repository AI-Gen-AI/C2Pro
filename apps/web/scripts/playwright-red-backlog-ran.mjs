// Usage (from apps/web): node scripts/playwright-red-backlog-ran.mjs
import { main } from "./playwright-red-backlog-check.mjs";

process.exitCode = main();

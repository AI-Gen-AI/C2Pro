/**
 * PJ-01 run recorder: per-step timing, findings and evidence for one browser run.
 *
 * Writes `playwright/.pj01/<run-id>/run.json` plus screenshots. Records identifiers and
 * timings only; never tokens, cookies or credentials.
 *
 * Navigation mode (`PJ01_NAVIGATION_MODE`):
 * - `strict` (default, acceptance): a navigability gap fails the run immediately;
 * - `diagnostic`: the gap is recorded, the step continues by the smallest workaround, and the
 *   run can at best be TECHNICALLY_FUNCTIONAL. Diagnostic runs never count as a PJ-01 PASS.
 */
import { mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";

import type { Page } from "@playwright/test";

import { classifyRun, type Pj01Classification, type RunFinding } from "../../../pj01/classification";

export type NavigationMode = "strict" | "diagnostic";

export interface Pj01StepRecord {
  id: string;
  title: string;
  startedAt: string;
  durationMs: number;
  status: "passed" | "failed";
  error?: string;
}

export class Pj01RunRecorder {
  readonly runId: string;
  readonly dir: string;
  readonly mode: NavigationMode;
  private readonly steps: Pj01StepRecord[] = [];
  private readonly findings: RunFinding[] = [];
  private readonly facts: Record<string, unknown> = {};
  private currentStep = "setup";

  constructor(options: { runId?: string; rootDir?: string; mode?: NavigationMode } = {}) {
    this.runId = options.runId ?? `pj01-${new Date().toISOString().replace(/[:.]/g, "-")}`;
    this.dir = path.join(options.rootDir ?? path.join(process.cwd(), "playwright", ".pj01"), this.runId);
    this.mode = options.mode ?? "strict";
  }

  static fromEnv(): Pj01RunRecorder {
    const mode = process.env.PJ01_NAVIGATION_MODE === "diagnostic" ? "diagnostic" : "strict";
    return new Pj01RunRecorder({ runId: process.env.PJ01_RUN_ID, mode });
  }

  async step<T>(id: string, title: string, action: () => Promise<T>): Promise<T> {
    const started = Date.now();
    this.currentStep = id;
    try {
      const result = await action();
      this.steps.push({ id, title, startedAt: new Date(started).toISOString(), durationMs: Date.now() - started, status: "passed" });
      return result;
    } catch (error) {
      this.steps.push({
        id,
        title,
        startedAt: new Date(started).toISOString(),
        durationMs: Date.now() - started,
        status: "failed",
        error: error instanceof Error ? error.message.split("\n")[0] : String(error),
      });
      throw error;
    }
  }

  /** Non-secret run facts (ids, timings, how a step was reached). */
  record(key: string, value: unknown): void {
    this.facts[key] = value;
  }

  gap(code: string, detail: string, options: { blocking?: boolean } = {}): void {
    this.findings.push({ kind: "gap", code, step: this.currentStep, detail, blocking: options.blocking ?? this.mode === "strict" });
  }

  violation(code: string, detail: string, options: { blocking?: boolean } = {}): void {
    this.findings.push({ kind: "violation", code, step: this.currentStep, detail, blocking: options.blocking ?? true });
  }

  /** Record a navigability gap; in strict mode it also stops the run with a coded error. */
  gapOrStop(code: string, detail: string): void {
    this.gap(code, detail);
    if (this.mode === "strict") throw new Error(`PJ01_${code}: ${detail}`);
  }

  blockingFindings(): RunFinding[] {
    return this.findings.filter((finding) => finding.blocking);
  }

  classification(): Pj01Classification {
    return classifyRun({
      failedSteps: this.steps.filter((step) => step.status === "failed").length,
      findings: this.findings,
    });
  }

  async screenshot(page: Page, label: string): Promise<void> {
    mkdirSync(this.dir, { recursive: true });
    const file = `${String(this.steps.length).padStart(2, "0")}-${label.replace(/[^a-z0-9-]+/gi, "-")}.png`;
    await page.screenshot({ path: path.join(this.dir, file), fullPage: true }).catch(() => undefined);
  }

  write(): string {
    mkdirSync(this.dir, { recursive: true });
    const file = path.join(this.dir, "run.json");
    writeFileSync(
      file,
      JSON.stringify(
        {
          schema: "c2pro-pj01-run/v1",
          runId: this.runId,
          navigationMode: this.mode,
          classification: this.classification(),
          steps: this.steps,
          findings: this.findings,
          facts: this.facts,
        },
        null,
        2,
      ),
      "utf8",
    );
    return file;
  }
}

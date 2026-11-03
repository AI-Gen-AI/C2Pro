/**
 * Integral S1–S8 UAT ledger: one stage record per acceptance step, written as the browser-side half of the
 * evidence manifest.
 *
 * The ledger is deliberately fail-closed and honest:
 *  - a stage is PASS only when every check recorded under it passed and nothing was flagged partial;
 *  - a thrown error marks the stage FAIL, names it as the FIRST failure of the run when it is the first, and (for a
 *    critical stage) stops the run -- later stages are then NOT_RUN, never inferred;
 *  - a check that cannot be exercised on this product/mode is PARTIAL with its reason, never silently PASS;
 *  - nothing here ever stores a token, a cookie, a prompt, a completion or a document body: ids, hashes, statuses,
 *    counts and timings only.
 */
import { createHash } from "node:crypto";
import { mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";

export const STAGE_IDS = ["S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8"] as const;
export type StageId = (typeof STAGE_IDS)[number];
export type StageStatus = "PASS" | "PARTIAL" | "FAIL" | "NOT_RUN";

export interface StageRecord {
  id: StageId;
  title: string;
  status: StageStatus;
  startedAt: string | null;
  durationMs: number;
  checks: Array<{ name: string; ok: boolean; detail?: string }>;
  partial: string[];
  milestones: { required: string[]; reached: string[]; missing: string[] };
  evidence: Record<string, unknown>;
  error?: string;
}

export interface FirstFailure {
  stage: StageId;
  message: string;
}

const firstLine = (error: unknown): string =>
  (error instanceof Error ? error.message : String(error)).split("\n")[0]!.slice(0, 400);

export const sha256Hex = (value: string | Buffer): string => createHash("sha256").update(value).digest("hex");

/** A stable digest of any JSON value (keys sorted), used to show two snapshots are identical without storing them. */
export function digestOf(value: unknown): string {
  const sort = (input: unknown): unknown => {
    if (Array.isArray(input)) return input.map(sort);
    if (input && typeof input === "object") {
      return Object.fromEntries(
        Object.entries(input as Record<string, unknown>)
          .sort(([a], [b]) => a.localeCompare(b))
          .map(([key, inner]) => [key, sort(inner)]),
      );
    }
    return input;
  };
  return sha256Hex(JSON.stringify(sort(value)));
}

/** A failure inside a stage entered from another stage: already recorded; the outer stage only unwinds. */
class NestedStageFailure extends Error {}

interface Internal {
  id: StageId;
  title: string;
  touched: boolean;
  startedAt: string | null;
  durationMs: number;
  checks: Array<{ name: string; ok: boolean; detail?: string }>;
  partial: string[];
  required: string[];
  reached: Set<string>;
  evidence: Record<string, unknown>;
  error?: string;
}

/**
 * A stage may be entered several times (the journey interleaves them: the contract is approved in S5 before the
 * budget is uploaded in S2). Its status is derived, never asserted: FAIL on an error or a failed check; otherwise
 * PARTIAL when something was flagged or a REQUIRED milestone was never reached (a halted run cannot pass a stage it
 * did not finish); PASS only when everything required was reached; NOT_RUN when the stage was never entered.
 */
export class IntegralLedger {
  private readonly stages = new Map<StageId, Internal>();
  private readonly facts: Record<string, unknown> = {};
  private failure: FirstFailure | null = null;
  private current: StageId | null = null;
  private halted = false;

  constructor(
    titles: Record<StageId, string>,
    required: Partial<Record<StageId, string[]>> = {},
  ) {
    for (const id of STAGE_IDS) {
      this.stages.set(id, {
        id,
        title: titles[id],
        touched: false,
        startedAt: null,
        durationMs: 0,
        checks: [],
        partial: [],
        required: required[id] ?? [],
        reached: new Set(),
        evidence: {},
      });
    }
  }

  get firstFailure(): FirstFailure | null {
    return this.failure;
  }

  get isHalted(): boolean {
    return this.halted;
  }

  private fail(id: StageId, message: string): void {
    if (!this.failure) this.failure = { stage: id, message: message.slice(0, 400) };
  }

  /** Run (part of) a stage. A critical stage that throws halts the run; later work stays NOT_RUN. */
  async stage<T>(id: StageId, action: () => Promise<T>, options: { critical?: boolean } = {}): Promise<T | undefined> {
    if (this.halted) {
      if (this.current !== null) throw new NestedStageFailure();
      return undefined;
    }
    const record = this.stages.get(id)!;
    const started = Date.now();
    record.touched = true;
    record.startedAt ??= new Date(started).toISOString();
    const previous = this.current;
    this.current = id;
    try {
      return await action();
    } catch (error) {
      if (error instanceof NestedStageFailure) return undefined;
      record.error ??= firstLine(error);
      this.fail(id, firstLine(error));
      if (options.critical !== false) this.halted = true;
      if (previous !== null && this.halted) throw new NestedStageFailure();
      return undefined;
    } finally {
      record.durationMs += Date.now() - started;
      this.current = previous;
    }
  }

  /** A non-throwing assertion. A false check fails the stage but lets the remaining checks of that stage run. */
  check(name: string, ok: boolean, detail?: string): boolean {
    const record = this.record();
    record.checks.push({ name, ok, ...(detail ? { detail: detail.slice(0, 300) } : {}) });
    if (!ok) this.fail(record.id, `${name}${detail ? `: ${detail}` : ""}`);
    return ok;
  }

  /** The stage reached one of its required checkpoints (see the constructor). */
  milestone(name: string): void {
    this.record().reached.add(name);
  }

  /** Something this run could not exercise (stated, never hidden). Makes the stage PARTIAL at best. */
  partial(reason: string): void {
    this.record().partial.push(reason.slice(0, 300));
  }

  evidence(key: string, value: unknown): void {
    this.record().evidence[key] = value;
  }

  fact(key: string, value: unknown): void {
    this.facts[key] = value;
  }

  private record(): Internal {
    if (!this.current) throw new Error("INTEGRAL_LEDGER_NO_ACTIVE_STAGE");
    return this.stages.get(this.current)!;
  }

  private render(record: Internal): StageRecord {
    const missing = record.required.filter((name) => !record.reached.has(name));
    let status: StageStatus;
    if (!record.touched) status = "NOT_RUN";
    else if (record.error || record.checks.some((check) => !check.ok)) status = "FAIL";
    else if (record.partial.length > 0 || missing.length > 0) status = "PARTIAL";
    else status = "PASS";
    return {
      id: record.id,
      title: record.title,
      status,
      startedAt: record.startedAt,
      durationMs: record.durationMs,
      checks: record.checks,
      partial: record.partial,
      milestones: { required: record.required, reached: [...record.reached], missing },
      evidence: record.evidence,
      ...(record.error ? { error: record.error } : {}),
    };
  }

  snapshot(): { stages: StageRecord[]; facts: Record<string, unknown>; firstFailure: FirstFailure | null } {
    return {
      stages: STAGE_IDS.map((id) => this.render(this.stages.get(id)!)),
      facts: { ...this.facts },
      firstFailure: this.failure,
    };
  }

  write(file: string, header: Record<string, unknown>): string {
    mkdirSync(path.dirname(file), { recursive: true });
    writeFileSync(
      file,
      `${JSON.stringify({ schema: "c2pro-integral-s1-s8-browser/v1", ...header, ...this.snapshot() }, null, 2)}\n`,
      "utf8",
    );
    return file;
  }
}

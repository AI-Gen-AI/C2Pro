"use client";

/**
 * Test Suite ID: TS-E2E-COH-V1-09
 * Demo route for Coherence v1 customer-facing QA scenarios.
 */

import { useState } from "react";
import { AlertReviewCenter } from "@/components/features/alerts/AlertReviewCenter";
import { CoherenceClient } from "@/components/coherence/CoherenceClient";
import type { DashboardSummary } from "@/lib/api/contracts";

const CONTRACT_ONLY_SUMMARY: DashboardSummary = {
  project_id: "proj_demo_001",
  tenant_id: "tenant-demo",
  coherence_score: null,
  global_score: null,
  sub_scores: {},
  weights_used: {},
  alert_count: 1,
  document_count: 1,
  methodology_version: "v1",
  score_version: "coherence-v1",
  score_reason: "insufficient_evidence",
  score_missing_dimensions: ["schedule", "budget"],
  last_updated: "2026-05-01T00:00:00Z",
};

const FULL_TRIPLET_SUMMARY: DashboardSummary = {
  project_id: "proj_demo_001",
  tenant_id: "tenant-demo",
  coherence_score: 82,
  global_score: 82,
  sub_scores: {
    SCOPE: 84,
    BUDGET: 78,
    QUALITY: 86,
    TECHNICAL: 80,
    LEGAL: 88,
    TIME: 76,
  },
  weights_used: {
    SCOPE: 0.17,
    BUDGET: 0.17,
    QUALITY: 0.16,
    TECHNICAL: 0.16,
    LEGAL: 0.17,
    TIME: 0.17,
  },
  alert_count: 3,
  document_count: 3,
  methodology_version: "v1",
  score_version: "coherence-v1",
  score_reason: null,
  score_missing_dimensions: [],
  last_updated: "2026-05-01T00:00:00Z",
};

const HISTORICAL_V0_SUMMARY: DashboardSummary = {
  ...FULL_TRIPLET_SUMMARY,
  coherence_score: 91,
  global_score: 91,
  score_version: "coherence-v1",
  methodology_version: "v0",
  last_updated: "2026-04-15T00:00:00Z",
};

export default function DemoCoherenceV1Page() {
  const [summary, setSummary] = useState<DashboardSummary>(CONTRACT_ONLY_SUMMARY);

  return (
    <main className="mx-auto max-w-6xl space-y-6 px-4 py-8">
      <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-normal text-muted-foreground">
            Demo / Coherence v1
          </p>
          <h1 className="text-2xl font-semibold">Customer QA Scenario</h1>
        </div>
        <button
          className="inline-flex h-10 items-center justify-center rounded-md bg-primary px-4 text-sm font-semibold text-primary-foreground"
          type="button"
          onClick={() => setSummary(FULL_TRIPLET_SUMMARY)}
        >
          Supply schedule and budget
        </button>
        <button
          className="inline-flex h-10 items-center justify-center rounded-md border border-border bg-background px-4 text-sm font-semibold"
          type="button"
          onClick={() => setSummary(HISTORICAL_V0_SUMMARY)}
        >
          Show v0 historical row
        </button>
      </div>

      <CoherenceClient summary={summary} />

      <section
        aria-label="Email template preview"
        className="rounded-md border bg-card p-5 text-sm shadow-sm"
      >
        <p className="text-xs font-semibold uppercase tracking-normal text-muted-foreground">
          Email template preview
        </p>
        <h2 className="mt-1 text-lg font-semibold">Coherence Score v1 is active</h2>
        <p className="mt-2 text-muted-foreground">
          New scores use weighted finding severity, confidence, and project scope. Contract-only
          uploads now produce AUDIT_INCOMPLETE until schedule and budget evidence are supplied.
        </p>
      </section>

      <AlertReviewCenter
        projectId="proj_demo_001"
        alerts={[
          {
            id: "audit-incomplete",
            title: "AUDIT_INCOMPLETE: schedule and budget evidence missing",
            severity: "medium",
            status: summary.coherence_score == null ? "pending" : "approved",
            clauseId: "audit-meta",
            assignee: "project.manager",
          },
          {
            id: "legal-302",
            title: "Unlimited IP indemnity conflicts with licensor cap",
            severity: "high",
            status: "pending",
            clauseId: "clause-302",
            assignee: "legal.owner",
          },
        ]}
      />
    </main>
  );
}

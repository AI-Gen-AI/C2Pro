/**
 * PJ-01 shared browser harness.
 *
 * First half: Login → Create Project → Upload Contract A → Processing (to the mandatory human
 * review) → HITL approval → processing resumes → Health → six dimensions → toward Evidence, on the
 * deterministic PJ-01 Contract A fixture.
 * Second half: Upload revision B → processing to its own human review → What Changed? → Health and
 * Current State still on revision A while B is pending → HITL approval of B → processing resumes →
 * Health and Current State on revision B.
 *
 * Consumers (the What Changed spec, the Health → Evidence spec, the integrated PJ-01
 * acceptance run) call `runPj01FirstHalf` and continue from the returned project and
 * document, instead of re-implementing sign-in, upload and processing.
 */
import { mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";

import type { Page } from "@playwright/test";

import {
  contractAPdfPath,
  healthExpectationsFromManifest,
  loadContractAManifest,
  type Pj01ContractFixtureManifest,
} from "../../../pj01/fixture-contract";
import { evaluateHealthSourceDocument, type HealthVectorPayload } from "../../../pj01/health-evaluator";
import { contractBPdfPath, loadContractBManifest } from "../../../pj01/revision-fixture";
import { assertCurrentStateThroughNavigation } from "./current-state";
import { navigateTowardEvidence } from "./evidence";
import { assertSixHealthDimensions, openHealthThroughNavigation } from "./health";
import { observeProcessingWithoutReload, type ProcessingObservation } from "./processing";
import { approvePendingReviewThroughUi, returnToDocuments, type ReviewDecision } from "./review";
import { uploadNewVersionThroughUi, type RevisionUploadResult } from "./revision";
import { judgeHealthEvidenceRevision, readHealthEvidenceRevision } from "./revision-authority";
import type { Pj01RunRecorder } from "./run-recorder";
import { createProjectThroughUi, signInAsJourneyUser } from "./session";
import { uploadDocumentThroughUi } from "./upload";
import {
  assertNoDuplicateChangeEvent,
  assertWhatChangedThroughNavigation,
  type WhatChangedResult,
} from "./what-changed";

/** With the AI provider deterministic every analysis is "not assessed" and MUST wait for a human. */
const AI_IS_MOCKED = process.env.C2PRO_AI_MOCK === "1";

export const PJ01_PROJECT_ID_FILE = path.join(process.cwd(), "playwright", ".pj01", "project-id.txt");

export interface Pj01FirstHalfResult {
  projectId: string;
  documentId: string;
  manifest: Pj01ContractFixtureManifest;
  /** The wait that ended at the human-review gate (or at "analyzed" when no review was needed). */
  processing: ProcessingObservation;
  /** The person's decision on revision A; null when the analysis finished without needing one. */
  review: ReviewDecision | null;
  /** The wait after that decision, up to "analyzed". */
  resumed: ProcessingObservation;
  health: HealthVectorPayload;
  /** The revision Health cites for revision A (read from Evidence). */
  revisionAId: string | null;
}

/** What the wait saw, in one line, so a failed run explains itself in the CI log. */
function describeObservation(observed: ProcessingObservation): string {
  const stages = [...new Set(observed.timeline.polls.map((poll) => poll.stage))].join(">") || "none";
  const labels = [...new Set(observed.timeline.uiSamples.map((sample) => sample.label))].join(" | ") || "none";
  return `polls=${observed.timeline.polls.length} backendStages=${stages} uiLabels=${labels} reloads=${observed.reloads}`;
}

interface HumanGateResult {
  gate: ProcessingObservation;
  review: ReviewDecision | null;
  resumed: ProcessingObservation;
}

/**
 * Processing exactly as a waiting user lives it: the wait ends at the mandatory human review, a
 * person decides it through the review queue, and processing resumes until the document is analyzed.
 * Nothing is skipped: a missing gate under the deterministic provider is itself a violation.
 */
async function processThroughHumanReview(
  page: Page,
  recorder: Pj01RunRecorder,
  options: { projectId: string; documentId: string; generation: number; label: string; stepId: string },
): Promise<HumanGateResult> {
  const { projectId, documentId, generation, label, stepId } = options;
  const gate = await recorder.step(`${stepId}`, `Processing ${label} until the human-review gate`, async () => {
    const observed = await observeProcessingWithoutReload(page, recorder, { projectId, documentId, settlement: "review_required" });
    await recorder.screenshot(page, `${stepId.toLowerCase()}-gate`);
    if (observed.evaluation.violations.length > 0 || !["review_required", "analyzed"].includes(observed.evaluation.outcome)) {
      const codes = observed.evaluation.violations.map((violation) => violation.code).join(", ");
      throw new Error(`PJ01_PROCESSING: ${label}: outcome=${observed.evaluation.outcome} violations=[${codes}] ${describeObservation(observed)}`);
    }
    return observed;
  });

  if (gate.evaluation.outcome === "analyzed") {
    if (AI_IS_MOCKED) {
      recorder.violation("HITL_GATE_NOT_EXERCISED", `${label}: analysis finished without the mandatory human review while the AI is mocked`);
    }
    return { gate, review: null, resumed: gate };
  }

  const review = await recorder.step(`${stepId}b`, `Human decision on ${label} through the review queue`, () =>
    approvePendingReviewThroughUi(page, recorder, { projectId, documentId, expectedGeneration: generation, label }),
  );
  const resumed = await recorder.step(`${stepId}c`, `Processing resumes after the decision on ${label}`, async () => {
    const observed = await observeProcessingWithoutReload(page, recorder, {
      projectId,
      documentId,
      trigger: () => returnToDocuments(page, recorder, projectId),
    });
    await recorder.screenshot(page, `${stepId.toLowerCase()}c-resumed`);
    if (observed.evaluation.outcome !== "analyzed" || observed.evaluation.violations.length > 0) {
      const codes = observed.evaluation.violations.map((violation) => violation.code).join(", ");
      throw new Error(`PJ01_PROCESSING_AFTER_REVIEW: ${label}: outcome=${observed.evaluation.outcome} violations=[${codes}] ${describeObservation(observed)}`);
    }
    return observed;
  });
  return { gate, review, resumed };
}

export async function runPj01FirstHalf(
  page: Page,
  options: { baseURL: string; recorder: Pj01RunRecorder; projectName?: string },
): Promise<Pj01FirstHalfResult> {
  const { recorder } = options;
  const manifest = loadContractAManifest();
  recorder.record("fixture", manifest.fixture_id);

  const observation = await recorder.step("PJ01-S1", "Login", async () => {
    const auth = await signInAsJourneyUser(page, options.baseURL);
    await recorder.screenshot(page, "s1-projects");
    return auth;
  });

  const projectId = await recorder.step("PJ01-S2", "Create project", async () => {
    const id = await createProjectThroughUi(page, observation, options.projectName ?? `PJ-01 ${recorder.runId}`);
    mkdirSync(path.dirname(PJ01_PROJECT_ID_FILE), { recursive: true });
    writeFileSync(PJ01_PROJECT_ID_FILE, id, "utf8");
    recorder.record("projectId", id);
    await recorder.screenshot(page, "s2-documents-empty");
    return id;
  });

  const { documentId } = await recorder.step("PJ01-S3", "Upload Contract A", async () => {
    const result = await uploadDocumentThroughUi(page, recorder, {
      projectId,
      filePath: contractAPdfPath(manifest),
      documentType: manifest.document_type,
    });
    await recorder.screenshot(page, "s3-upload-accepted");
    return result;
  });

  const { gate: processing, review, resumed } = await processThroughHumanReview(page, recorder, {
    projectId,
    documentId,
    generation: 1,
    label: "Contract A",
    stepId: "PJ01-S4",
  });

  const health = await recorder.step("PJ01-S5", "Reach Health through navigation", async () => {
    const vector = await openHealthThroughNavigation(page, recorder, { projectId });
    await recorder.screenshot(page, "s5-health");
    return vector;
  });

  await recorder.step("PJ01-S6", "Assert six Health dimensions", async () => {
    await assertSixHealthDimensions(page, recorder, health, healthExpectationsFromManifest(manifest));
    // Health → Evidence authority: the assessment must name the uploaded document itself.
    for (const violation of evaluateHealthSourceDocument(health, documentId)) {
      recorder.violation(`HEALTH_${violation.code}`, violation.detail);
    }
    recorder.record("healthSourceDocumentId", health.single_document_coverage?.document_id ?? null);
  });

  await recorder.step("PJ01-S7", "Follow Health supporting clause into Evidence", async () => {
    await navigateTowardEvidence(page, recorder, { projectId, documentId, health });
    await recorder.screenshot(page, "s7-evidence");
  });

  // Which revision does Health rest on once revision A is approved? Read from Evidence.
  const revisionAId = await recorder.step("PJ01-S7b", "Health rests on revision A", async () => {
    const read = await readHealthEvidenceRevision(page, recorder, {
      projectId,
      documentId,
      notBefore: review?.approvedAt,
    });
    if (!read.revisionId) {
      recorder.violation("REVISION_AUTHORITY_EVIDENCE_CLAUSE_UNRESOLVED", `Health cites ${read.clauseId} but Evidence names no revision for it`);
    }
    recorder.record("healthEvidenceRevision.A", { clauseId: read.clauseId, revisionId: read.revisionId, attempts: read.attempts });
    return read.revisionId;
  });

  return { projectId, documentId, manifest, processing, review, resumed, health, revisionAId };
}

export interface Pj01SecondHalfResult {
  revision: RevisionUploadResult;
  revisionProcessing: ProcessingObservation;
  revisionReview: ReviewDecision | null;
  whatChanged: WhatChangedResult;
}

/**
 * Second half: Upload revision B → its processing up to its own human review → What Changed? →
 * Health/Current State still on revision A while B is pending → HITL approval of B → processing
 * resumes → Health/Current State on revision B. Revision B is the deterministic Contract B fixture;
 * every revision, event and report is generated by the application itself, and the expected
 * identities and changes are derived from the committed Contract A/B files and manifests.
 */
export async function runPj01SecondHalf(
  page: Page,
  options: { recorder: Pj01RunRecorder; first: Pj01FirstHalfResult },
): Promise<Pj01SecondHalfResult> {
  const { recorder, first } = options;
  const revisionManifest = loadContractBManifest();
  recorder.record("revisionFixture", revisionManifest.fixture_id);

  const revision = await recorder.step("PJ01-S8", "Upload revision B of the same document", async () => {
    const result = await uploadNewVersionThroughUi(page, recorder, {
      projectId: first.projectId,
      documentId: first.documentId,
      filePath: contractBPdfPath(revisionManifest),
      expectedVersion: 2,
    });
    await recorder.screenshot(page, "s8-revision-accepted");
    return result;
  });

  // Revision B waits at its own gate. Everything between here and the decision is judged while B is
  // PENDING, so the human step is deliberately split around those checks.
  const revisionProcessing = await recorder.step("PJ01-S9", "Revision B processing until the human-review gate", async () => {
    const observed = await observeProcessingWithoutReload(page, recorder, {
      projectId: first.projectId,
      documentId: first.documentId,
      settlement: "review_required",
    });
    await recorder.screenshot(page, "s9-revision-gate");
    if (observed.evaluation.violations.length > 0 || !["review_required", "analyzed"].includes(observed.evaluation.outcome)) {
      const codes = observed.evaluation.violations.map((violation) => violation.code).join(", ");
      throw new Error(`PJ01_REVISION_PROCESSING: outcome=${observed.evaluation.outcome} violations=[${codes}] ${describeObservation(observed)}`);
    }
    return observed;
  });
  const pending = revisionProcessing.evaluation.outcome === "review_required";
  if (!pending && AI_IS_MOCKED) {
    recorder.violation("HITL_GATE_NOT_EXERCISED", "revision B finished without the mandatory human review while the AI is mocked");
  }

  const whatChanged = await recorder.step("PJ01-S10", "What Changed? for revision B", async () =>
    assertWhatChangedThroughNavigation(page, recorder, {
      projectId: first.projectId,
      documentId: first.documentId,
      contractAPdf: contractAPdfPath(first.manifest),
      contractBPdf: contractBPdfPath(revisionManifest),
      base: first.manifest,
      revision: revisionManifest,
    }),
  );

  if (first.revisionAId && first.revisionAId !== whatChanged.sourceRevisionId) {
    recorder.violation(
      "REVISION_A_IDENTITY",
      `Health cited revision ${first.revisionAId} for contract A but What Changed names ${whatChanged.sourceRevisionId} as its source revision`,
    );
  }

  if (pending) {
    await recorder.step("PJ01-S10b", "While B is pending, Health still rests on revision A", async () => {
      const read = await readHealthEvidenceRevision(page, recorder, { projectId: first.projectId, documentId: first.documentId });
      judgeHealthEvidenceRevision(recorder, read, {
        expectedRevisionId: whatChanged.sourceRevisionId,
        otherRevisionId: whatChanged.targetRevisionId,
        phase: "B-pending",
      });
      await recorder.screenshot(page, "s10b-evidence-while-pending");
    });
    await recorder.step("PJ01-S11a", "Current State while revision B is pending", async () => {
      await assertCurrentStateThroughNavigation(page, recorder, { projectId: first.projectId, phase: "pending-review" });
    });
  }

  let approvedReview: ReviewDecision | null = null;
  if (pending) {
    approvedReview = await recorder.step("PJ01-S12", "Human decision on revision B through the review queue", () =>
      approvePendingReviewThroughUi(page, recorder, {
        projectId: first.projectId,
        documentId: first.documentId,
        expectedGeneration: 2,
        label: "Revision B",
      }),
    );
    await recorder.step("PJ01-S12c", "Processing resumes after the decision on revision B", async () => {
      const observed = await observeProcessingWithoutReload(page, recorder, {
        projectId: first.projectId,
        documentId: first.documentId,
        trigger: () => returnToDocuments(page, recorder, first.projectId),
      });
      await recorder.screenshot(page, "s12c-revision-resumed");
      if (observed.evaluation.outcome !== "analyzed" || observed.evaluation.violations.length > 0) {
        const codes = observed.evaluation.violations.map((violation) => violation.code).join(", ");
        throw new Error(`PJ01_REVISION_PROCESSING_AFTER_REVIEW: outcome=${observed.evaluation.outcome} violations=[${codes}] ${describeObservation(observed)}`);
      }
    });
  }

  await recorder.step("PJ01-S13", "After the decision, Health rests on revision B", async () => {
    const read = await readHealthEvidenceRevision(page, recorder, {
      projectId: first.projectId,
      documentId: first.documentId,
      notBefore: approvedReview?.approvedAt,
    });
    judgeHealthEvidenceRevision(recorder, read, {
      expectedRevisionId: whatChanged.targetRevisionId,
      otherRevisionId: whatChanged.sourceRevisionId,
      phase: "B-approved",
    });
    await recorder.screenshot(page, "s13-evidence-after-approval");
  });

  await recorder.step("PJ01-S14", "Current State after revision B is approved", async () => {
    await assertCurrentStateThroughNavigation(page, recorder, {
      projectId: first.projectId,
      phase: "approved",
      approvedAt: approvedReview?.approvedAt ?? whatChanged.occurredAt,
    });
  });

  await recorder.step("PJ01-S15", "The approval does not create a second change", async () => {
    await assertNoDuplicateChangeEvent(page, recorder, {
      projectId: first.projectId,
      documentId: first.documentId,
      changeEventId: whatChanged.changeEventId,
    });
  });

  return { revision, revisionProcessing, revisionReview: approvedReview, whatChanged };
}

/**
 * TS-E2E-INTEGRAL-S1S8-001 — the integral ACC-01 S1–S8 UAT: ONE project, from the first login to the relogin.
 *
 * One sequential scenario. User A (a real Clerk Development identity) creates ONE project through the wizard and
 * every later stage works on THAT project: four documents uploaded through the upload dialog (contract, budget,
 * schedule, technical specification) plus one deliberately wrong draft that a reviewer rejects, human decisions
 * through the review queue, six-dimension Health, an honest Score, persisted alerts with their source, a contract
 * revision B (pending, then approved), a canonical WBS and three human-approved source links, and finally a real
 * sign-out and a NEW login of the same user in an empty browser context that must find everything unchanged.
 * User B (a second Clerk Development identity, another Organization and tenant) owns a project of its own; the
 * denial between the two tenants is proved in both directions, before and after the relogin.
 *
 * NOTHING is seeded for the journey: the database is only prepared with the two tenants (seed_integral_uat.py).
 * NOTHING is forged: every document, revision, review, alert, WBS baseline and link is created by the application
 * in answer to what the signed-in person does here.
 *
 * The runner is FAIL-CLOSED and states what it could not prove: every stage is judged from milestones it must
 * reach; a failure records the FIRST failing stage and the run stops there (later stages are NOT_RUN, never inferred);
 * what the product cannot do today is PARTIAL with its reason, never a PASS. The browser half of the evidence
 * manifest is written to playwright-report/integral-browser-manifest.json (ids, hashes, statuses, timings; never a
 * token, a cookie, a prompt, a completion or a document body). verify_integral_s1_s8_pg.py then re-reads PostgreSQL
 * independently, on the same project id.
 *
 * Modes: with C2PRO_AI_MOCK=1 the AI provider is deterministic (a no-cost rehearsal of the runner, NEVER UAT);
 * with C2PRO_AI_MOCK=0 the run is the real-AI UAT. The mode is recorded in the manifest and in every verdict.
 */
import { mkdirSync } from "node:fs";
import path from "node:path";

import { expect, test, type Page } from "@playwright/test";

import { callApi, itemsOf, str, type Json } from "./support/integral/api";
import {
  DENIAL,
  DEV_B_EMAIL_ENV,
  clerkIdentity,
  denialsFor,
  developmentBEmail,
  pseudonym,
  signInTenantB,
  type ClerkIdentity,
} from "./support/integral/identity";
import {
  FILES,
  LOCATORS,
  TECHNICAL_SECTION,
  filePath,
  pinnedSha,
  revisionB,
  triplet,
} from "./support/integral/fixtures";
import {
  approveCanonicalWbs,
  approveStructuredLink,
  approveTechnicalLink,
  approveThroughUi,
  listDocuments,
  openProjectTab,
  readAlerts,
  readCurrentState,
  readDashboard,
  readHealth,
  readLinks,
  readRevisions,
  readWhatChanged,
  rejectThroughUi,
  waitForDocument,
  waitForSixDimensionHealth,
  type WbsBaseline,
} from "./support/integral/flow";
import { IntegralLedger, digestOf, sha256Hex, type StageId } from "./support/integral/ledger";
import { Pj01RunRecorder } from "./support/pj01/run-recorder";
import { uploadNewVersionThroughUi } from "./support/pj01/revision";
import { createProjectThroughUi, signInAsJourneyUser } from "./support/pj01/session";
import { uploadDocumentThroughUi } from "./support/pj01/upload";

const AI_MOCK = process.env.C2PRO_AI_MOCK === "1";
const TENANT_B_EMAIL = developmentBEmail();
const REPORT_DIR = path.join(process.cwd(), "playwright-report");
const BROWSER_MANIFEST = path.join(REPORT_DIR, "integral-browser-manifest.json");
const EMPTY_SESSION = { cookies: [], origins: [] };
const REJECTION_REASON =
  "The draft sets a 5 MPa concrete strength: the figure is implausible for structural work. Re-issue the specification.";

/**
 * What the PRODUCT cannot do today, stated in every manifest next to the stage it limits, with the minimum
 * correction. A gap is never turned into a PASS; closing one is a product change with its own review.
 */
const PRODUCT_GAPS = [
  {
    stage: "S4",
    gap: "an alert leads to its contract clause; the Budget row and the Schedule activity it also rests on are named in the evidence text, not linked",
    minimalCorrection: "carry the source locator (sheet!row) of each cited structured row in detection_evidence and render it as a link to the revision",
  },
  {
    stage: "S5",
    gap: "granular per-finding decisions (CONFIRMED / DISMISSED) exist as a use case over an append-only ledger but have no HTTP route and no UI control",
    minimalCorrection: "expose RecordFindingDecisionUseCase as POST /hitl/queue/{item}/findings/{finding}/decision and add the controls to the review card; a run also needs a provider that yields findings",
  },
  {
    stage: "S7",
    gap: "the WBS baseline is approved by the same human who submitted it (a tenant with one human): separation of duties is not satisfied",
    minimalCorrection: "a second human administrator in the tenant (or an independent approval); the run records self_approved and never equates it with an independent approval",
  },
] as const;

const TITLES: Record<StageId, string> = {
  S1: "Two Clerk identities in different tenants; project created through the UI; foreign tenant denied",
  S2: "Four sources uploaded through the dialog with pinned bytes; unsupported file refused",
  S3: "Six-dimension Health, honest Score with reason, persisted alerts",
  S4: "An alert leads to its trusted source revision",
  S5: "Human decisions: final approvals, a rejection with a reason, a rejected proposal never trusted",
  S6: "Contract revision B: pending next to trusted A, What Changed, Current State, approval",
  S7: "Approved canonical WBS and three human-approved source links",
  S8: "Real sign-out, new login of the same user, identical persisted state, tenants denied both ways",
};

const REQUIRED: Partial<Record<StageId, string[]>> = {
  S1: ["tenant-a-identity", "tenant-b-identity", "tenants-differ", "project-a-created", "project-b-created", "a-to-b-denied", "b-to-a-denied"],
  S2: ["unsupported-refused", "contract-uploaded", "budget-uploaded", "schedule-uploaded", "specification-uploaded", "rejected-candidate-uploaded", "bytes-pinned"],
  S3: ["health-six-dimensions", "evaluated", "score-honest", "alerts-persisted"],
  S4: ["alert-opened", "source-resolved"],
  S5: ["contract-approved", "specification-approved", "candidate-rejected", "rejected-never-trusted"],
  S6: ["revision-b-pending", "a-still-trusted", "what-changed", "current-state-pending", "revision-b-approved", "current-state-approved"],
  S7: ["wbs-approved", "link-budget", "link-schedule", "link-technical", "links-current"],
  S8: ["signed-out", "relogin-same-user", "state-identical", "a-to-b-denied-after", "b-to-a-denied-after"],
};

test.describe("TS-E2E-INTEGRAL-S1S8-001: one project from login to relogin", () => {
  test.beforeEach(({ browserName }, testInfo) => {
    // Opt-in only: the integral UAT workflow sets INTEGRAL_UAT=1; nothing else may run this journey by accident.
    testInfo.skip(process.env.INTEGRAL_UAT !== "1", `set INTEGRAL_UAT=1 to run the integral S1-S8 UAT (${browserName})`);
  });

  test("S1–S8 in one persisted project, two tenants, real Clerk", async ({ browser, baseURL }) => {
    test.setTimeout(2_700_000);
    const base = baseURL ?? "http://localhost:3100";
    mkdirSync(REPORT_DIR, { recursive: true });
    const ledger = new IntegralLedger(TITLES, REQUIRED);
    const recorder = new Pj01RunRecorder({ runId: `integral-${new Date().toISOString().replace(/[:.]/g, "-")}` });
    const tag = Date.now().toString(36);

    const state: {
      projectA: string;
      projectB: string;
      identityA?: ClerkIdentity;
      identityB?: ClerkIdentity;
      contract?: { documentId: string; revisionA?: string; revisionB?: string };
      budget?: { documentId: string };
      schedule?: { documentId: string };
      specification?: { documentId: string };
      rejected?: { documentId: string };
      documentIds: Record<string, string>;
      wbs?: WbsBaseline;
      reviewIds: Record<string, string>;
      eventIds: Record<string, string>;
      snapshotDigests: { before?: string; after?: string };
      dynamicGaps: Array<{ stage: string; gap: string; minimalCorrection: string }>;
    } = { projectA: "", projectB: "", documentIds: {}, reviewIds: {}, eventIds: {}, snapshotDigests: {}, dynamicGaps: [] };

    // The page of user A; replaced by the page of the NEW login at S8.
    const contextA = await browser.newContext({ baseURL: base, storageState: EMPTY_SESSION });
    const pageA = await contextA.newPage();
    let tenantB = null as { page: Page; close: () => Promise<void> } | null;

    const writeManifest = (): void => {
      ledger.write(BROWSER_MANIFEST, {
        generatedAt: new Date().toISOString(),
        mode: AI_MOCK ? "deterministic-rehearsal" : "real-ai-uat",
        aiMock: AI_MOCK,
        evidenceClass: AI_MOCK ? "NIGHTLY_DETERMINISTIC_AI_REHEARSAL (not UAT)" : "UAT_REAL",
        candidateSha: process.env.GITHUB_SHA ?? null,
        frontendRuntimeSha: process.env.FRONTEND_RUNTIME_SHA ?? null,
        projectIdA: state.projectA || null,
        projectIdB: state.projectB || null,
        documentIds: state.documentIds,
        contractRevisionIds: { A: state.contract?.revisionA ?? null, B: state.contract?.revisionB ?? null },
        reviewItemIds: state.reviewIds,
        eventIds: state.eventIds,
        wbs: state.wbs
          ? {
              baselineId: state.wbs.baselineId,
              baselineNo: state.wbs.baselineNo,
              nodeId: state.wbs.childNodeId,
              approvalEventId: state.wbs.approvalEventId,
              selfApproved: state.wbs.selfApproved,
            }
          : null,
        clerkIdentityChecks: {
          a: state.identityA
            ? { user: pseudonym(state.identityA.userId), organization: pseudonym(state.identityA.organizationId), tenant: state.identityA.tenantId }
            : null,
          b: state.identityB
            ? { user: pseudonym(state.identityB.userId), organization: pseudonym(state.identityB.organizationId), tenant: state.identityB.tenantId }
            : null,
          distinctUsers: Boolean(state.identityA && state.identityB && state.identityA.userId !== state.identityB.userId),
          distinctOrganizations: Boolean(state.identityA && state.identityB && state.identityA.organizationId !== state.identityB.organizationId),
          distinctTenants: Boolean(state.identityA && state.identityB && state.identityA.tenantId !== state.identityB.tenantId),
        },
        snapshotDigests: state.snapshotDigests,
        productGaps: [...PRODUCT_GAPS, ...state.dynamicGaps],
        pj01RunDirectory: path.basename(recorder.dir),
      });
    };

    try {
      // ═══ S1 ═══════════════════════════════════════════════════════════════════════════════════════════════
      await ledger.stage("S1", async () => {
        ledger.check(`tenant B identity configured (${DEV_B_EMAIL_ENV}, no fallback)`, TENANT_B_EMAIL.length > 0);
        if (!TENANT_B_EMAIL) throw new Error("S1_TENANT_B_IDENTITY_NOT_CONFIGURED");

        const observation = await signInAsJourneyUser(pageA, base);
        state.identityA = await clerkIdentity(pageA);
        ledger.check("Clerk identity A has a user, an active Organization and a tenant", Boolean(state.identityA.userId && state.identityA.organizationId && state.identityA.tenantId));
        ledger.milestone("tenant-a-identity");
        await recorder.screenshot(pageA, "s1-projects");

        state.projectA = await createProjectThroughUi(pageA, observation, `Integral UAT ${tag}`);
        ledger.milestone("project-a-created");
        ledger.evidence("projectA", state.projectA);
        await recorder.screenshot(pageA, "s1-project-a-created");

        tenantB = await signInTenantB(browser, base, TENANT_B_EMAIL);
        state.identityB = await clerkIdentity(tenantB.page);
        ledger.check("Clerk identity B has a user, an active Organization and a tenant", Boolean(state.identityB.userId && state.identityB.organizationId && state.identityB.tenantId));
        ledger.milestone("tenant-b-identity");
        const differ =
          state.identityA.userId !== state.identityB.userId &&
          state.identityA.organizationId !== state.identityB.organizationId &&
          state.identityA.tenantId !== state.identityB.tenantId;
        ledger.check("A and B are different users, Organizations and tenants", differ);
        if (differ) ledger.milestone("tenants-differ");

        const created = await callApi(tenantB.page, "/api/projects", "POST", { name: `Integral UAT tenant B ${tag}` });
        ledger.check("tenant B creates its own project", created.status < 300, `HTTP ${created.status}`);
        state.projectB = str((created.data as Json).id);
        ledger.check("tenant B's project has an id", state.projectB.length > 0);
        const own = await callApi(tenantB.page, `/api/v1/projects/${state.projectB}`);
        ledger.check("tenant B reads its own project", own.status === 200, `HTTP ${own.status}`);
        ledger.milestone("project-b-created");

        const aToB = await denialsFor(pageA, state.projectB);
        ledger.check("A is denied every read of B's project", aToB.every((s) => DENIAL.includes(s)), aToB.join(","));
        if (aToB.every((s) => DENIAL.includes(s))) ledger.milestone("a-to-b-denied");
        const bToA = await denialsFor(tenantB.page, state.projectA);
        ledger.check("B is denied every read of A's project", bToA.every((s) => DENIAL.includes(s)), bToA.join(","));
        if (bToA.every((s) => DENIAL.includes(s))) ledger.milestone("b-to-a-denied");
        ledger.evidence("denials", { aToB, bToA });
      });

      // ═══ S2 + S5: upload and decide, document by document (the order the product requires) ═══════════════
      await ledger.stage("S2", async () => {
        const projectId = state.projectA;
        // The upload dialog refuses an unsupported type and sends nothing.
        const uploadPosts: string[] = [];
        const onRequest = (request: { method(): string; url(): string }): void => {
          if (request.method() === "POST" && new RegExp(`/projects/${projectId}/documents/?$`).test(new URL(request.url()).pathname)) {
            uploadPosts.push(request.url());
          }
        };
        pageA.on("request", onRequest);
        await pageA.getByRole("button", { name: /upload document/i }).click();
        const surface = pageA.getByTestId("document-upload-surface");
        await expect(surface).toBeVisible({ timeout: 15_000 });
        await pageA.setInputFiles('input[type="file"]', {
          name: "payload.bin",
          mimeType: "application/octet-stream",
          buffer: Buffer.from("not a project document"),
        });
        await expect(surface.getByText(/unsupported file type: \.bin/i)).toBeVisible({ timeout: 15_000 });
        pageA.off("request", onRequest);
        ledger.check("a refused file never reaches the backend", uploadPosts.length === 0);
        await pageA.keyboard.press("Escape");
        await expect(surface).toBeHidden({ timeout: 15_000 });
        ledger.milestone("unsupported-refused");

        const upload = async (name: string, documentType: string, key: string): Promise<string> => {
          pinnedSha(name);
          const { documentId, taskId } = await uploadDocumentThroughUi(pageA, recorder, { projectId, filePath: filePath(name), documentType });
          ledger.check(`${name}: the worker was enqueued`, Boolean(taskId));
          state.documentIds[key] = documentId;
          return documentId;
        };

        // Contract A first: it waits for its mandatory human review, which S5 decides before anything else is uploaded.
        const contractId = await upload(FILES.contractA, "contract", "contract");
        state.contract = { documentId: contractId };
        ledger.milestone("contract-uploaded");
        const gate = await waitForDocument(pageA, projectId, contractId, ["review_required", "analyzed"]);
        ledger.check("the contract waits for the mandatory human review", str(gate.lifecycle_status) === "review_required" || !AI_MOCK, str(gate.lifecycle_status));
        if (str(gate.lifecycle_status) !== "review_required") ledger.partial("the contract finished analysis without a human review gate (real AI may not require one)");
        await recorder.screenshot(pageA, "s2-contract-gate");

        await ledger.stage("S5", async () => {
          if (str(gate.lifecycle_status) !== "review_required") {
            ledger.milestone("contract-approved");
            return;
          }
          const decision = await approveThroughUi(pageA, recorder, { projectId, documentId: contractId });
          ledger.check("the approval names who decided", decision.decidedBy.length > 0);
          ledger.check("the approval is of analysis generation 1", decision.generation === 1, String(decision.generation));
          state.reviewIds.contractA = decision.itemId;
          ledger.evidence("contractA", { itemId: decision.itemId, rowId: decision.rowId, status: decision.status, generation: decision.generation });
          await waitForDocument(pageA, projectId, contractId, ["analyzed"]);
          ledger.milestone("contract-approved");
        });
        const revisionsA = await readRevisions(pageA, contractId);
        const trustedA = revisionsA.filter((r) => r.trustState === "trusted");
        ledger.check("contract revision A is the single trusted revision", trustedA.length === 1 && trustedA[0]?.blobHash === pinnedSha(FILES.contractA), JSON.stringify(revisionsA.map((r) => r.trustState)));
        state.contract.revisionA = trustedA[0]?.revisionId;

        const budgetId = await upload(FILES.budget, "budget", "budget");
        state.budget = { documentId: budgetId };
        ledger.milestone("budget-uploaded");
        const scheduleId = await upload(FILES.schedule, "schedule", "schedule");
        state.schedule = { documentId: scheduleId };
        ledger.milestone("schedule-uploaded");
        const specificationId = await upload(FILES.specification, "technical_spec", "specification");
        state.specification = { documentId: specificationId };
        ledger.milestone("specification-uploaded");
        const rejectedId = await upload(FILES.specificationRejected, "technical_spec", "rejectedCandidate");
        state.rejected = { documentId: rejectedId };
        ledger.milestone("rejected-candidate-uploaded");

        await waitForDocument(pageA, projectId, budgetId, ["analyzed"]);
        await waitForDocument(pageA, projectId, scheduleId, ["analyzed"]);
        const specGate = await waitForDocument(pageA, projectId, specificationId, ["review_required", "analyzed"]);
        const rejectedGate = await waitForDocument(pageA, projectId, rejectedId, ["review_required", "analyzed"]);

        // The stored bytes are the pinned fixtures, one document per family, with their genesis revisions.
        const listed = await listDocuments(pageA, projectId);
        const byId = new Map(listed.map((d) => [str(d.id), d]));
        const expectedTypes: Record<string, string> = {
          contract: "contract",
          budget: "budget",
          schedule: "schedule",
          specification: "technical_spec",
          rejectedCandidate: "technical_spec",
        };
        const names: Record<string, string> = {
          contract: FILES.contractA,
          budget: FILES.budget,
          schedule: FILES.schedule,
          specification: FILES.specification,
          rejectedCandidate: FILES.specificationRejected,
        };
        let pinned = true;
        const bytes: Record<string, { documentId: string; revisions: number; blobSha256: string }> = {};
        for (const [key, documentId] of Object.entries(state.documentIds)) {
          const revisions = await readRevisions(pageA, documentId);
          const first = revisions[0];
          const ok = revisions.length === 1 && first?.blobHash === pinnedSha(names[key]!) && str(byId.get(documentId)?.document_type) === expectedTypes[key];
          if (!ok) pinned = false;
          ledger.check(`${names[key]}: one revision, the pinned bytes, the canonical type`, ok, `${revisions.length} revision(s)`);
          bytes[key] = { documentId, revisions: revisions.length, blobSha256: first?.blobHash ?? "" };
        }
        ledger.evidence("storedBytes", bytes);
        if (pinned) ledger.milestone("bytes-pinned");

        await ledger.stage("S5", async () => {
          if (str(specGate.lifecycle_status) === "review_required") {
            const approved = await approveThroughUi(pageA, recorder, { projectId, documentId: specificationId });
            ledger.check("the specification approval names who decided", approved.decidedBy.length > 0);
            state.reviewIds.specification = approved.itemId;
            await waitForDocument(pageA, projectId, specificationId, ["analyzed"]);
          }
          ledger.milestone("specification-approved");

          if (str(rejectedGate.lifecycle_status) !== "review_required") {
            throw new Error(`S5_REJECTION_NOT_POSSIBLE: the draft specification reached ${str(rejectedGate.lifecycle_status)} without a review to reject`);
          }
          const rejected = await rejectThroughUi(pageA, recorder, { projectId, documentId: rejectedId, reason: REJECTION_REASON });
          ledger.check("the rejection names who decided", rejected.decidedBy.length > 0);
          ledger.check("the review ends REJECTED", rejected.status.toUpperCase() === "REJECTED", rejected.status);
          state.reviewIds.rejectedCandidate = rejected.itemId;
          ledger.evidence("rejection", { itemId: rejected.itemId, rowId: rejected.rowId, reasonSha256: sha256Hex(REJECTION_REASON), decidedBy: pseudonym(rejected.decidedBy) });
          ledger.milestone("candidate-rejected");
          const after = (await listDocuments(pageA, projectId)).find((d) => d.id === rejectedId);
          ledger.check("the rejected document does not become Analyzed", str(after?.lifecycle_status) !== "analyzed", str(after?.lifecycle_status));
          const rejectedRevisions = await readRevisions(pageA, rejectedId);
          ledger.check("no revision of the rejected proposal is trusted", rejectedRevisions.every((r) => r.trustState !== "trusted"), JSON.stringify(rejectedRevisions.map((r) => r.trustState)));
          if (rejectedRevisions.every((r) => r.trustState !== "trusted")) ledger.milestone("rejected-never-trusted");
          // Honest scope: an individual finding decision (CONFIRMED / DISMISSED) exists only as a use case
          // over the append-only ledger; it has no HTTP route and no UI control, so a browser cannot take it.
          ledger.partial("granular per-finding decisions are not exercised: no HTTP route or UI control exists for them (use case + ledger are covered by PostgreSQL integration tests)");
        });
      });

      // ═══ S3: Health, evaluation, Score, alerts ═══════════════════════════════════════════════════════════
      const expectedRules = [...triplet.expected_rules, ...triplet.expected_provisional];
      await ledger.stage("S3", async () => {
        const projectId = state.projectA;
        const health = await waitForSixDimensionHealth(pageA, projectId);
        ledger.evidence("health", { computedAt: health.computedAt, compositeBand: health.compositeBand, assessments: health.assessments });
        ledger.milestone("health-six-dimensions");

        await openProjectTab(pageA, projectId, "coherence");
        const evaluateButton = pageA.getByRole("button", { name: /^evaluate coherence$/i });
        await expect(evaluateButton, "evaluation is available once the sources are trusted").toBeEnabled({ timeout: 60_000 });
        const answered = pageA.waitForResponse(
          (response) => response.request().method() === "POST" && /\/coherence\/evaluate/.test(response.url()),
          { timeout: 240_000 },
        );
        await evaluateButton.click();
        const response = await answered;
        ledger.check("the coherence evaluation succeeds", response.status() < 300, `HTTP ${response.status()}`);
        const evaluated = (await response.json()) as {
          overall_score?: number | null;
          score_reason?: string | null;
          score_missing_dimensions?: string[] | null;
          alerts?: Array<{ rule_id?: string }>;
        };
        ledger.milestone("evaluated");

        const missing = evaluated.score_missing_dimensions ?? [];
        const score = evaluated.overall_score ?? null;
        const honest = score === null ? Boolean(evaluated.score_reason) && missing.length > 0 : !(score === 0 && missing.length > 0);
        ledger.check("a null Score states its reason and what is missing; a Score is never 0 for missing evidence", honest, `score=${score} reason=${evaluated.score_reason ?? "none"} missing=${missing.join("|")}`);
        const dashboard = await readDashboard(pageA, projectId);
        ledger.check("the persisted dashboard states the same Score and reason", dashboard.globalScore === score && dashboard.scoreReason === (evaluated.score_reason ?? null), `${dashboard.globalScore}/${dashboard.scoreReason}`);
        ledger.evidence("score", { overall: score, reason: evaluated.score_reason ?? null, missing, version: dashboard.scoreVersion, evaluatedAt: dashboard.evaluatedAt });
        if (honest) ledger.milestone("score-honest");

        const rules = new Set((evaluated.alerts ?? []).map((a) => a.rule_id));
        for (const rule of expectedRules) ledger.check(`${rule} is raised by the evaluation`, rules.has(rule));
        const alerts = await readAlerts(pageA, projectId);
        const persistedRules = new Set(alerts.map((a) => a.ruleCode));
        ledger.check("at least one alert is persisted", alerts.length > 0, `${alerts.length} alert(s)`);
        for (const rule of triplet.expected_rules) ledger.check(`${rule} is persisted`, persistedRules.has(rule));
        ledger.evidence("alerts", alerts.map((a) => ({ id: a.id, ruleCode: a.ruleCode, status: a.status, hasClause: a.sourceClauseId !== null })));
        if (alerts.length > 0) ledger.milestone("alerts-persisted");
      });

      // ═══ S4: alert → source ═════════════════════════════════════════════════════════════════════════════
      await ledger.stage("S4", async () => {
        const projectId = state.projectA;
        await openProjectTab(pageA, projectId, "alerts");
        await expect.poll(async () => pageA.locator("table tbody tr").count(), { timeout: 30_000, message: "the Alerts table lists the persisted alerts" }).toBeGreaterThan(0);
        const evidenceLink = pageA.getByRole("link", { name: /^view evidence for /i }).first();
        await expect(evidenceLink, "an alert links to its source").toBeVisible({ timeout: 30_000 });
        await evidenceLink.click();
        await pageA.waitForURL(new RegExp(`/projects/${projectId}/evidence\\?documentId=`), { timeout: 30_000 });
        await expect(pageA.getByText(/could not load|failed to load/i)).toHaveCount(0);
        await recorder.screenshot(pageA, "s4-evidence");
        ledger.milestone("alert-opened");

        const alerts = await readAlerts(pageA, projectId);
        const withClause = alerts.filter((a) => a.sourceClauseId);
        ledger.check("an alert carries the clause it was detected on", withClause.length > 0, `${alerts.length} alert(s), ${withClause.length} with a clause`);
        const revisionA = state.contract?.revisionA ?? "";
        const document = await callApi(pageA, `/api/v1/documents/${state.contract!.documentId}?revision_id=${revisionA}`);
        const clauses = ((document.data as { clauses?: Json[] }).clauses ?? []);
        const resolved = withClause.filter((alert) => clauses.some((clause) => clause.id === alert.sourceClauseId && clause.revision_id === revisionA));
        ledger.check("that clause belongs to the TRUSTED revision of the contract", resolved.length > 0, `${resolved.length}/${withClause.length} resolved`);
        ledger.evidence("provenance", { alerts: withClause.length, resolvedToTrustedRevision: resolved.length, trustedRevisionId: revisionA });
        if (resolved.length > 0) ledger.milestone("source-resolved");
        // Honest scope: only the clause is a first-class link; the budget/schedule row is named in the evidence text.
        ledger.partial("alert → source is a clause link; the budget/schedule row is named in the evidence text, not linked");
      });

      // ═══ S6: revision B ═════════════════════════════════════════════════════════════════════════════════
      await ledger.stage("S6", async () => {
        const projectId = state.projectA;
        const contractId = state.contract!.documentId;
        const hashA = pinnedSha(FILES.contractA);
        const hashB = pinnedSha(FILES.contractB);
        // What the project says (Health, Score) while revision A is the only trusted contract.
        const healthBeforeB = await readHealth(pageA, projectId);
        const scoreBeforeB = await readDashboard(pageA, projectId);
        await uploadNewVersionThroughUi(pageA, recorder, { projectId, documentId: contractId, filePath: filePath(FILES.contractB), expectedVersion: 2 });
        // The helper expects a one-document project; this project lists five, which is not a finding.
        const findings = recorder.blockingFindings().filter((f) => f.code !== "DOCUMENT_DUPLICATED" && f.step === "setup");
        ledger.check("the new-version upload raised no finding", findings.length === 0, findings.map((f) => f.code).join(","));
        const gate = await waitForDocument(pageA, projectId, contractId, ["review_required", "analyzed"]);
        const pending = str(gate.lifecycle_status) === "review_required";
        ledger.check("revision B waits for its own human review", pending || !AI_MOCK, str(gate.lifecycle_status));
        if (!pending) ledger.partial("revision B finished analysis without a human review gate");
        if (pending) ledger.milestone("revision-b-pending");

        const revisions = await readRevisions(pageA, contractId);
        const revA = revisions.find((r) => r.blobHash === hashA);
        const revB = revisions.find((r) => r.blobHash === hashB);
        ledger.check("two revisions with the pinned A and B bytes", revisions.length === 2 && Boolean(revA) && Boolean(revB), `${revisions.length} revision(s)`);
        state.contract!.revisionB = revB?.revisionId;
        const aTrustedWhilePending = revA?.trustState === "trusted" && revA.isCurrent === true;
        ledger.check("while B is pending, A is still the trusted current revision", aTrustedWhilePending, `${revA?.trustState}/${revA?.isCurrent}`);
        ledger.check("a pending B is never trusted", revB?.trustState !== "trusted", String(revB?.trustState));
        if (aTrustedWhilePending && revB?.trustState !== "trusted") ledger.milestone("a-still-trusted");

        // A pending B changes nothing the project already states: Health and the persisted Score keep resting on the
        // trusted revision A, and "contract_pending_approval" is NOT claimed (it only describes a project whose
        // contract has NO trusted revision yet).
        if (pending) {
          const healthPending = await readHealth(pageA, projectId);
          const scorePending = await readDashboard(pageA, projectId);
          ledger.check(
            "while B is pending, Health still states the assessments that rest on A",
            JSON.stringify(healthPending?.assessments ?? null) === JSON.stringify(healthBeforeB?.assessments ?? null),
          );
          ledger.check(
            "while B is pending, the persisted Score, its version and its reason are those of A",
            scorePending.globalScore === scoreBeforeB.globalScore &&
              scorePending.scoreVersion === scoreBeforeB.scoreVersion &&
              scorePending.scoreReason === scoreBeforeB.scoreReason,
            `${scoreBeforeB.globalScore}/${scoreBeforeB.scoreReason} -> ${scorePending.globalScore}/${scorePending.scoreReason}`,
          );
          ledger.check(
            "contract_pending_approval is not claimed while a trusted revision A stands",
            scorePending.scoreReason !== "contract_pending_approval",
            String(scorePending.scoreReason),
          );
          ledger.evidence("scoreWhileBPending", {
            score: scorePending.globalScore,
            reason: scorePending.scoreReason,
            missing: scorePending.missingDimensions,
          });
        }

        const changed = await readWhatChanged(pageA, recorder, { projectId, documentId: contractId, marker: "garant" });
        ledger.check("What Changed names revision A as the source and B as the target", changed.sourceRevisionId === revA?.revisionId && changed.targetRevisionId === revB?.revisionId);
        ledger.check("its hashes are the pinned A and B files", changed.sourceBlobHash === hashA && changed.targetBlobHash === hashB);
        ledger.check("the change is settled and states the added clause", changed.state === "ready" && changed.changeCount >= 1 && changed.mentionsAddedClause, `state=${changed.state} changes=${changed.changeCount}`);
        state.eventIds.revisionChanged = changed.changeEventId;
        ledger.evidence("whatChanged", { eventId: changed.changeEventId, cause: changed.changeCause, changes: changed.changeCount });
        if (changed.state === "ready") ledger.milestone("what-changed");

        const stateBefore = (await readCurrentState(pageA, recorder, projectId)).find((d) => d.filename === FILES.contractA);
        const okPending = stateBefore?.trustedRevision?.revision_id === revA?.revisionId && stateBefore?.trustedRevision?.blob_hash === hashA && stateBefore?.pendingRevision?.revision_id === revB?.revisionId && stateBefore?.pendingRevision?.blob_hash === hashB;
        ledger.check("Current State shows A trusted and B pending", okPending, JSON.stringify(stateBefore ?? null));
        if (okPending) ledger.milestone("current-state-pending");

        if (pending) {
          const approved = await ledger.stage("S5", async () => approveThroughUi(pageA, recorder, { projectId, documentId: contractId }));
          ledger.check("revision B's approval names who decided", Boolean(approved?.decidedBy));
          await waitForDocument(pageA, projectId, contractId, ["analyzed"]);
          if (approved) state.reviewIds.contractB = approved.itemId;
        }
        const after = await readRevisions(pageA, contractId);
        const revBAfter = after.find((r) => r.blobHash === hashB);
        const revAAfter = after.find((r) => r.blobHash === hashA);
        const trustedB = revBAfter?.trustState === "trusted" && revBAfter.isCurrent === true;
        ledger.check("after the approval B is the trusted current revision", trustedB, `${revBAfter?.trustState}/${revBAfter?.isCurrent}`);
        ledger.check("A is no longer current", revAAfter?.isCurrent !== true);
        if (trustedB) ledger.milestone("revision-b-approved");
        const stateAfter = (await readCurrentState(pageA, recorder, projectId)).find((d) => d.filename === FILES.contractA);
        const okApproved = stateAfter?.trustedRevision?.revision_id === revB?.revisionId && stateAfter?.trustedRevision?.blob_hash === hashB && !stateAfter?.pendingRevision;
        ledger.check("Current State rests on B with nothing pending", okApproved, JSON.stringify(stateAfter ?? null));
        if (okApproved) ledger.milestone("current-state-approved");
      });

      // ═══ S7: canonical WBS and three links ══════════════════════════════════════════════════════════════
      await ledger.stage("S7", async () => {
        const projectId = state.projectA;
        state.wbs = await approveCanonicalWbs(pageA, projectId);
        ledger.evidence("wbs", { baselineNo: state.wbs.baselineNo, selfApproved: state.wbs.selfApproved, treeDigest: state.wbs.treeDigest });
        state.eventIds.wbsApproval = state.wbs.approvalEventId;
        ledger.milestone("wbs-approved");
        if (state.wbs.selfApproved) {
          ledger.partial("the WBS baseline was approved by the same human who submitted it: this tenant has ONE human, so separation of duties is relaxed by tenant setting (declared, recorded as self_approved)");
        }
        await openProjectTab(pageA, projectId, "wbs");
        await recorder.screenshot(pageA, "s7-wbs");

        const trustedRevision = async (documentId: string): Promise<{ revisionId: string; blobHash: string }> => {
          const revisions = await readRevisions(pageA, documentId);
          const chosen = revisions.find((r) => r.isCurrent) ?? revisions.at(-1);
          return { revisionId: chosen?.revisionId ?? "", blobHash: chosen?.blobHash ?? "" };
        };
        const budget = await trustedRevision(state.budget!.documentId);
        const schedule = await trustedRevision(state.schedule!.documentId);
        const specification = await trustedRevision(state.specification!.documentId);

        const attempts = [
          await approveStructuredLink(pageA, projectId, state.wbs, { family: "budget", documentId: state.budget!.documentId, ...budget, locator: LOCATORS.budget }),
          await approveStructuredLink(pageA, projectId, state.wbs, { family: "schedule", documentId: state.schedule!.documentId, ...schedule, locator: LOCATORS.schedule }),
          await approveTechnicalLink(pageA, projectId, state.wbs, { documentId: state.specification!.documentId, ...specification, section: TECHNICAL_SECTION }),
        ];
        for (const attempt of attempts) {
          const ok = attempt.status === 201;
          ledger.check(`${attempt.family}: the human approval of the canonical link is accepted`, ok, `HTTP ${attempt.status} ${attempt.detail}`);
          if (ok) {
            ledger.milestone(`link-${attempt.family}`);
            if (attempt.eventId) state.eventIds[`link.${attempt.family}`] = attempt.eventId;
          }
        }
        ledger.evidence("linkAttempts", attempts.map((a) => ({ family: a.family, status: a.status, detail: a.detail })));
        const untrusted = attempts.filter((a) => a.family !== "technical" && a.status !== 201 && /not (current )?trusted/i.test(a.detail));
        if (untrusted.length > 0) {
          state.dynamicGaps.push({
            stage: "S7",
            gap: `${untrusted.map((a) => a.family).join(" and ")} source revision(s) uploaded through the UI are not TRUSTED: only the N17 graph writes trusted artifacts and structured workbooks never pass through it, so no canonical link can rest on them`,
            minimalCorrection: "give a structured revision an explicit human trust approval (a proposed artifact + review, then commit_candidate) without touching N17; until then S7 fails honestly here",
          });
        }

        const links = await readLinks(pageA, projectId);
        const current = links.filter((l) => l.state === "CURRENT" && l.authority === "EXPLICIT_HUMAN_CANONICAL_LINK" && l.baselineId === state.wbs!.baselineId && l.nodeId === state.wbs!.childNodeId);
        ledger.check("three CURRENT human-approved links on the approved baseline and node", current.length === 3 && new Set(current.map((l) => l.family)).size === 3, `${current.length} current link(s)`);
        if (current.length === 3) ledger.milestone("links-current");
      });

      // ═══ S8: a real sign-out, a NEW login, identical persisted state, tenants denied both ways ═════════════
      await ledger.stage("S8", async () => {
        const projectId = state.projectA;
        const contractId = state.contract!.documentId;
        const take = async (page: Page): Promise<unknown> => {
          const revisionsByDocument: Record<string, unknown> = {};
          for (const [key, documentId] of Object.entries(state.documentIds)) revisionsByDocument[key] = await readRevisions(page, documentId);
          const queue = await callApi(page, `/api/v1/hitl/queue?project_id=${projectId}&limit=100`);
          return {
            project: str(((await callApi(page, `/api/v1/projects/${projectId}`)).data as Json).id),
            documents: (await listDocuments(page, projectId)).map((d) => ({ id: str(d.id), type: str(d.document_type), state: str(d.lifecycle_status) })).sort((a, b) => a.id.localeCompare(b.id)),
            revisions: revisionsByDocument,
            decisions: itemsOf(queue.data).map((d) => ({ item: str(d.item_id), row: str(d.row_id), status: str(d.current_status), by: str(d.approved_by), at: str(d.approved_at) })).sort((a, b) => a.row.localeCompare(b.row)),
            alerts: await readAlerts(page, projectId),
            links: await readLinks(page, projectId),
            health: await readHealth(page, projectId),
            dashboard: await readDashboard(page, projectId),
            wbsAuthority: (await callApi(page, `/api/v1/projects/${projectId}/wbs-governance/authority`)).data,
          };
        };

        // The WBS approval and the revision approvals enqueue project snapshots AFTER they commit; the state is
        // compared only once Health and the persisted evaluation have stopped moving.
        for (let attempt = 0; attempt < 6; attempt += 1) {
          const first = digestOf([await readHealth(pageA, projectId), await readDashboard(pageA, projectId)]);
          await pageA.waitForTimeout(10_000);
          if (first === digestOf([await readHealth(pageA, projectId), await readDashboard(pageA, projectId)])) break;
        }
        const before = await take(pageA);
        state.snapshotDigests.before = digestOf(before);
        const userBefore = await clerkIdentity(pageA);

        await pageA.getByRole("button", { name: "User menu" }).click();
        await pageA.getByRole("menuitem", { name: /sign out/i }).click();
        await expect(pageA).toHaveURL(/\/sign-in/, { timeout: 30_000 });
        await pageA.waitForFunction(() => window.Clerk?.loaded === true, undefined, { timeout: 30_000 });
        const stillSigned = await pageA.evaluate(() => Boolean(window.Clerk?.session));
        await pageA.goto(`/projects/${projectId}/documents`);
        await expect(pageA).toHaveURL(/\/sign-in/, { timeout: 30_000 });
        ledger.check("after the sign-out there is no Clerk session and a protected page leads to sign-in", !stillSigned);
        if (!stillSigned) ledger.milestone("signed-out");
        await contextA.close();

        // A brand-new context: no cookie, no local storage. The same documented Clerk bootstrap, a NEW login.
        const contextAgain = await browser.newContext({ baseURL: base, storageState: EMPTY_SESSION });
        const again = await contextAgain.newPage();
        try {
          await signInAsJourneyUser(again, base);
          const userAfter = await clerkIdentity(again);
          const same = userAfter.userId === userBefore.userId && userAfter.organizationId === userBefore.organizationId;
          ledger.check("the new login is the same Clerk user in the same Organization", same);
          if (same) ledger.milestone("relogin-same-user");
          await again.getByText(`Integral UAT ${tag}`, { exact: true }).first().click();
          await expect(again).toHaveURL(new RegExp(`/projects/${projectId}`), { timeout: 30_000 });
          const afterSnapshot = await take(again);
          state.snapshotDigests.after = digestOf(afterSnapshot);
          const identical = JSON.stringify(JSON.parse(JSON.stringify(afterSnapshot))) === JSON.stringify(JSON.parse(JSON.stringify(before)));
          ledger.check("documents, revisions, decisions, alerts, links, Health, Score and WBS authority are identical after the new login", identical, `${state.snapshotDigests.before?.slice(0, 12)} vs ${state.snapshotDigests.after?.slice(0, 12)}`);
          if (identical) ledger.milestone("state-identical");
          const links = (afterSnapshot as { links: unknown[] }).links;
          ledger.check("the three canonical links survive the new login", links.length === 3, `${links.length} link(s)`);
          ledger.check("revision B is still the trusted current revision", ((await readRevisions(again, contractId)).find((r) => r.blobHash === pinnedSha(FILES.contractB))?.trustState) === "trusted");
          ledger.check("the stored sources are all still there", Object.keys(state.documentIds).length === 5);

          const aToB = await denialsFor(again, state.projectB);
          ledger.check("after the relogin A is still denied B's project", aToB.every((s) => DENIAL.includes(s)), aToB.join(","));
          if (aToB.every((s) => DENIAL.includes(s))) ledger.milestone("a-to-b-denied-after");
          const bToA = await denialsFor(tenantB!.page, projectId);
          ledger.check("after the relogin B is still denied A's project", bToA.every((s) => DENIAL.includes(s)), bToA.join(","));
          if (bToA.every((s) => DENIAL.includes(s))) ledger.milestone("b-to-a-denied-after");
          const bOwn = await callApi(tenantB!.page, `/api/v1/projects/${state.projectB}`);
          ledger.check("B still reads its own project", bOwn.status === 200, `HTTP ${bOwn.status}`);
        } finally {
          await contextAgain.close();
        }
      });
    } finally {
      writeManifest();
      recorder.write();
      if (tenantB) await tenantB.close().catch(() => undefined);
      await contextA.close().catch(() => undefined);
    }

    const result = ledger.snapshot();
    test.info().annotations.push({
      type: "integral-s1-s8",
      description: JSON.stringify({
        mode: AI_MOCK ? "deterministic-rehearsal" : "real-ai-uat",
        projectId: state.projectA,
        firstFailure: result.firstFailure,
        stages: result.stages.map((stage) => `${stage.id}:${stage.status}`),
      }),
    });
    // The verdict of the run: every stage must be PASS or an honestly stated PARTIAL; any FAIL / NOT_RUN fails it.
    const unfinished = result.stages.filter((stage) => stage.status === "FAIL" || stage.status === "NOT_RUN");
    expect(unfinished.map((s) => `${s.id}:${s.status}${s.error ? `(${s.error})` : ""}`), `first failure: ${JSON.stringify(result.firstFailure)}`).toEqual([]);
  });
});

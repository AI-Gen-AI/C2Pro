/**
 * TS-E2E-REAL-AI-HITL-001 -- ACC-01 second functional pilot: REAL AI + browser + human review + PostgreSQL, ONE project.
 *
 * One vertical path, nothing seeded for the review, nothing mocked at the provider:
 *   1 Clerk Development login (the existing E2E identity)   2 project created in the browser   3 synthetic contract uploaded
 *   4 processed by the REAL provider (worker + graph)       5 findings shown in the review UI  6 one finding CONFIRMED and one
 *   DISMISSED with a typed reason (the current per-finding rules, no final Approve/Reject)   7 PostgreSQL read independently
 *   by verify_real_ai_hitl_pg.py   8 reload AND sign-out/sign-in: the decisions are still there.
 *
 * What it does NOT do: approve or reject the review, upload a second document, run S3-S8, or retry anything.
 *
 * Honest by construction: a capability the product does not offer is recorded as a GAP and the verdict is PARTIAL with the
 * concrete blocker; nothing is forged to hide it. A step that fails stops the run and names itself (failedStep).
 * The manifest holds ids, hashes, counts and titles of the findings of a SYNTHETIC public contract: never a token, cookie,
 * prompt or completion. Opt-in only (project "real-ai-hitl", enabled by the manual job).
 */
import { createHash } from "node:crypto";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";

import { expect, test, type Page } from "@playwright/test";

import { callApi, str, type Json } from "./support/integral/api";
import { clerkIdentity } from "./support/integral/identity";
import {
  grantProjectAuthority,
  openProjectTab,
  openReviewCard,
  readFindingsBack,
  decideFindingsThroughUi,
  waitForDocument,
  type FindingDecisionsOutcome,
} from "./support/integral/flow";
import { Pj01RunRecorder } from "./support/pj01/run-recorder";
import { createProjectThroughUi, signInAsJourneyUser } from "./support/pj01/session";
import { uploadDocumentThroughUi } from "./support/pj01/upload";

const FIXTURE_DIR = path.join(process.cwd(), "src", "tests", "e2e", "test-data", "pj01");
const CONTRACT = path.join(FIXTURE_DIR, "contract-a.pdf");
const MANIFEST_OUT = path.join(process.cwd(), "playwright-report", "real-ai-hitl-vertical.json");
const DISMISS_REASON = "Pilot reviewer: this finding is not supported by the quoted clause of the synthetic contract.";
const ANALYSIS_BUDGET_MS = 420_000;

const sha256 = (file: string): string => createHash("sha256").update(readFileSync(file)).digest("hex");

interface Gap {
  code: string;
  detail: string;
}

interface Facts {
  mode: "REAL_AI";
  aiMockEnv: string | undefined;
  contractSha256: string;
  failedStep: string | null;
  failure: string | null;
  steps: string[];
  gaps: Gap[];
  blocker: string | null;
  projectId: string;
  documentId: string;
  reviewItemId: string;
  reviewRowId: string;
  lifecycleAtGate: string;
  panel: { surfaced: boolean; findings: number; scopeStatesProvisional: boolean };
  decided: Array<{ ordinal: number; action: string }>;
  persistedActionsBeforeRelogin: Array<string | null>;
  persistedActionsAfterRelogin: Array<string | null>;
  persistedAfterReload: boolean;
  reviewStillPending: boolean;
  findingsShown: Array<{ ordinal: number; title: string; category: string; apiClauseRef: string | null; clauseRefVisibleInUi: boolean; sourceQuoteVisibleInUi: boolean }>;
  relogin: { sameUser: boolean; decisionsVisible: boolean };
}

const emptyFacts = (): Facts => ({
  mode: "REAL_AI",
  aiMockEnv: process.env.C2PRO_AI_MOCK,
  contractSha256: "",
  failedStep: null,
  failure: null,
  steps: [],
  gaps: [],
  blocker: null,
  projectId: "",
  documentId: "",
  reviewItemId: "",
  reviewRowId: "",
  lifecycleAtGate: "",
  panel: { surfaced: false, findings: 0, scopeStatesProvisional: false },
  decided: [],
  persistedActionsBeforeRelogin: [],
  persistedActionsAfterRelogin: [],
  persistedAfterReload: false,
  reviewStillPending: false,
  findingsShown: [],
  relogin: { sameUser: false, decisionsVisible: false },
});

/** What the review UI shows for each finding, next to what the server's own read model carries for it. */
async function readFindingsShown(page: Page, reviewRowId: string): Promise<Facts["findingsShown"]> {
  const answer = await callApi(page, `/api/v1/hitl/reviews/${reviewRowId}/findings`);
  const findings = Array.isArray((answer.data as Json | null)?.findings) ? (((answer.data as Json).findings as Json[]) ?? []) : [];
  const region = page.getByRole("region", { name: "Findings of this analysis" });
  const shown: Facts["findingsShown"] = [];
  for (const finding of [...findings].sort((a, b) => Number(a.ordinal) - Number(b.ordinal))) {
    const ordinal = Number(finding.ordinal);
    const risk = (finding.risk ?? {}) as Json;
    const rowText = ((await region.getByTestId(`finding-${ordinal}`).innerText().catch(() => "")) ?? "").toLowerCase();
    const clauseRef = str(risk.clause_ref) || null;
    const quote = str(risk.source_quote) || str(risk.source_text_snippet);
    shown.push({
      ordinal,
      title: str(risk.title) || str(risk.summary),
      category: str(risk.category),
      apiClauseRef: clauseRef,
      clauseRefVisibleInUi: Boolean(clauseRef) && rowText.includes(clauseRef!.toLowerCase()),
      sourceQuoteVisibleInUi: quote.length > 20 && rowText.includes(quote.slice(0, 40).toLowerCase()),
    });
  }
  return shown;
}

test.describe("TS-E2E-REAL-AI-HITL-001: real AI + browser + human review + PostgreSQL", () => {
  test("a user works with the REAL findings of an uploaded contract and the decisions persist", async ({ browser, baseURL }) => {
    test.setTimeout(1_500_000);
    const base = baseURL ?? "http://localhost:3100";
    const facts = emptyFacts();
    const recorder = new Pj01RunRecorder({ runId: `real-ai-hitl-${new Date().toISOString().replace(/[:.]/g, "-")}` });
    const step = async <T>(id: string, action: () => Promise<T>): Promise<T> => {
      facts.steps.push(id);
      try {
        return await action();
      } catch (error) {
        facts.failedStep = id;
        facts.failure = error instanceof Error ? error.message.split("\n")[0]! : String(error);
        throw error;
      }
    };
    const write = (): void => {
      mkdirSync(path.dirname(MANIFEST_OUT), { recursive: true });
      writeFileSync(MANIFEST_OUT, `${JSON.stringify(facts, null, 2)}\n`, "utf8");
    };

    try {
      // Fail closed BEFORE anything is created: this scenario is meaningless with a mocked provider.
      expect(process.env.C2PRO_AI_MOCK, "REAL_AI_REQUIRES_C2PRO_AI_MOCK=0").toBe("0");
      facts.contractSha256 = sha256(CONTRACT);

      const context = await browser.newContext({ baseURL: base, storageState: { cookies: [], origins: [] } });
      const page = await context.newPage();

      const observation = await step("1-login", () => signInAsJourneyUser(page, base));
      const identity = await clerkIdentity(page);
      expect(identity.userId && identity.organizationId && identity.tenantId, "an existing Clerk Development identity in an Organization with a tenant").toBeTruthy();

      facts.projectId = await step("2-create-project-in-browser", () => createProjectThroughUi(page, observation, `Real-AI vertical ${Date.now().toString(36)}`));
      // The current review rules (S5, enforce): explicit per-project grants for the single human, declared as such.
      await step("2b-project-grants", async () => {
        const grants = await grantProjectAuthority(facts.projectId);
        expect(grants.grants.join(",")).toBe("APPROVE_CANDIDATE,READ_REVIEW,REVIEW_FINDING");
      });

      const upload = await step("3-upload-contract", () => uploadDocumentThroughUi(page, recorder, { projectId: facts.projectId, filePath: CONTRACT, documentType: "contract" }));
      facts.documentId = upload.documentId;
      expect(upload.taskId, "the worker was enqueued").toBeTruthy();

      const gate = await step("4-real-ai-processing", () => waitForDocument(page, facts.projectId, facts.documentId, ["review_required", "analyzed"], ANALYSIS_BUDGET_MS));
      facts.lifecycleAtGate = str(gate.lifecycle_status);
      facts.reviewItemId = str(gate.review_item_id);
      if (facts.lifecycleAtGate !== "review_required") {
        facts.blocker = `NO_HUMAN_REVIEW_GATE: the document reached "${facts.lifecycleAtGate}" without a pending review, so there is nothing to decide`;
        facts.gaps.push({ code: "NO_REVIEW_GATE", detail: facts.blocker });
        return;
      }

      let outcome: FindingDecisionsOutcome | null = null;
      try {
        outcome = await step("5-6-findings-and-decisions", () =>
          decideFindingsThroughUi(page, recorder, {
            projectId: facts.projectId,
            documentId: facts.documentId,
            plan: { kind: "confirm-and-dismiss", confirm: 0, dismiss: 1, dismissReason: DISMISS_REASON },
          }),
        );
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        if (!/INTEGRAL_FINDINGS_PLAN_NEEDS_MORE_FINDINGS/.test(message)) throw error;
        // A real result with fewer than two findings is a finding about the product/provider, not a harness failure.
        facts.failedStep = null;
        facts.failure = null;
        facts.blocker = message.split("\n")[0]!;
        facts.gaps.push({ code: "FEWER_THAN_TWO_FINDINGS", detail: facts.blocker });
        return;
      }
      facts.panel = { surfaced: outcome.surfaced, findings: outcome.findings, scopeStatesProvisional: outcome.scopeStatesProvisional };
      if (!outcome.surfaced) {
        facts.blocker = "FINDINGS_PANEL_NOT_SURFACED: the review card offers no per-finding surface for this analysis (not candidate-bound, or the read failed)";
        facts.gaps.push({ code: "FINDINGS_PANEL_NOT_SURFACED", detail: facts.blocker });
        return;
      }
      facts.reviewRowId = outcome.reviewRowId;
      facts.decided = outcome.decided;
      facts.persistedAfterReload = outcome.persistedAfterReload;
      facts.reviewStillPending = outcome.reviewStillPending;
      facts.persistedActionsBeforeRelogin = outcome.persistedActions;

      // What the person can actually SEE of the contract behind each finding. The data may exist without being shown.
      await step("5b-contract-references-in-ui", async () => {
        const { card } = await openReviewCard(page, recorder, facts.projectId, facts.documentId);
        await expect(card).toBeVisible();
        facts.findingsShown = await readFindingsShown(page, facts.reviewRowId);
        const withRef = facts.findingsShown.filter((f) => f.apiClauseRef);
        const refsShown = withRef.filter((f) => f.clauseRefVisibleInUi).length;
        const quotesShown = facts.findingsShown.filter((f) => f.sourceQuoteVisibleInUi).length;
        if (withRef.length > 0 && refsShown < withRef.length) {
          facts.gaps.push({
            code: "CONTRACT_REFERENCE_NOT_SHOWN_IN_REVIEW_UI",
            detail: `${withRef.length} finding(s) carry a clause reference in the server read model; the review UI shows it for ${refsShown}. The panel renders title, category, severity and description only.`,
          });
        }
        if (quotesShown === 0) {
          facts.gaps.push({
            code: "SOURCE_QUOTE_NOT_SHOWN_IN_REVIEW_UI",
            detail: "no finding shows the contract text it rests on: the findings read model exposes title, description, category, severity, likelihood and clause_ref only (source_quote stays in the candidate artifact)",
          });
        }
      });

      // Relogin: the first session really ends; a NEW login of the same user, in an empty context, finds the decisions.
      await step("8-relogin", async () => {
        const userBefore = await page.evaluate(() => window.Clerk?.user?.id ?? null);
        await page.getByRole("button", { name: "User menu" }).click();
        await page.getByRole("menuitem", { name: /sign out/i }).click();
        await expect(page).toHaveURL(/\/sign-in/, { timeout: 30_000 });
        const fresh = await browser.newContext({ baseURL: base, storageState: { cookies: [], origins: [] } });
        try {
          const again = await fresh.newPage();
          await signInAsJourneyUser(again, base);
          facts.relogin.sameUser = (await again.evaluate(() => window.Clerk?.user?.id ?? null)) === userBefore;
          await openProjectTab(again, facts.projectId, "documents").catch(async () => {
            await again.getByText(/real-ai vertical/i).first().click();
          });
          const { card } = await openReviewCard(again, recorder, facts.projectId, facts.documentId);
          const region = card.getByRole("region", { name: "Findings of this analysis" });
          await expect(region).toBeVisible({ timeout: 60_000 });
          const back = await readFindingsBack(again, facts.reviewRowId);
          facts.persistedActionsAfterRelogin = back.actions;
          facts.relogin.decisionsVisible =
            (await region.getByTestId("finding-current-0").innerText()).includes("Confirmed") &&
            (await region.getByTestId("finding-current-1").innerText()).includes("Dismissed") &&
            JSON.stringify(back.actions) === JSON.stringify(facts.persistedActionsBeforeRelogin);
          expect(facts.relogin.decisionsVisible, "the decisions are shown unchanged after a brand-new login").toBe(true);
        } finally {
          await fresh.close();
        }
      });
    } finally {
      write();
    }
  });
});

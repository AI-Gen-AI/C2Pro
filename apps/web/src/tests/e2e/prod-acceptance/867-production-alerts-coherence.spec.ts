import { mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";

import { expect, test, type Page, type Response } from "@playwright/test";

import {
  contractAPdfPath,
  loadContractAManifest,
} from "../../pj01/fixture-contract";
import {
  contractBPdfPath,
  loadContractBManifest,
} from "../../pj01/revision-fixture";
import { clickProjectTab } from "../support/pj01/health";
import { observeProcessingWithoutReload } from "../support/pj01/processing";
import { uploadNewVersionThroughUi } from "../support/pj01/revision";
import { Pj01RunRecorder } from "../support/pj01/run-recorder";
import { createProjectThroughAuthenticatedUi } from "../support/pj01/session";
import { uploadDocumentThroughUi } from "../support/pj01/upload";
import {
  signInSyntheticProductionUser,
  signOutThroughUi,
} from "./support/prod-auth.synthetic";

const OUTPUT = path.join(process.cwd(), "playwright", ".prod-b1", "run.json");
const GENUINE_RULE = "DET-TIM-OVERDUE";
const FALSE_POSITIVE_RULE = "DET-QUA-INSPECT";

type PersistedAlert = {
  id: string;
  rule_code: string;
  status: string;
  message: string;
  source_clause_id?: string | null;
};

type AlertList = {
  items: PersistedAlert[];
  total: number;
};

function runId(): string {
  const value = process.env.PROD_ACCEPTANCE_RUN_ID?.trim();
  if (!value) throw new Error("B1_PROD_MISSING_ENV:PROD_ACCEPTANCE_RUN_ID");
  return value;
}

function requiredFixture(name: "B1_BUDGET_FIXTURE" | "B1_SCHEDULE_FIXTURE"): string {
  const value = process.env[name]?.trim();
  if (!value) throw new Error(`B1_PROD_MISSING_ENV:${name}`);
  return value;
}

function alertsResponse(projectId: string) {
  const exact = new RegExp(`/api/v1/alerts/projects/${projectId}/?$`);
  const compatibility = new RegExp(`/api/v1/projects/${projectId}/alerts/?$`);
  return (response: Response): boolean =>
    response.request().method() === "GET" &&
    response.ok() &&
    (exact.test(new URL(response.url()).pathname) ||
      compatibility.test(new URL(response.url()).pathname));
}

async function openAlertsAndRead(page: Page, recorder: Pj01RunRecorder, projectId: string): Promise<AlertList> {
  const observed = page.waitForResponse(alertsResponse(projectId), { timeout: 60_000 });
  await clickProjectTab(page, recorder, projectId, "alerts", "ALERTS_TAB_NOT_NAVIGABLE");
  await page.waitForURL(new RegExp(`/projects/${projectId}/alerts`), { timeout: 30_000 });
  return (await (await observed).json()) as AlertList;
}

function findRule(alerts: AlertList, rule: string): PersistedAlert {
  const matches = alerts.items.filter((item) => item.rule_code === rule);
  if (matches.length !== 1) {
    throw new Error(`B1_EXPECTED_EXACT_RULE:${rule}:count=${matches.length}`);
  }
  return matches[0];
}

async function reviewThroughUi(
  page: Page,
  alert: PersistedAlert,
  decision: "approve" | "reject",
  reason?: string,
): Promise<void> {
  const review = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      response.ok() &&
      new RegExp(`/api/v1/alerts/${alert.id}/review/?$`).test(
        new URL(response.url()).pathname,
      ),
    { timeout: 60_000 },
  );

  if (decision === "approve") {
    await page.getByRole("button", { name: `Approve ${alert.id}` }).click();
    await page.getByRole("checkbox", { name: /I confirm approval/i }).check();
    await page.getByRole("button", { name: "Confirm Approve" }).click();
  } else {
    await page.getByRole("button", { name: `Reject ${alert.id}` }).click();
    await page.getByLabel("Rejection reason").fill(
      reason ??
        "False positive: this clause grants access to inspection/test records; it is not the procedure that defines inspection frequency or method.",
    );
    await page.getByRole("button", { name: "Confirm Reject" }).click();
  }

  await review;
  await expect(page.getByRole("dialog")).toHaveCount(0, { timeout: 30_000 });
}

async function evaluateThroughUi(
  page: Page,
  recorder: Pj01RunRecorder,
  projectId: string,
): Promise<{ alerts: Array<{ rule_id?: string }> }> {
  await clickProjectTab(
    page,
    recorder,
    projectId,
    "coherence",
    "COHERENCE_TAB_NOT_NAVIGABLE",
  );
  await page.waitForURL(new RegExp(`/projects/${projectId}/coherence`), {
    timeout: 30_000,
  });

  const button = page.getByRole("button", { name: /^evaluate coherence$/i });
  await expect(button).toBeEnabled({ timeout: 300_000 });

  const evaluated = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      new URL(response.url()).pathname === "/api/v1/coherence/evaluate",
    { timeout: 300_000 },
  );
  await button.click();
  const response = await evaluated;
  if (!response.ok()) {
    throw new Error(`B1_COHERENCE_EVALUATION_REJECTED:HTTP_${response.status()}`);
  }
  return (await response.json()) as { alerts: Array<{ rule_id?: string }> };
}

test.describe("B1-12 production qualification — Alerts + Coherence", () => {
  test("@production-qualification governed review, exact rescore and stale-basis prevention", async ({
    page,
  }) => {
    test.setTimeout(20 * 60_000);

    const id = runId();
    const projectName = `ACCEPT-867-${id}`;
    const recorder = new Pj01RunRecorder({
      runId: id,
      rootDir: path.join(process.cwd(), "playwright", ".prod-b1", "artifacts"),
      mode: "strict",
    });
    const contractA = loadContractAManifest();
    const contractB = loadContractBManifest();

    await signInSyntheticProductionUser(page);
    const projectId = await createProjectThroughAuthenticatedUi(page, projectName);

    const contract = await uploadDocumentThroughUi(page, recorder, {
      projectId,
      filePath: contractAPdfPath(contractA),
      documentType: "contract",
    });
    if (!contract.taskId) throw new Error("B1_CONTRACT_NOT_ENQUEUED");

    const contractProcessing = await observeProcessingWithoutReload(page, recorder, {
      projectId,
      documentId: contract.documentId,
    });
    if (
      contractProcessing.evaluation.outcome !== "analyzed" ||
      contractProcessing.evaluation.violations.length
    ) {
      throw new Error(
        `B1_CONTRACT_NOT_ANALYZED:${contractProcessing.evaluation.outcome}`,
      );
    }

    const budget = await uploadDocumentThroughUi(page, recorder, {
      projectId,
      filePath: requiredFixture("B1_BUDGET_FIXTURE"),
      documentType: "budget",
    });
    const schedule = await uploadDocumentThroughUi(page, recorder, {
      projectId,
      filePath: requiredFixture("B1_SCHEDULE_FIXTURE"),
      documentType: "schedule",
    });
    expect(budget.documentId).not.toBe(contract.documentId);
    expect(schedule.documentId).not.toBe(contract.documentId);

    const firstEvaluation = await evaluateThroughUi(page, recorder, projectId);
    const firstRules = firstEvaluation.alerts
      .map((item) => item.rule_id)
      .filter((value): value is string => Boolean(value));
    expect(firstRules).toContain(GENUINE_RULE);
    expect(firstRules).toContain(FALSE_POSITIVE_RULE);

    const firstAlerts = await openAlertsAndRead(page, recorder, projectId);
    const genuine = findRule(firstAlerts, GENUINE_RULE);
    const falsePositive = findRule(firstAlerts, FALSE_POSITIVE_RULE);
    expect(genuine.status).toBe("open");
    expect(falsePositive.status).toBe("open");

    await reviewThroughUi(page, genuine, "approve");
    await reviewThroughUi(page, falsePositive, "reject");

    // Fresh auth/browser read: durable status must survive, not just React/query state.
    await signOutThroughUi(page);
    await signInSyntheticProductionUser(page);
    const projectLink = page.getByRole("link", { name: projectName }).first();
    await expect(projectLink).toBeVisible({ timeout: 30_000 });
    await projectLink.click();
    await page.waitForURL(new RegExp(`/projects/${projectId}/`), {
      timeout: 30_000,
    });

    const afterReview = await openAlertsAndRead(page, recorder, projectId);
    expect(findRule(afterReview, GENUINE_RULE).status).toBe("acknowledged");
    expect(findRule(afterReview, FALSE_POSITIVE_RULE).status).toBe("dismissed");

    // New authoritative observation: same logical contract, new revision.
    const revision = await uploadNewVersionThroughUi(page, recorder, {
      projectId,
      documentId: contract.documentId,
      filePath: contractBPdfPath(contractB),
    });
    expect(revision.documentId).toBe(contract.documentId);

    const revisionProcessing = await observeProcessingWithoutReload(page, recorder, {
      projectId,
      documentId: contract.documentId,
    });
    if (
      revisionProcessing.evaluation.outcome !== "analyzed" ||
      revisionProcessing.evaluation.violations.length
    ) {
      throw new Error(
        `B1_REVISION_B_NOT_ANALYZED:${revisionProcessing.evaluation.outcome}`,
      );
    }

    const secondEvaluation = await evaluateThroughUi(page, recorder, projectId);
    const secondRules = secondEvaluation.alerts
      .map((item) => item.rule_id)
      .filter((value): value is string => Boolean(value));
    expect(secondRules).toContain(FALSE_POSITIVE_RULE);

    const afterNewObservation = await openAlertsAndRead(page, recorder, projectId);
    const currentFalsePositive = findRule(afterNewObservation, FALSE_POSITIVE_RULE);
    expect(currentFalsePositive.status).toBe("open");

    const recorderPath = recorder.write();
    mkdirSync(path.dirname(OUTPUT), { recursive: true });
    writeFileSync(
      OUTPUT,
      JSON.stringify(
        {
          schema: "c2pro-b1-12-production-run/v1",
          run_id: id,
          project_name: projectName,
          project_id: projectId,
          contract_document_id: contract.documentId,
          budget_document_id: budget.documentId,
          schedule_document_id: schedule.documentId,
          genuine_rule: GENUINE_RULE,
          genuine_alert_id: genuine.id,
          false_positive_rule: FALSE_POSITIVE_RULE,
          false_positive_alert_id: falsePositive.id,
          post_revision_false_positive_alert_id: currentFalsePositive.id,
          false_positive_rationale:
            "The Quality clause grants access to inspection/test records; it does not purport to define the inspection procedure, frequency or method.",
          relogin_verified: true,
          second_authoritative_observation_evaluated: true,
          recorder_path: path.relative(process.cwd(), recorderPath),
        },
        null,
        2,
      ),
      "utf8",
    );
  });
});

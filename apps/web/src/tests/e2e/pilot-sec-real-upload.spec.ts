/**
 * OPERACIÓN REAL en el PILOTO Railway.
 * Public SEC Exhibit 99.1 -> PDF -> real Clerk identity -> real project ->
 * real upload/worker/provider -> candidate-bound findings GET 200.
 * NO source fabrication, NO mock, NO synthetic database, NO human decision.
 * Run only by manual, owner-authorized GitHub workflow; one unique project.
 */
import { createHash } from "node:crypto";
import { mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";
import { expect, test, type APIRequestContext, type Page, type Browser } from "@playwright/test";
import { clerk, setupClerkTestingToken } from "@clerk/testing/playwright";

const API = "https://projectgraph-api-pilot.up.railway.app";
const SEC = "https://www.sec.gov/Archives/edgar/data/1519472/000164033426000032/solarmax_ex991.htm";
const SOURCE_SHA = "b90a590e134e92059915e9b3d574a06f38fdef9aef756db456b256ad4c3bea60";
const E2E_USER = process.env.E2E_CLERK_USER_EMAIL?.trim() || "testuser@c2pro.com";
const OUT = path.resolve("playwright-report/pilot-solarmax-sec-real-receipt.json");
const sha256 = (x: Buffer) => createHash("sha256").update(x).digest("hex");
const value = (x: unknown) => typeof x === "string" ? x : "";
type ObjectRow = Record<string, unknown>;
const obj = (x: unknown): ObjectRow => x && typeof x === "object" && !Array.isArray(x) ? x as ObjectRow : {};
const arr = (x: unknown): ObjectRow[] => Array.isArray(x) ? x.map(obj) : [];

async function tokenOf(page: Page): Promise<string> {
  const token = await page.evaluate(async () => (await window.Clerk?.session?.getToken()) || "");
  expect(token.length, "Clerk token required; never log it").toBeGreaterThan(50);
  return token;
}
async function getJson(request: APIRequestContext, page: Page, url: string) {
  const response = await request.get(API + url, {
    failOnStatusCode: false, headers: { Authorization: "Bearer " + await tokenOf(page) },
    timeout: 30_000,
  });
  return { status: response.status(), data: response.status() === 200 ? await response.json() : null };
}

test("SEC SolarMax real contract -> Railway pilot -> genuine finding candidate, no final approval", async ({ browser, request }) => {
  test.setTimeout(1_200_000);
  expect(process.env.C2PRO_REAL_PILOT_SEC_UPLOAD).toBe("OWNER-AUTHORIZED-REAL-PILOT");
  expect(process.env.PILOT_API_URL).toBe(API);
  expect(process.env.GITHUB_RUN_ID).toMatch(/^\d+$/);
  const receipt: ObjectRow = {
    evidence_class: "LIVE_RAILWAY_PILOT_REAL_CONTRACT",
    code_sha: process.env.GITHUB_SHA || "",
    github_run_id: process.env.GITHUB_RUN_ID,
    source_sec_url: SEC,
    source_html_sha256_expected: SOURCE_SHA,
    human_final_approval: "NOT_ATTEMPTED",
    simulated_candidate: false,
    database_seed: false,
    provider_mock: false,
    project_created: false,
    upload_accepted: false,
    findings_http_200: false,
  };
  const record = () => { mkdirSync(path.dirname(OUT), {recursive: true}); writeFileSync(OUT, JSON.stringify(receipt, null, 2) + "\n"); };
  let auth: Awaited<ReturnType<Browser["newContext"]>> | undefined;
  try {
    // Immutable public primary-source check. Reject unexpected SEC/third-party content BEFORE product writes.
    const fetched = await request.get(SEC, {
      failOnStatusCode: false, timeout: 45_000,
      headers: { "User-Agent": "AI-GEN C2Pro technical validation info@ai-gen.ai" },
    });
    expect(fetched.status(), "SEC original exhibit must be accessible").toBe(200);
    const officialBytes = await fetched.body();
    expect(sha256(officialBytes), "primary SEC source hash").toBe(SOURCE_SHA);
    receipt.source_bytes = officialBytes.length;
    const htm = officialBytes.toString("utf8");
    expect(htm).toContain("NAGUABO BESS LLC");
    expect(htm).toContain("122,350,571");
    for (const clause of ["2.5.5", "4.3.1", "9.6", "14.14.1"]) expect(htm).toContain(clause);

    // Chromium prints the *real SEC exhibit*, not an AI-invented fixture.
    // The resulting page layout differs from the 94-page Library PDF; preserve its own SHA.
    const renderContext = await browser.newContext({ javaScriptEnabled: false });
    const renderPage = await renderContext.newPage();
    await renderPage.route("**/*", route => route.abort());
    const htmlStart = htm.toLowerCase().indexOf("<html");
    const htmlEnd = htm.toLowerCase().lastIndexOf("</text>");
    expect(htmlStart).toBeGreaterThanOrEqual(0);
    await renderPage.setContent(htm.slice(htmlStart, htmlEnd), { waitUntil: "domcontentloaded" });
    const pdf = await renderPage.pdf({
      format: "A4", printBackground: true, preferCSSPageSize: false,
      margin: { top: "12mm", bottom: "12mm", left: "11mm", right: "11mm" },
      displayHeaderFooter: false,
    });
    await renderContext.close();
    expect(pdf.subarray(0,4).toString("ascii")).toBe("%PDF");
    expect(pdf.length, "genuine SEC contract PDF size").toBeGreaterThan(100_000);
    receipt.rendered_pdf_sha256 = sha256(pdf);
    receipt.rendered_pdf_bytes = pdf.length;
    record();

    auth = await browser.newContext({baseURL: "http://localhost:3100", storageState: { cookies: [], origins: [] }});
    const page = await auth.newPage();
    await setupClerkTestingToken({ page });
    await page.goto("/");
    await clerk.loaded({ page });
    await clerk.signIn({ page, emailAddress: E2E_USER });
    await page.waitForFunction(() => Boolean(window.Clerk?.session && window.Clerk?.organization), undefined, {timeout: 60_000});
    const preflight = await getJson(request, page, "/api/v1/projects");
    expect(preflight.status, "PILOT Clerk bearer must read projects").toBe(200);

    const code = "REAL-SEC-" + process.env.GITHUB_RUN_ID;
    const create = await request.post(API + "/api/v1/projects", {
      failOnStatusCode: false, timeout: 45_000,
      headers: { Authorization: "Bearer " + await tokenOf(page) },
      data: {
        name: "UAT REAL | Naguabo BESS EPC SEC | " + process.env.GITHUB_RUN_ID,
        code,
        project_type: "construction",
        description: "Original public SEC EX-99.1, filed Jan 2026; complete contractual analysis. No fabricated exhibits. Source SHA " + SOURCE_SHA,
        client_name: "Naguabo BESS LLC",
        estimated_budget: 122350571,
        currency: "USD",
      },
    });
    receipt.project_create_status = create.status();
    expect(create.status(), "real project POST").toBe(201);
    const created = obj(await create.json());
    const projectId = value(created.id);
    expect(projectId).toMatch(/^[a-f0-9-]{36}$/i);
    receipt.project_id = projectId;
    receipt.project_created = true;
    record();

    const fileName = "solarmax_naguabo_SEC_EX99-1_real.pdf";
    const uploaded = await request.post(API + "/api/v1/projects/" + projectId + "/documents", {
      failOnStatusCode: false, timeout: 120_000,
      headers: { Authorization: "Bearer " + await tokenOf(page) },
      multipart: {
        document_type: "contract",
        file: { name: fileName, mimeType: "application/pdf", buffer: pdf },
      },
    });
    receipt.upload_http_status = uploaded.status();
    expect(uploaded.status(), "real PDF upload with Celery enqueue").toBe(202);
    const uploadedBody = obj(await uploaded.json());
    const documentId = value(uploadedBody.id || uploadedBody.document_id);
    expect(documentId).toMatch(/^[a-f0-9-]{36}$/i);
    receipt.document_id = documentId;
    receipt.task_enqueued = Boolean(uploadedBody.task_id);
    receipt.upload_accepted = true;
    record();
    expect(receipt.task_enqueued, "real Worker task enqueued").toBe(true);

    // Read-after-write against deployed Railway, not isolated test DB.
    const end = Date.now() + 780_000;
    let seen = "";
    let findingsStatus = 0;
    while (Date.now() < end) {
      const docs = await getJson(request, page, "/api/v1/projects/" + projectId + "/documents?limit=100");
      expect(docs.status).toBe(200);
      const items = arr(obj(docs.data).items || obj(docs.data).documents || docs.data);
      const document = items.find(x => value(x.id) === documentId);
      expect(document, "document visible from real tenant after accepted upload").toBeTruthy();
      const state = value(document?.lifecycle_status || document?.upload_status);
      if (state !== seen) { seen = state; receipt.last_document_state = state; record(); }
      const reviewItemId = value(document?.review_item_id);
      if (reviewItemId) {
        const queue = await getJson(request, page, "/api/v1/hitl/queue?project_id=" + projectId + "&limit=200");
        expect(queue.status).toBe(200);
        const candidate = arr(obj(queue.data).items).find(x => value(x.item_id) === reviewItemId);
        const rowId = value(candidate?.row_id);
        receipt.review_status = value(candidate?.current_status);
        if (rowId) {
          receipt.review_row_identified = true;
          const findings = await getJson(request, page, "/api/v1/hitl/reviews/" + rowId + "/findings");
          findingsStatus = findings.status;
          receipt.findings_http_status = findingsStatus;
          if (findingsStatus === 200) {
            const list = arr(obj(findings.data).findings);
            receipt.finding_count = list.length;
            receipt.findings_http_200 = true;
            receipt.findings_with_clause_ref = list.filter(x => Boolean(value(obj(x.risk).clause_ref))).length;
            receipt.findings_with_verified_quote = list.filter(x => value(obj(x.risk).source_quote_status) === "VERIFIED").length;
            receipt.review_row_id = rowId;
            record();
            expect(list.length, "real candidate must contain readable findings").toBeGreaterThan(0);
            break;
          }
        }
      }
      if (["error", "failed_retryable", "needs_changes"].includes(state)) {
        throw new Error("DOCUMENT_FAILED_REAL_PILOT: " + state + "; no fake completion");
      }
      await page.waitForTimeout(8_000);
    }
    expect(findingsStatus, "real candidate-bound read GET /findings must be 200").toBe(200);
    receipt.result = "REAL_PILOT_INGESTION_FINDINGS_READY_FOR_HUMAN";
    record();
  } catch (e) {
    receipt.result = "BLOCKED_NOT_ACCEPTED";
    receipt.failure_type = e instanceof Error ? e.name : "UnknownError";
    receipt.failure_step = (e instanceof Error ? e.message.split("\n")[0] : String(e)).slice(0,140);
    record();
    throw e;
  } finally {
    if (auth) await auth.close();
    record();
  }
});

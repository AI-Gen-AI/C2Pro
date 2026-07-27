/**
 * Regression guard for TASK-QA-340.
 *
 * `PDFViewer.tsx` renders documents via `react-pdf`, which imports its own
 * pinned `pdfjs-dist` as the PDF.js *API*. The same component configures
 * `pdfjs.GlobalWorkerOptions.workerSrc` from the app's `pdfjs-dist` package
 * (the *worker*) through `new URL("pdfjs-dist/build/pdf.worker.min.mjs", …)`.
 *
 * PDF.js hard-requires that the API version and the worker version are
 * identical — any skew makes it throw ("The API version … does not match the
 * Worker version …") the moment a document is opened, which is exactly the
 * runtime crash QA-340 observed when clicking a document link (the FRT-192
 * wedge worked around it by asserting the href instead of navigating).
 *
 * These assertions fail fast in CI if the two ever drift again.
 */
import { createRequire } from "module";
import { readFileSync } from "fs";
import path from "path";
import { fileURLToPath } from "url";
import { describe, it, expect } from "vitest";

const require = createRequire(import.meta.url);

describe("PDFViewer pdfjs worker/API version alignment (QA-340)", () => {
  // The version react-pdf actually runs as the PDF.js API.
  const reactPdfPkg = require("react-pdf/package.json");
  const apiVersion: string = reactPdfPkg.dependencies["pdfjs-dist"];

  // The version the app ships as the worker (resolved by `new URL(...)`).
  const appPkgPath = path.resolve(
    path.dirname(fileURLToPath(import.meta.url)),
    "../../../package.json",
  );
  const appPkg = JSON.parse(readFileSync(appPkgPath, "utf8"));
  const declaredWorkerVersion: string | undefined =
    appPkg.dependencies?.["pdfjs-dist"] ??
    appPkg.devDependencies?.["pdfjs-dist"];

  it("pins pdfjs-dist to the exact version react-pdf uses as its API", () => {
    // Must be an exact pin (not a range) so the worker can never float ahead
    // of react-pdf's API version.
    expect(declaredWorkerVersion).toBe(apiVersion);
  });

  it("resolves a single installed pdfjs-dist matching react-pdf's API", () => {
    const installed = require("pdfjs-dist/package.json").version;
    expect(installed).toBe(apiVersion);
  });
});

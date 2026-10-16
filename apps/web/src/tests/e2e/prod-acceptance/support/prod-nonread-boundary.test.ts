import { describe, expect, it } from "vitest";
import { classifyNonReadRequest } from "./prod-nonread-boundary";

describe("PQ939 production first-party non-read fail-closed boundary", () => {
  it.each([
    ["https://c2pro.io/sign-in", "signin1", true],
    ["https://www.c2pro.io/sign-in", "signin2", true],
    ["https://c2pro.io/projects/p/evidence", "logout1", true],
    ["https://c2pro.io/projects/p/evidence", "logout2", true],
    ["https://c2pro.io/api/documents/d", "read1", false],
    ["https://c2pro-production.up.railway.app/api/v1/documents/d", "read2", false],
    ["https://c2pro.io/other-app-route", "signin1", true],
  ])("never exempts opaque app POST %s in %s (next action %s)", (url) => {
    expect(classifyNonReadRequest("POST", url)).toBe(
      "unverified_first_party_nonread",
    );
  });

  it.each(["PUT", "PATCH", "DELETE", "CONNECT", "TRACE"])(
    "rejects any first-party %s, regardless of path",
    (method) => {
      expect(classifyNonReadRequest(method, "https://c2pro.io/sign-in")).toBe(
        "unverified_first_party_nonread",
      );
    },
  );

  it("fails closed on an unparseable non-read target", () => {
    expect(classifyNonReadRequest("POST", "not a url")).toBe(
      "unparseable_nonread",
    );
  });

  it("does not waive external-provider or unknown-origin POSTs without attributable safety", () => {
    expect(classifyNonReadRequest("POST", "https://accounts.clerk.com/session")).toBe(
      "unverified_external_nonread",
    );
    expect(classifyNonReadRequest("POST", "https://c2pro.io.evil.invalid/sign-in")).toBe(
      "unverified_external_nonread",
    );
  });

  it.each(["GET", "HEAD", "OPTIONS"])("does not treat %s as a product write", (method) => {
    expect(classifyNonReadRequest(method, "https://c2pro.io/projects/p/evidence")).toBe(
      "read",
    );
  });
});

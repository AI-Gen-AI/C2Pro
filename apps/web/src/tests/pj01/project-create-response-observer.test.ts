import { describe, expect, it } from "vitest";

import { isBrowserVisibleProjectCreateResponse } from "../e2e/support/pj01/session";

function response(url: string, method: string, status = 201) {
  return {
    url: () => url,
    request: () => ({ method: () => method }),
    ok: () => status >= 200 && status < 300,
  };
}

describe("PJ-01 project creation response observer", () => {
  it("recognizes the successful browser-visible project create response", () => {
    expect(isBrowserVisibleProjectCreateResponse(response("http://localhost:3100/api/projects", "POST"))).toBe(true);
  });

  it("rejects an unrelated browser route", () => {
    expect(isBrowserVisibleProjectCreateResponse(response("http://localhost:3100/api/projects/123", "POST"))).toBe(false);
  });

  it("does not depend on the backend-internal API route", () => {
    expect(isBrowserVisibleProjectCreateResponse(response("http://localhost:3100/api/v1/projects", "POST"))).toBe(false);
  });
});

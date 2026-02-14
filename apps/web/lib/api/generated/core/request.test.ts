import { describe, expect, it } from "vitest";
import { formatRequestError } from "@/lib/api/generated/core/request";

describe("formatRequestError", () => {
  it("formats aggregate errors with inner causes", () => {
    const error = new AggregateError(
      [new Error("connect ECONNREFUSED ::1:8000"), new Error("connect ECONNREFUSED 127.0.0.1:8000")],
      "network failed",
    );

    const message = formatRequestError(error);

    expect(message).toContain("API request failed");
    expect(message).toContain("ECONNREFUSED");
  });

  it("formats axios response errors with status details", () => {
    const axiosLikeError = {
      isAxiosError: true,
      response: {
        status: 503,
        statusText: "Service Unavailable",
      },
    };

    const message = formatRequestError(axiosLikeError);
    expect(message).toBe("API request failed (503 Service Unavailable)");
  });

  it("formats generic errors", () => {
    const message = formatRequestError(new Error("boom"));
    expect(message).toBe("API request failed: boom");
  });
});

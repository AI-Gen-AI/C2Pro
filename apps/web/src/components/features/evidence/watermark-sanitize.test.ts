/**
 * Test Suite ID: S3-03
 * Roadmap Reference: S3-03 Dynamic watermark (pseudonymized ID)
 */
import { describe, expect, it } from "vitest";
import { sanitizeWatermarkPayload } from "@/src/components/features/evidence/watermark-sanitize";

describe("S3-03 RED - watermark sanitizer", () => {
  it("[S3-03-RED-UNIT-03] removes raw PII keys and returns only safe display fields", () => {
    const output = sanitizeWatermarkPayload({
      pseudonymId: "USR-2FD9A1",
      email: "jane.doe@acme.com",
      fullName: "Jane Doe",
      phone: "+1 (555) 010-9911",
      rawUserId: "user_123e4567-e89b-12d3-a456-426614174000",
      tenantLegalName: "Acme Construction LLC",
      environment: "staging",
    });

    expect(output).toEqual({
      pseudonymId: "USR-2FD9A1",
      environment: "staging",
    });
  });

  it("[S3-03-RED-UNIT-04] strips PII-like fragments from string values", () => {
    const output = sanitizeWatermarkPayload({
      pseudonymId: "USR-2FD9A1",
      note: "owner jane.doe@acme.com +1 555-222-8899",
      environment: "prod",
    });

    expect(output.note).not.toMatch(/@/);
    expect(output.note).not.toMatch(/\+1\s?555|555-222-8899/);
  });
});

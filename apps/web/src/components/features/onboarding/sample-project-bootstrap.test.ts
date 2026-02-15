/**
 * Test Suite ID: S3-11
 * Roadmap Reference: S3-11 Onboarding sample project frontend
 */
import { describe, expect, it } from "vitest";
import { transitionBootstrapState } from "@/src/components/features/onboarding/sample-project-bootstrap";

describe("S3-11 RED - sample project bootstrap state machine", () => {
  it("[S3-11-RED-UNIT-02] transitions deterministically across bootstrap states", () => {
    expect(transitionBootstrapState("idle", "start")).toBe("provisioning");
    expect(transitionBootstrapState("provisioning", "success")).toBe("ready");
    expect(transitionBootstrapState("provisioning", "error")).toBe("failed");
    expect(transitionBootstrapState("failed", "retry")).toBe("provisioning");
  });
});

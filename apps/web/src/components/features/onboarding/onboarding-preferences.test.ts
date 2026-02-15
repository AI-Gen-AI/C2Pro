/**
 * Test Suite ID: S3-11
 * Roadmap Reference: S3-11 Onboarding sample project frontend
 */
import { describe, expect, it } from "vitest";
import {
  shouldShowOnboarding,
  storeOnboardingPreference,
} from "@/src/components/features/onboarding/onboarding-preferences";

describe("S3-11 RED - onboarding preferences", () => {
  it("[S3-11-RED-UNIT-04] persists skip/resume preference and avoids unexpected reopen", () => {
    storeOnboardingPreference({ dismissed: true, resumeLater: true });

    expect(shouldShowOnboarding()).toBe(false);
  });
});

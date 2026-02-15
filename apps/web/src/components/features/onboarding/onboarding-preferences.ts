/**
 * Test Suite ID: S3-11
 * Roadmap Reference: S3-11 Onboarding sample project frontend
 */

interface OnboardingPreference {
  dismissed: boolean;
  resumeLater: boolean;
}

const STORAGE_KEY = "s3-11-onboarding-preference";

export function storeOnboardingPreference(value: OnboardingPreference): void {
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify(value));
}

export function shouldShowOnboarding(): boolean {
  const raw = sessionStorage.getItem(STORAGE_KEY);
  if (!raw) return true;

  try {
    const parsed = JSON.parse(raw) as OnboardingPreference;
    if (parsed.dismissed || parsed.resumeLater) {
      return false;
    }
  } catch {
    return true;
  }

  return true;
}


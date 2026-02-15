/**
 * Test Suite ID: S3-09
 * Roadmap Reference: S3-09 Cookie consent banner (GDPR)
 */

export interface CookieConsentCategories {
  necessary: boolean;
  analytics: boolean;
  marketing: boolean;
}

export function isScriptAllowedByConsent(
  category: keyof CookieConsentCategories,
  consent: CookieConsentCategories,
): boolean {
  return Boolean(consent[category]);
}


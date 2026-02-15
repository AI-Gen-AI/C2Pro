/**
 * Test Suite ID: S3-09
 * Roadmap Reference: S3-09 Cookie consent banner (GDPR)
 */
"use client";

import { useMemo, useState } from "react";
import { type CookieConsentCategories } from "@/src/components/features/compliance/consent-gating";

interface ConsentPayload {
  version: string;
  acceptedAt: string;
  categories: CookieConsentCategories;
}

interface CookieConsentBannerProps {
  policyVersion: string;
}

const DEFAULT_CATEGORIES: CookieConsentCategories = {
  necessary: true,
  analytics: false,
  marketing: false,
};

export function CookieConsentBanner({ policyVersion }: CookieConsentBannerProps) {
  const [isPreferencesOpen, setPreferencesOpen] = useState(false);
  const [draftCategories, setDraftCategories] =
    useState<CookieConsentCategories>(DEFAULT_CATEGORIES);
  const [payload, setPayload] = useState<ConsentPayload | null>(null);

  const serializedPayload = useMemo(() => {
    if (!payload) return "";
    return JSON.stringify({
      version: payload.version,
      acceptedAt: payload.acceptedAt,
      ...payload.categories,
    });
  }, [payload]);

  const savePayload = (categories: CookieConsentCategories) => {
    setPayload({
      version: policyVersion,
      acceptedAt: "2026-02-15T00:00:00.000Z",
      categories,
    });
    setDraftCategories(categories);
  };

  return (
    <section role="region" aria-label="Cookie consent">
      <h2>Cookie consent</h2>
      <ul>
        <li>Necessary</li>
        <li>Analytics</li>
        <li>Marketing</li>
      </ul>

      <button
        type="button"
        onClick={() => {
          savePayload({
            necessary: true,
            analytics: true,
            marketing: true,
          });
        }}
      >
        Accept all
      </button>
      <button
        type="button"
        onClick={() => {
          savePayload({
            necessary: true,
            analytics: false,
            marketing: false,
          });
        }}
      >
        Reject optional
      </button>
      <button type="button" onClick={() => setPreferencesOpen(true)}>
        Manage preferences
      </button>

      {isPreferencesOpen ? (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Cookie preferences"
          onKeyDown={(event) => {
            if (event.key === "Escape") {
              setPreferencesOpen(false);
            }
          }}
        >
          <label>
            <input checked disabled readOnly type="checkbox" />
            Necessary cookies
          </label>
          <label>
            <input
              type="checkbox"
              checked={draftCategories.analytics}
              onChange={(event) =>
                setDraftCategories((prev) => ({ ...prev, analytics: event.target.checked }))
              }
            />
            Analytics cookies
          </label>
          <label>
            <input
              type="checkbox"
              checked={draftCategories.marketing}
              onChange={(event) =>
                setDraftCategories((prev) => ({ ...prev, marketing: event.target.checked }))
              }
            />
            Marketing cookies
          </label>

          <button
            type="button"
            onClick={() => {
              savePayload({
                necessary: true,
                analytics: draftCategories.analytics,
                marketing: draftCategories.marketing,
              });
              setPreferencesOpen(false);
            }}
          >
            Save preferences
          </button>
        </div>
      ) : null}

      <output data-testid="cookie-consent-payload">{serializedPayload}</output>
    </section>
  );
}


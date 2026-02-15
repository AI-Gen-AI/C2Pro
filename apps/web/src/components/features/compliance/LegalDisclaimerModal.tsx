/**
 * Test Suite ID: S3-08
 * Roadmap Reference: S3-08 Legal disclaimer modal (Gate 8)
 */
"use client";

import { useMemo, useState } from "react";

interface LegalDisclaimerModalProps {
  open: boolean;
  gateId: string;
  version: string;
  effectiveDate: string;
  acceptedVersion?: string;
  onConfirm: () => void;
  onCancel: () => void;
}

export function LegalDisclaimerModal({
  open,
  gateId,
  version,
  effectiveDate,
  acceptedVersion,
  onConfirm,
  onCancel,
}: LegalDisclaimerModalProps) {
  const [accepted, setAccepted] = useState(false);

  const requiresReprompt = useMemo(() => {
    if (!acceptedVersion) return true;
    return acceptedVersion !== version;
  }, [acceptedVersion, version]);

  if (!open) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Legal disclaimer"
      onKeyDown={(event) => {
        if (event.key === "Escape") {
          onCancel();
        }
      }}
    >
      <h2>Legal Disclaimer</h2>
      <p data-testid="legal-gate-id">{gateId}</p>
      <p data-testid="legal-version">{version}</p>
      <p data-testid="legal-effective-date">{effectiveDate}</p>
      <p data-testid="legal-gate-state">{accepted ? "unblocked" : "blocked"}</p>
      <p data-testid="legal-reprompt-required">{String(requiresReprompt)}</p>

      <label>
        <input
          type="checkbox"
          checked={accepted}
          onChange={(event) => setAccepted(event.target.checked)}
        />
        I have read and accept this legal disclaimer
      </label>

      <button
        type="button"
        disabled={!accepted}
        onClick={() => {
          if (!accepted) return;
          onConfirm();
        }}
      >
        Confirm acceptance
      </button>
      <button type="button" onClick={onCancel}>
        Cancel
      </button>
    </div>
  );
}


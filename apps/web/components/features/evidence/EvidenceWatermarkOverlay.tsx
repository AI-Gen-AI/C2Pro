/**
 * Test Suite ID: S3-03
 * Roadmap Reference: S3-03 Dynamic watermark (pseudonymized ID)
 */
"use client";

import { sanitizeWatermarkPayload, type WatermarkPayloadInput } from "@/components/features/evidence/watermark-sanitize";

interface EvidenceWatermarkOverlayProps {
  watermark: WatermarkPayloadInput;
}

export function EvidenceWatermarkOverlay({ watermark }: EvidenceWatermarkOverlayProps) {
  const safe = sanitizeWatermarkPayload(watermark);
  const display = [safe.pseudonymId, safe.environment, safe.timestampIso, safe.note]
    .filter(Boolean)
    .join(" • ");

  const tiles = Array.from({ length: 6 }, (_, index) => (
    <span key={`wm-${index}`} data-testid="evidence-watermark-tile" aria-hidden="true">
      {display}
    </span>
  ));

  return (
    <div
      data-testid="evidence-watermark-overlay"
      data-watermark-style="tilted-grid"
      className="pointer-events-none select-none opacity-25"
    >
      {tiles}
    </div>
  );
}

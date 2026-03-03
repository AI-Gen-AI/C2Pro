/**
 * Test Suite ID: S3-03
 * Roadmap Reference: S3-03 Dynamic watermark (pseudonymized ID)
 */
import { describe, expect, it } from "vitest";
import { render, screen } from "@/src/tests/test-utils";
import { EvidenceWatermarkOverlay } from "@/components/features/evidence/EvidenceWatermarkOverlay";

describe("S3-03 RED - EvidenceWatermarkOverlay", () => {
  it("[S3-03-RED-UNIT-05] renders tiled/rotated watermark with pseudonymized identity only", () => {
    render(
      <EvidenceWatermarkOverlay
        watermark={{
          pseudonymId: "USR-2FD9A1",
          timestampIso: "2026-02-14T10:45:00.000Z",
          environment: "staging",
          fullName: "Jane Doe",
          email: "jane.doe@acme.com",
        }}
      />,
    );

    expect(screen.getByTestId("evidence-watermark-overlay")).toBeInTheDocument();
    expect(screen.getAllByTestId("evidence-watermark-tile").length).toBeGreaterThanOrEqual(4);
    expect(screen.getByTestId("evidence-watermark-overlay")).toHaveAttribute(
      "data-watermark-style",
      "tilted-grid",
    );
    expect(screen.getByTestId("evidence-watermark-overlay")).toHaveTextContent("USR-2FD9A1");
    expect(screen.queryByText(/jane doe/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/jane\.doe@acme\.com/i)).not.toBeInTheDocument();
  });
});

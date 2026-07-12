import { describe, expect, it } from "vitest";
import { fireEvent, renderWithProviders, screen } from "@/src/tests/test-utils";
import { ScoreVersionBadge } from "@/components/coherence/ScoreVersionBadge";

describe("ScoreVersionBadge", () => {
  it("renders v1 label for canonical coherence-v1 score", () => {
    renderWithProviders(<ScoreVersionBadge scoreVersion="coherence-v1" />);

    expect(screen.getByText("(v1)")).toBeInTheDocument();
    expect(screen.getByLabelText(/v1 coherence score/i)).toBeInTheDocument();
  });

  it("renders v2 label for canonical coherence-v2 score", () => {
    renderWithProviders(<ScoreVersionBadge scoreVersion="coherence-v2" />);

    expect(screen.getByText("(v2)")).toBeInTheDocument();
    expect(screen.getByLabelText(/v2 evidence-aware coherence score/i)).toBeInTheDocument();
  });

  it("gracefully renders legacy v0_flag_based as v1 until DB migration", () => {
    // Phase F: legacy values backfill to coherence-v1 in the DB migration.
    // Until deployment finishes, the badge renders unknown legacy values as (v1).
    renderWithProviders(<ScoreVersionBadge scoreVersion="v0_flag_based" />);

    expect(screen.getByText("(v1)")).toBeInTheDocument();
    expect(screen.getByLabelText(/v1 coherence score/i)).toBeInTheDocument();
  });

  it("gracefully renders legacy v1_exponential_decay as v1 until DB migration", () => {
    renderWithProviders(<ScoreVersionBadge scoreVersion="v1_exponential_decay" />);

    expect(screen.getByText("(v1)")).toBeInTheDocument();
    expect(screen.getByLabelText(/v1 coherence score/i)).toBeInTheDocument();
  });

  it("shows customer-facing version guidance and a FAQ link in the tooltip", async () => {
    renderWithProviders(<ScoreVersionBadge scoreVersion="coherence-v1" />);

    fireEvent.mouseOver(screen.getByLabelText(/v1 coherence score/i));

    expect(
      (await screen.findAllByText(/v1 uses weighted finding severity/i))[0],
    ).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: /what changed/i })[0]).toHaveAttribute(
      "href",
      "/docs/customer/COHERENCE_V1_FAQ.md",
    );
  });

  it("data-score-version attribute reflects canonical resolved version", () => {
    renderWithProviders(<ScoreVersionBadge scoreVersion="v1_exponential_decay" />);
    const button = screen.getByRole("button");
    expect(button).toHaveAttribute("data-score-version", "coherence-v1");
  });
});

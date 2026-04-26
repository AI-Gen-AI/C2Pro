import { describe, expect, it } from "vitest";
import { fireEvent, renderWithProviders, screen } from "@/src/tests/test-utils";
import { ScoreVersionBadge } from "./ScoreVersionBadge";

describe("ScoreVersionBadge", () => {
  it("renders a compact v0 label for flag-based scores", () => {
    renderWithProviders(<ScoreVersionBadge scoreVersion="v0_flag_based" />);

    expect(screen.getByText("(v0)")).toBeInTheDocument();
    expect(screen.getByLabelText(/legacy flag-based coherence score/i)).toBeInTheDocument();
  });

  it("renders a compact v1 label for exponential-decay scores", () => {
    renderWithProviders(<ScoreVersionBadge scoreVersion="v1_exponential_decay" />);

    expect(screen.getByText("(v1)")).toBeInTheDocument();
    expect(screen.getByLabelText(/v1 exponential-decay coherence score/i)).toBeInTheDocument();
  });

  it("shows customer-facing version guidance and a FAQ link in the tooltip", async () => {
    renderWithProviders(<ScoreVersionBadge scoreVersion="v1_exponential_decay" />);

    fireEvent.mouseOver(screen.getByLabelText(/v1 exponential-decay coherence score/i));

    expect(
      (await screen.findAllByText(/v1 uses weighted finding severity/i))[0],
    ).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: /what changed/i })[0]).toHaveAttribute(
      "href",
      "/docs/customer/COHERENCE_V1_FAQ.md",
    );
  });
});

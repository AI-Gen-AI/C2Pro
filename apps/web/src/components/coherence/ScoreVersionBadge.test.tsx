import { describe, expect, it } from "vitest";
import { renderWithProviders, screen } from "@/src/tests/test-utils";
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
});

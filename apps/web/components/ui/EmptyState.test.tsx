import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { FolderOpen } from "lucide-react";
import { EmptyState } from "./EmptyState";

describe("EmptyState", () => {
  it("renders the title and description correctly", () => {
    render(
      <EmptyState
        title="No items found"
        description="Try adjusting your filters or create a new item."
      />
    );

    expect(screen.getByText("No items found")).toBeInTheDocument();
    expect(
      screen.getByText("Try adjusting your filters or create a new item.")
    ).toBeInTheDocument();
  });

  it("renders the icon when provided", () => {
    render(
      <EmptyState
        icon={FolderOpen}
        title="Empty Folder"
        description="Nothing here."
      />
    );

    expect(screen.getByText("Empty Folder")).toBeInTheDocument();
  });

  it("renders the custom CTA action button when provided", () => {
    render(
      <EmptyState
        title="Ready to start?"
        description="Click below to get started."
        action={<button data-testid="cta-btn">Get Started</button>}
      />
    );

    expect(screen.getByTestId("cta-btn")).toBeInTheDocument();
  });
});

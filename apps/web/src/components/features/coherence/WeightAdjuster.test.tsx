import type { ReactNode } from "react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { fireEvent, renderWithProviders, screen } from "@/src/tests/test-utils";
import { WeightAdjuster } from "./WeightAdjuster";

vi.mock("@clerk/nextjs", () => ({
  ClerkProvider: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

vi.mock("next/navigation", () => ({
  usePathname: () => "/projects/proj_demo_001/coherence",
  useSearchParams: () => new URLSearchParams(),
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    prefetch: vi.fn(),
  }),
}));

vi.mock("@/lib/api/generated", () => ({}));

describe("WeightAdjuster", () => {
  it("shows the default weights and allows saving when total is 100", async () => {
    const onSave = vi.fn();
    const user = userEvent.setup();

    renderWithProviders(<WeightAdjuster onSave={onSave} />);

    expect(screen.getAllByRole("slider")).toHaveLength(6);
    expect(screen.getByText(/total:\s*100/i)).toBeInTheDocument();

    const saveButton = screen.getByRole("button", { name: /save weights/i });
    expect(saveButton).toBeEnabled();

    await user.click(saveButton);

    expect(onSave).toHaveBeenCalledWith({
      scope: 20,
      budget: 15,
      time: 20,
      technical: 15,
      legal: 15,
      quality: 15,
    });
  });

  it("disables save when the total deviates from 100", async () => {
    const onSave = vi.fn();
    const user = userEvent.setup();

    renderWithProviders(<WeightAdjuster onSave={onSave} />);

    const scopeSlider = screen.getByRole("slider", { name: /scope/i });
    fireEvent.change(scopeSlider, { target: { value: 25 } });

    expect(screen.getByText(/total:\s*105/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /save weights/i })).toBeDisabled();
  });
});

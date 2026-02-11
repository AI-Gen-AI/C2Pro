import { describe, expect, it, vi } from "vitest";
import { renderWithProviders, screen } from "@/src/tests/test-utils";
import { Toaster } from "./toaster";

vi.mock("@/hooks/use-toast", () => ({
  useToast: () => ({
    toasts: [
      {
        id: "toast-1",
        title: "Saved",
        description: "Settings updated",
        open: true,
      },
    ],
  }),
}));

describe("Toaster", () => {
  it("renders toast content from the store", () => {
    renderWithProviders(<Toaster />);

    expect(screen.getByText("Saved")).toBeInTheDocument();
    expect(screen.getByText("Settings updated")).toBeInTheDocument();
  });
});

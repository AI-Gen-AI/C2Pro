import { describe, expect, it, vi } from "vitest";
import { renderWithProviders } from "@/src/tests/test-utils";
import { Toaster } from "./sonner";

vi.mock("next-themes", () => ({
  useTheme: () => ({ theme: "light" }),
}));

describe("Toaster", () => {
  it("renders without crashing", () => {
    const { container } = renderWithProviders(<Toaster />);
    expect(container.querySelector(".toaster")).toBeTruthy();
  });
});

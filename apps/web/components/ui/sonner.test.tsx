import { describe, expect, it, vi } from "vitest";
import { renderWithProviders } from "@/src/tests/test-utils";
import { Toaster } from "./sonner";

vi.mock("next-themes", async (importOriginal) => {
  const actual = await importOriginal<typeof import("next-themes")>();
  return {
    ...actual,
    useTheme: () => ({ theme: "light" }),
  };
});

describe("Toaster", () => {
  it("renders without crashing", () => {
    expect(() => renderWithProviders(<Toaster />)).not.toThrow();
  });
});

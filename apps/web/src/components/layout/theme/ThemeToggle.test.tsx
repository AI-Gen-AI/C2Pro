import type { ReactNode } from "react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import userEvent from "@testing-library/user-event";
import { renderWithProviders, screen } from "@/src/tests/test-utils";

let currentTheme: "light" | "dark" | "system" = "light";
const setTheme = vi.fn();

vi.mock("@clerk/nextjs", () => ({
  ClerkProvider: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

vi.mock("next/navigation", () => ({
  usePathname: () => "/dashboard",
  useSearchParams: () => new URLSearchParams(),
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    prefetch: vi.fn(),
  }),
}));

vi.mock("@/lib/api/generated", () => ({}));

vi.mock("next-themes", async (importOriginal) => {
  const actual = await importOriginal<typeof import("next-themes")>();
  return {
    ...actual,
    useTheme: () => ({
      theme: currentTheme,
      setTheme,
    }),
  };
});

import { ThemeToggle } from "./ThemeToggle";

describe("ThemeToggle", () => {
  beforeEach(() => {
    setTheme.mockClear();
    currentTheme = "light";
  });

  it("toggles from light to dark when activated", async () => {
    const user = userEvent.setup();
    renderWithProviders(<ThemeToggle />);

    await user.click(
      screen.getByRole("button", { name: /toggle dark mode/i }),
    );

    expect(setTheme).toHaveBeenCalledWith("dark");
  });

  it("toggles from dark to light when activated", async () => {
    const user = userEvent.setup();
    currentTheme = "dark";
    renderWithProviders(<ThemeToggle />);

    await user.click(
      screen.getByRole("button", { name: /toggle dark mode/i }),
    );

    expect(setTheme).toHaveBeenCalledWith("light");
  });
});

import type { ReactNode } from "react";
import fs from "fs";
import path from "path";
import { describe, expect, it, vi } from "vitest";
import { renderWithProviders, screen } from "@/src/tests/test-utils";
import RootLayout from "@/app/layout";

vi.mock("@clerk/nextjs", () => ({
  ClerkProvider: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

vi.mock("next/navigation", () => ({
  usePathname: () => "/",
  useSearchParams: () => new URLSearchParams(),
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    prefetch: vi.fn(),
  }),
}));

vi.mock("next/font/local", () => ({
  default: (options: { variable?: string }) => ({
    variable: options.variable ?? "",
  }),
}));

vi.mock("@/lib/api/generated", () => ({}));

describe("RootLayout local fonts", () => {
  it("applies local font variables to the html element", () => {
    renderWithProviders(
      <RootLayout>
        <div>App Content</div>
      </RootLayout>,
    );

    expect(screen.getByText("App Content")).toBeInTheDocument();
    expect(document.documentElement.className).toContain("--font-sans");
    expect(document.documentElement.className).toContain("--font-mono");
  });

  it("includes required local font files for next/font/local", () => {
    const fontDir = path.resolve(process.cwd(), "fonts");
    const requiredFonts = [
      "InterVariable-roman.woff2",
      "InterVariable-italic.woff2",
      "JetBrainsMono-Regular.woff2",
    ];

    const missing = requiredFonts.filter(
      (file) => !fs.existsSync(path.join(fontDir, file)),
    );

    expect(missing).toEqual([]);
  });
});

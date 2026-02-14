import type { ReactNode } from "react";
import fs from "fs";
import path from "path";
import { describe, expect, it, vi } from "vitest";
import RootLayout from "@/app/layout";

vi.mock("@clerk/nextjs", () => ({
  ClerkProvider: ({ children }: { children: ReactNode }) => <>{children}</>,
  useAuth: () => ({
    isSignedIn: true,
    isLoaded: true,
    getToken: async () => "test-token",
    signOut: async () => undefined,
  }),
  useOrganization: () => ({
    organization: { id: "test-org", name: "Test Org" },
  }),
  useUser: () => ({
    user: {
      id: "user-1",
      firstName: "Test",
      lastName: "User",
      primaryEmailAddress: { emailAddress: "test@example.com" },
      publicMetadata: {},
      unsafeMetadata: {},
    },
  }),
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
    const element = RootLayout({ children: <div>App Content</div> });
    expect(element.type).toBe("html");
    expect(element.props.className).toContain("--font-sans");
    expect(element.props.className).toContain("--font-mono");

    const body = element.props.children;
    expect(body.type).toBe("body");
    const providers = body.props.children;
    expect(providers.props.children).toMatchObject({
      props: { children: "App Content" },
    });
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

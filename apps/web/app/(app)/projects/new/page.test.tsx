import { describe, expect, it, vi } from "vitest";
import { redirect } from "next/navigation";
import NewProjectPage from "./page";

vi.mock("next/navigation", () => ({
  redirect: vi.fn(),
}));

describe("NewProjectPage", () => {
  it("redirects to /projects?create=1", () => {
    NewProjectPage();
    expect(redirect).toHaveBeenCalledWith("/projects?create=1");
  });
});

/**
 * Test Suite ID: TASK-021
 * Route Coverage: top-level evidence page loads projects through fetch-safe services
 */
import { renderWithProviders, screen } from "@/src/tests/test-utils";
import { waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import EvidencePage from "./page";

const pushMock = vi.fn();
const listProjectsMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: pushMock,
  }),
}));

vi.mock("@/lib/api/services/dashboard", () => ({
  listProjects: (...args: unknown[]) => listProjectsMock(...args),
}));

describe("EvidencePage", () => {
  beforeEach(() => {
    pushMock.mockReset();
    listProjectsMock.mockReset();
  });

  it("loads projects from the backend and routes to project evidence", async () => {
    const user = userEvent.setup();

    listProjectsMock.mockResolvedValue([
      {
        id: "project-1",
        tenant_id: "tenant-1",
        name: "Hospital Central",
        status: "active",
      },
      {
        id: "project-2",
        tenant_id: "tenant-1",
        name: "Metro Extension",
        status: "review",
      },
    ]);

    renderWithProviders(<EvidencePage />);

    await waitFor(() =>
      expect(
        screen.getByRole("heading", { name: /hospital central/i }),
      ).toBeInTheDocument(),
    );
    expect(
      screen.getByRole("heading", { name: /metro extension/i }),
    ).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /open hospital central evidence/i }));

    expect(pushMock).toHaveBeenCalledWith("/projects/project-1/evidence");
  });
});

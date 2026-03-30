/**
 * Test Suite ID: TASK-1347
 * Route Coverage: Top-level evidence page loads backend projects for evidence navigation
 */
import { renderWithProviders, screen } from "@/src/tests/test-utils";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import EvidencePage from "./page";

const pushMock = vi.fn();
const useListProjectsMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: pushMock,
  }),
}));

vi.mock("@/lib/api/generated/projects/projects", () => ({
  useListProjectsApiV1ProjectsGet: (...args: unknown[]) => useListProjectsMock(...args),
}));

describe("EvidencePage", () => {
  beforeEach(() => {
    pushMock.mockReset();
    useListProjectsMock.mockReset();
  });

  it("loads projects from the backend and routes to project evidence", async () => {
    const user = userEvent.setup();

    useListProjectsMock.mockReturnValue({
      data: {
        items: [
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
        ],
        total: 2,
      },
      isLoading: false,
      error: null,
    });

    renderWithProviders(<EvidencePage />);

    expect(
      screen.getByRole("heading", { name: /hospital central/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: /metro extension/i }),
    ).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /open hospital central evidence/i }));

    expect(pushMock).toHaveBeenCalledWith("/projects/project-1/evidence");
  });
});

/**
 * Test Suite ID: TASK-013
 * Route Coverage: Projects list page
 */
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, renderWithProviders, screen } from "@/src/tests/test-utils";
import ProjectsPage from "./page";

const useProjectsMock = vi.fn();
const useAuthStoreMock = vi.fn();

vi.mock("@clerk/nextjs", () => ({
  ClerkProvider: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

vi.mock("next/link", () => ({
  default: ({
    children,
    href,
  }: {
    children: ReactNode;
    href: string;
  }) => <a href={href}>{children}</a>,
}));

vi.mock("@/hooks/useProjects", () => ({
  useProjects: (...args: unknown[]) => useProjectsMock(...args),
}));

vi.mock("@/stores/auth", () => ({
  useAuthStore: (selector: (state: { token: string | null }) => unknown) =>
    useAuthStoreMock(selector),
}));

afterEach(() => {
  vi.restoreAllMocks();
});

describe("ProjectsPage real-data boundary", () => {
  it("shows the auth gate while the token is missing", () => {
    useAuthStoreMock.mockImplementation(
      (selector: (state: { token: string | null }) => unknown) =>
        selector({ token: null }),
    );
    useProjectsMock.mockReturnValue({
      data: undefined,
      isLoading: false,
      error: null,
    });

    renderWithProviders(<ProjectsPage />);

    expect(screen.getByText(/authenticating/i)).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: /^projects$/i })).not.toBeInTheDocument();
  });

  it("renders the real empty state instead of seeded demo records", () => {
    useAuthStoreMock.mockImplementation(
      (selector: (state: { token: string | null }) => unknown) =>
        selector({ token: "real-token" }),
    );
    useProjectsMock.mockReturnValue({
      data: [],
      isLoading: false,
      error: null,
    });

    renderWithProviders(<ProjectsPage />);

    expect(
      screen.getByRole("heading", { level: 1, name: /^projects$/i }),
    ).toBeInTheDocument();
    expect(screen.getByText(/0 projects/i)).toBeInTheDocument();
    expect(screen.getByText(/no projects yet/i)).toBeInTheDocument();
    expect(
      screen.queryByText(/petrochemical plant epc/i),
    ).not.toBeInTheDocument();
  });

  it("shows the loading state while project data is still being fetched", () => {
    useAuthStoreMock.mockImplementation(
      (selector: (state: { token: string | null }) => unknown) =>
        selector({ token: "real-token" }),
    );
    useProjectsMock.mockReturnValue({
      data: undefined,
      isLoading: true,
      error: null,
    });

    renderWithProviders(<ProjectsPage />);

    expect(screen.getByText(/loading\.\.\./i)).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1, name: /^projects$/i })).toBeInTheDocument();
  });

  it("renders project rows returned by the backend and exposes the create link", () => {
    useAuthStoreMock.mockImplementation(
      (selector: (state: { token: string | null }) => unknown) =>
        selector({ token: "real-token" }),
    );
    useProjectsMock.mockReturnValue({
      data: [
        {
          id: "proj-1",
          name: "North Sea Platform",
          description: "Active EPC delivery",
          code: "NSP-001",
        },
        {
          id: "proj-2",
          name: "Airport Retrofit",
          description: null,
          code: "AIR-002",
        },
      ],
      isLoading: false,
      error: null,
    });

    renderWithProviders(<ProjectsPage />);

    expect(screen.getByRole("link", { name: /north sea platform/i })).toHaveAttribute(
      "href",
      "/projects/proj-1",
    );
    expect(screen.getByText("Active EPC delivery")).toBeInTheDocument();
    expect(screen.getByText("AIR-002")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /new project/i })).toHaveAttribute(
      "href",
      "/projects/new",
    );
  });

  it("opens a batch import dialog and previews parsed project rows", () => {
    useAuthStoreMock.mockImplementation(
      (selector: (state: { token: string | null }) => unknown) =>
        selector({ token: "real-token" }),
    );
    useProjectsMock.mockReturnValue({
      data: [],
      isLoading: false,
      error: null,
    });

    renderWithProviders(<ProjectsPage />);

    fireEvent.click(screen.getByRole("button", { name: /batch import/i }));

    expect(screen.getByText(/import projects in bulk/i)).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(/project rows/i), {
      target: {
        value:
          "Hospital Central,EPC,HC-001\nPort Expansion,Maritime,PE-002",
      },
    });

    expect(screen.getByText(/2 project rows ready to import/i)).toBeInTheDocument();
    expect(screen.getAllByText(/hospital central/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/port expansion/i).length).toBeGreaterThan(0);
  });

  it("opens project templates and previews the selected template structure", () => {
    useAuthStoreMock.mockImplementation(
      (selector: (state: { token: string | null }) => unknown) =>
        selector({ token: "real-token" }),
    );
    useProjectsMock.mockReturnValue({
      data: [],
      isLoading: false,
      error: null,
    });

    renderWithProviders(<ProjectsPage />);

    fireEvent.click(screen.getByRole("button", { name: /project templates/i }));

    expect(screen.getByText(/start from a project template/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /epc megaproject/i })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /industrial retrofit/i }));

    expect(screen.getByText(/industrial retrofit recovery/i)).toBeInTheDocument();
    expect(screen.getByText(/shutdown planning/i)).toBeInTheDocument();
    expect(screen.getByText(/brownfield/i)).toBeInTheDocument();
  });

  it("exports the current projects list to PDF, Excel, and JSON", () => {
    useAuthStoreMock.mockImplementation(
      (selector: (state: { token: string | null }) => unknown) =>
        selector({ token: "real-token" }),
    );
    useProjectsMock.mockReturnValue({
      data: [
        {
          id: "proj-1",
          name: "North Sea Platform",
          description: "Active EPC delivery",
          code: "NSP-001",
        },
        {
          id: "proj-2",
          name: "Airport Retrofit",
          description: null,
          code: "AIR-002",
        },
      ],
      isLoading: false,
      error: null,
    });

    const popupDocument = {
      write: vi.fn(),
      close: vi.fn(),
    };
    const popupWindow = {
      document: popupDocument,
      focus: vi.fn(),
      print: vi.fn(),
    };
    const openSpy = vi
      .spyOn(window, "open")
      .mockReturnValue(popupWindow as unknown as Window);
    const createObjectUrlSpy = vi
      .spyOn(URL, "createObjectURL")
      .mockReturnValue("blob:projects-export");
    const revokeObjectUrlSpy = vi
      .spyOn(URL, "revokeObjectURL")
      .mockImplementation(() => undefined);
    const appendSpy = vi.spyOn(document.body, "appendChild");
    const removeSpy = vi.spyOn(document.body, "removeChild");
    const anchorClickSpy = vi
      .spyOn(HTMLAnchorElement.prototype, "click")
      .mockImplementation(() => undefined);

    renderWithProviders(<ProjectsPage />);

    fireEvent.click(screen.getByRole("button", { name: /export pdf/i }));

    expect(openSpy).toHaveBeenCalled();
    expect(popupDocument.write).toHaveBeenCalledWith(
      expect.stringContaining("North Sea Platform"),
    );
    expect(popupWindow.print).toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: /export excel/i }));
    fireEvent.click(screen.getByRole("button", { name: /export json/i }));

    expect(createObjectUrlSpy).toHaveBeenCalledTimes(2);
    expect(anchorClickSpy).toHaveBeenCalledTimes(2);
    expect(appendSpy).toHaveBeenCalled();
    expect(removeSpy).toHaveBeenCalled();
    expect(revokeObjectUrlSpy).toHaveBeenCalledWith("blob:projects-export");
  });

  it("surfaces the backend error instead of rendering demo-backed project rows", () => {
    useAuthStoreMock.mockImplementation(
      (selector: (state: { token: string | null }) => unknown) =>
        selector({ token: "real-token" }),
    );
    useProjectsMock.mockReturnValue({
      data: undefined,
      isLoading: false,
      error: new Error("401 Unauthorized"),
    });

    renderWithProviders(<ProjectsPage />);

    expect(screen.getByText(/api request failed/i)).toBeInTheDocument();
    expect(
      screen.queryByText(/petrochemical plant epc/i),
    ).not.toBeInTheDocument();
  });
});

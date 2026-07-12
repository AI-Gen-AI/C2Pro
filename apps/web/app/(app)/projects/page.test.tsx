/**
 * Test Suite ID: TASK-013
 * Route Coverage: Projects list page
 */
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  fireEvent,
  renderWithProviders,
  screen,
  waitFor,
  within,
} from "@/src/tests/test-utils";
import ProjectsPage from "./page";

const useProjectsMock = vi.fn();
const useUpdateProjectMock = vi.fn();
const useCreateProjectMock = vi.fn();
const useProjectQuickViewSummaryMock = vi.fn();
const useAuthStoreMock = vi.fn();
const pushMock = vi.fn();
const replaceMock = vi.fn();
const searchParamsState = { value: new URLSearchParams() };

vi.mock("@clerk/nextjs", () => ({
  ClerkProvider: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: pushMock,
    replace: replaceMock,
  }),
  useSearchParams: () => searchParamsState.value,
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

vi.mock("@/hooks/useUpdateProject", () => ({
  useUpdateProject: (...args: unknown[]) => useUpdateProjectMock(...args),
}));

vi.mock("@/hooks/useProjectQuickViewSummary", () => ({
  useProjectQuickViewSummary: (...args: unknown[]) =>
    useProjectQuickViewSummaryMock(...args),
}));

vi.mock("@/lib/api/generated/projects/projects", () => ({
  useCreateProjectApiV1ProjectsPost: (...args: unknown[]) =>
    useCreateProjectMock(...args),
}));

vi.mock("@/stores/auth", () => ({
  useAuthStore: (selector: (state: { token: string | null }) => unknown) =>
    useAuthStoreMock(selector),
}));

vi.mock("@/components/features/projects/LazyProjectDialogs", () => ({
  LazyProjectBatchImportDialog: ({
    open,
    importDraft,
    importPreview,
    onImportDraftChange,
  }: {
    open: boolean;
    importDraft: string;
    importPreview: Array<{ name: string; type: string; code: string }>;
    onImportDraftChange: (value: string) => void;
  }) =>
    open ? (
      <div role="dialog" aria-label="Import projects in bulk">
        <h2>Import projects in bulk</h2>
        <label htmlFor="project-import-rows">Project rows</label>
        <textarea
          id="project-import-rows"
          value={importDraft}
          onChange={(event) => onImportDraftChange(event.target.value)}
        />
        <div>
          {importPreview.length} project row
          {importPreview.length === 1 ? "" : "s"} ready to import
        </div>
        <ul>
          {importPreview.map((row, index) => (
            <li key={`${row.name}-${row.code}-${index}`}>{row.name}</li>
          ))}
        </ul>
      </div>
    ) : null,
  LazyProjectTemplatesDialog: ({
    open,
    selectedTemplate,
    templates,
    onSelectTemplate,
  }: {
    open: boolean;
    selectedTemplate: {
      summary: string;
      phaseFocus: string[];
      tags: string[];
    } | null;
    templates: Array<{ id: string; name: string }>;
    onSelectTemplate: (templateId: string) => void;
  }) =>
    open ? (
      <div role="dialog" aria-label="Start from a project template">
        <h2>Start from a project template</h2>
        {templates.map((template) => (
          <button key={template.id} type="button" onClick={() => onSelectTemplate(template.id)}>
            {template.name}
          </button>
        ))}
        {selectedTemplate ? (
          <div>
            <div>{selectedTemplate.summary}</div>
            {selectedTemplate.phaseFocus.map((item) => (
              <div key={item}>{item}</div>
            ))}
            {selectedTemplate.tags.map((tag) => (
              <div key={tag}>{tag}</div>
            ))}
          </div>
        ) : null}
      </div>
    ) : null,
}));

vi.mock("@/components/ui/dropdown-menu", () => {
  function DropdownMenu({ children }: { children: ReactNode }) {
    return <div>{children}</div>;
  }

  function DropdownMenuTrigger({ children }: { children: ReactNode }) {
    return <>{children}</>;
  }

  function DropdownMenuContent({
    children,
    className,
  }: {
    children: ReactNode;
    className?: string;
  }) {
    return <div className={className}>{children}</div>;
  }

  function DropdownMenuLabel({
    children,
    className,
  }: {
    children: ReactNode;
    className?: string;
  }) {
    return <div className={className}>{children}</div>;
  }

  function DropdownMenuSeparator() {
    return <hr />;
  }

  function DropdownMenuCheckboxItem({
    children,
    checked,
    onCheckedChange,
  }: {
    children: ReactNode;
    checked?: boolean;
    onCheckedChange?: (checked: boolean) => void;
  }) {
    return (
      <label>
        <input
          type="checkbox"
          checked={checked}
          onChange={(event) => onCheckedChange?.(event.target.checked)}
        />
        {children}
      </label>
    );
  }

  return {
    DropdownMenu,
    DropdownMenuTrigger,
    DropdownMenuContent,
    DropdownMenuLabel,
    DropdownMenuSeparator,
    DropdownMenuCheckboxItem,
  };
});

afterEach(() => {
  vi.restoreAllMocks();
  window.localStorage.clear();
});

beforeEach(() => {
  pushMock.mockReset();
  replaceMock.mockReset();
  replaceMock.mockImplementation((url: string) => {
    const query = url.includes("?") ? url.split("?")[1] : "";
    searchParamsState.value = new URLSearchParams(query);
  });
  searchParamsState.value = new URLSearchParams();
  useUpdateProjectMock.mockReturnValue({
    mutateAsync: vi.fn(),
    isPending: false,
    error: null,
  });
  useCreateProjectMock.mockReturnValue({
    mutateAsync: vi.fn(),
    isPending: false,
    error: null,
  });
  useProjectQuickViewSummaryMock.mockReturnValue({
    data: null,
    isLoading: false,
    error: null,
  });
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

  it("renders project rows returned by the backend and exposes the create action", () => {
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
    expect(screen.getByRole("button", { name: /new project/i })).toBeInTheDocument();
  });

  it("opens a project creation wizard and keeps next disabled until the required name is provided", async () => {
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

    fireEvent.click(screen.getByRole("button", { name: /new project/i }));

    const wizard = await screen.findByRole("dialog", { name: /create project/i });
    expect(wizard).toHaveClass("bg-background/95");
    expect(wizard).toHaveClass("shadow-2xl");
    expect(within(wizard).getByText(/step 1 of 3/i)).toBeInTheDocument();
    expect(within(wizard).getByRole("button", { name: /next step/i })).toBeDisabled();

    fireEvent.change(within(wizard).getByLabelText(/project name/i), {
      target: { value: "Atlas Ridge" },
    });

    expect(within(wizard).getByRole("button", { name: /next step/i })).toBeEnabled();
  });

  it("creates a project from the wizard review step and redirects to documents upload", async () => {
    const mutateAsync = vi.fn().mockResolvedValue({ id: "proj-500" });
    useCreateProjectMock.mockReturnValue({
      mutateAsync,
      isPending: false,
      error: null,
    });
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

    fireEvent.click(screen.getByRole("button", { name: /new project/i }));

    const wizard = await screen.findByRole("dialog", { name: /create project/i });
    fireEvent.change(within(wizard).getByLabelText(/project name/i), {
      target: { value: "Atlas Ridge" },
    });
    fireEvent.change(within(wizard).getByLabelText(/project code/i), {
      target: { value: "ATR-500" },
    });
    fireEvent.change(within(wizard).getByLabelText(/project type/i), {
      target: { value: "epc" },
    });
    fireEvent.click(within(wizard).getByRole("button", { name: /next step/i }));

    fireEvent.change(within(wizard).getByLabelText(/client name/i), {
      target: { value: "Client Corp" },
    });
    fireEvent.change(within(wizard).getByLabelText(/project description/i), {
      target: { value: "Phase one delivery" },
    });
    fireEvent.change(within(wizard).getByLabelText(/currency/i), {
      target: { value: "USD" },
    });
    fireEvent.click(within(wizard).getByRole("button", { name: /review project/i }));

    expect(within(wizard).getByText(/step 3 of 3/i)).toBeInTheDocument();
    expect(within(wizard).getByText(/atlas ridge/i)).toBeInTheDocument();
    expect(within(wizard).getByText(/client corp/i)).toBeInTheDocument();
    fireEvent.click(within(wizard).getByRole("button", { name: /create project/i }));

    expect(mutateAsync).toHaveBeenCalledWith({
      data: {
        name: "Atlas Ridge",
        code: "ATR-500",
        description: "Phase one delivery",
        client_name: "Client Corp",
        currency: "USD",
        project_type: "epc",
      },
    });
    await waitFor(() => {
      expect(pushMock).toHaveBeenCalledWith("/projects/proj-500/documents");
    });
  });

  it("allows users to customize visible columns without hiding the project link", () => {
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
      ],
      isLoading: false,
      error: null,
    });

    renderWithProviders(<ProjectsPage />);

    expect(
      screen.getByText(/visible columns/i).closest(".rounded-xl"),
    ).toHaveClass("rounded-xl");
    expect(screen.getByRole("columnheader", { name: /project/i })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: /description/i })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: /code/i })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("checkbox", { name: /description/i }));
    fireEvent.click(screen.getByRole("checkbox", { name: /code/i }));

    expect(screen.getByRole("columnheader", { name: /project/i })).toBeInTheDocument();
    expect(
      screen.queryByRole("columnheader", { name: /description/i }),
    ).not.toBeInTheDocument();
    expect(screen.queryByRole("columnheader", { name: /code/i })).not.toBeInTheDocument();
    expect(screen.queryByText("Active EPC delivery")).not.toBeInTheDocument();
    expect(screen.queryByText("NSP-001")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: /north sea platform/i })).toHaveAttribute(
      "href",
      "/projects/proj-1",
    );
  });

  it("saves custom filter presets and reapplies them after remount", () => {
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
          description: "Terminal upgrade",
          code: "AIR-002",
        },
      ],
      isLoading: false,
      error: null,
    });
    const { unmount } = renderWithProviders(<ProjectsPage />);

    fireEvent.change(screen.getByPlaceholderText(/search projects/i), {
      target: { value: "airport" },
    });
    fireEvent.click(screen.getByRole("checkbox", { name: /description/i }));
    fireEvent.click(screen.getByRole("button", { name: /save preset/i }));

    const presetDialog = screen.getByRole("dialog", { name: /save current preset/i });
    expect(presetDialog).toHaveClass("bg-background/95");
    fireEvent.change(within(presetDialog).getByLabelText(/preset name/i), {
      target: { value: "Airport focus" },
    });
    fireEvent.click(within(presetDialog).getByRole("button", { name: /^save preset$/i }));

    expect(screen.getByRole("button", { name: /airport focus/i })).toBeInTheDocument();
    expect(screen.queryByText(/north sea platform/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("columnheader", { name: /description/i })).not.toBeInTheDocument();

    unmount();

    renderWithProviders(<ProjectsPage />);

    fireEvent.change(screen.getByPlaceholderText(/search projects/i), {
      target: { value: "" },
    });

    expect(screen.getByText(/north sea platform/i)).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: /description/i })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /airport focus/i }));

    expect(screen.queryByText(/north sea platform/i)).not.toBeInTheDocument();
    expect(screen.getByText(/airport retrofit/i)).toBeInTheDocument();
    expect(screen.queryByRole("columnheader", { name: /description/i })).not.toBeInTheDocument();
  });

  it("supports inline editing for project name, description, and code", async () => {
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
      ],
      isLoading: false,
      error: null,
    });
    const mutateAsync = vi.fn().mockResolvedValue({
      id: "proj-1",
      name: "North Sea Revamp",
      description: "Recovered offshore program",
      code: "NSR-009",
    });
    useUpdateProjectMock.mockReturnValue({
      mutateAsync,
      isPending: false,
      error: null,
    });

    renderWithProviders(<ProjectsPage />);

    fireEvent.click(screen.getByRole("button", { name: /edit north sea platform/i }));

    fireEvent.change(screen.getByLabelText(/project name/i), {
      target: { value: "North Sea Revamp" },
    });
    fireEvent.change(screen.getByLabelText(/project description/i), {
      target: { value: "Recovered offshore program" },
    });
    fireEvent.change(screen.getByLabelText(/project code/i), {
      target: { value: "NSR-009" },
    });

    fireEvent.click(screen.getByRole("button", { name: /save project changes/i }));

    expect(mutateAsync).toHaveBeenCalledWith({
      projectId: "proj-1",
      data: {
        name: "North Sea Revamp",
        description: "Recovered offshore program",
        code: "NSR-009",
      },
    });

    expect(await screen.findByRole("link", { name: /north sea revamp/i })).toHaveAttribute(
      "href",
      "/projects/proj-1",
    );
    expect(screen.getByText(/recovered offshore program/i)).toBeInTheDocument();
    expect(screen.getByText("NSR-009")).toBeInTheDocument();
  });

  it("opens a backend-backed project quick-view sheet from the project list", () => {
    useAuthStoreMock.mockImplementation(
      (selector: (state: { token: string | null }) => unknown) =>
        selector({ token: "real-token" }),
    );
    useProjectsMock.mockReturnValue({
      data: [
        {
          id: "proj-1",
          name: "North Sea Platform",
          description: "Offshore platform upgrade",
          code: "NSP-001",
          status: "active",
          project_type: "epc",
        },
      ],
      isLoading: false,
      error: null,
    });
    useProjectQuickViewSummaryMock.mockImplementation((projectId: string | null) => ({
      data:
        projectId === "proj-1"
          ? {
              project_id: "proj-1",
              tenant_id: "tenant-1",
              name: "North Sea Platform",
              code: "NSP-001",
              description: "Offshore platform upgrade",
              project_type: "epc",
              status: "active",
              coherence_score: 91,
              client_name: "Harbor Authority",
              open_alert_count: 3,
              critical_alert_count: 1,
              top_alerts: [
                {
                  id: "alert-1",
                  title: "Permit missing",
                  severity: "critical",
                  status: "open",
                  created_at: "2026-04-02T10:00:00Z",
                },
                {
                  id: "alert-2",
                  title: "Budget drift detected",
                  severity: "medium",
                  status: "open",
                  created_at: "2026-04-02T08:00:00Z",
                },
              ],
              updated_at: "2026-04-02T11:00:00Z",
            }
          : null,
      isLoading: false,
      error: null,
    }));

    renderWithProviders(<ProjectsPage />);

    fireEvent.click(
      screen.getByRole("button", { name: /quick view north sea platform/i }),
    );

    const quickViewDialog = screen.getByRole("dialog", {
      name: /project quick view/i,
    });

    expect(quickViewDialog).toHaveClass("bg-background/95");
    expect(quickViewDialog).toHaveClass("shadow-2xl");
    expect(within(quickViewDialog).getByText("North Sea Platform")).toBeInTheDocument();
    expect(within(quickViewDialog).getByText("Harbor Authority")).toBeInTheDocument();
    expect(within(quickViewDialog).getByText(/coherence score/i)).toBeInTheDocument();
    expect(within(quickViewDialog).getByText("91")).toBeInTheDocument();
    expect(within(quickViewDialog).getByText(/3 open alerts/i)).toBeInTheDocument();
    expect(within(quickViewDialog).getByText(/1 critical alert/i)).toBeInTheDocument();
    expect(within(quickViewDialog).getByText("Permit missing")).toBeInTheDocument();
    expect(within(quickViewDialog).getByText("Budget drift detected")).toBeInTheDocument();
    expect(
      within(quickViewDialog).getByRole("link", { name: /open full view/i }),
    ).toHaveAttribute("href", "/projects/proj-1");
    expect(
      within(quickViewDialog).getByRole("link", { name: /view evidence/i }),
    ).toHaveAttribute("href", "/projects/proj-1/evidence");
  });

  it("toggles between table and kanban project views", () => {
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
          status: "active",
        },
        {
          id: "proj-2",
          name: "Airport Retrofit",
          description: "Terminal upgrade",
          code: "AIR-002",
          status: "draft",
        },
      ],
      isLoading: false,
      error: null,
    });

    renderWithProviders(<ProjectsPage />);

    expect(screen.getByRole("table", { name: /project list/i })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /kanban view/i }));

    expect(screen.queryByRole("table", { name: /project list/i })).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /active/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /draft/i })).toBeInTheDocument();
    expect(screen.getByText(/north sea platform/i)).toBeInTheDocument();
    expect(screen.getByText(/airport retrofit/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /table view/i }));

    expect(screen.getByRole("table", { name: /project list/i })).toBeInTheDocument();
  });

  it("applies advanced search builder filters for status and type with reset support", () => {
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
          status: "active",
          project_type: "epc",
        },
        {
          id: "proj-2",
          name: "Airport Retrofit",
          description: "Terminal upgrade",
          code: "AIR-002",
          status: "draft",
          project_type: "building",
        },
        {
          id: "proj-3",
          name: "Port Expansion",
          description: "Marine logistics",
          code: "POR-100",
          status: "active",
          project_type: "maritime",
        },
      ],
      isLoading: false,
      error: null,
    });

    renderWithProviders(<ProjectsPage />);

    fireEvent.change(screen.getByLabelText(/status filter/i), {
      target: { value: "active" },
    });
    fireEvent.change(screen.getByLabelText(/type filter/i), {
      target: { value: "epc" },
    });

    expect(screen.getByText(/status:\s*active/i)).toBeInTheDocument();
    expect(screen.getByText(/type:\s*epc/i)).toBeInTheDocument();
    expect(screen.getByText(/north sea platform/i)).toBeInTheDocument();
    expect(screen.queryByText(/airport retrofit/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/port expansion/i)).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /reset filters/i }));

    expect(screen.getByText(/north sea platform/i)).toBeInTheDocument();
    expect(screen.getByText(/airport retrofit/i)).toBeInTheDocument();
    expect(screen.getByText(/port expansion/i)).toBeInTheDocument();
    expect(screen.queryByText(/status:\s*active/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/type:\s*epc/i)).not.toBeInTheDocument();
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

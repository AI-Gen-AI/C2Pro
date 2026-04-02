/**
 * Test Suite ID: TASK-1258
 * Route Coverage: Alerts analytics dashboard
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, renderWithProviders, screen, waitFor, within } from "@/src/tests/test-utils";
import AlertsPage from "./page";

const useAlertsMock = vi.fn();
const getAlertWorkspaceSettingsMock = vi.fn();
const saveAlertWorkspaceSettingsMock = vi.fn();
const bulkResolveAlertsMock = vi.fn();

vi.mock("@/hooks/useAlerts", () => ({
  useAlerts: () => useAlertsMock(),
}));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    getAlertWorkspaceSettings: (...args: unknown[]) => getAlertWorkspaceSettingsMock(...args),
    saveAlertWorkspaceSettings: (...args: unknown[]) => saveAlertWorkspaceSettingsMock(...args),
    bulkResolveAlerts: (...args: unknown[]) => bulkResolveAlertsMock(...args),
  };
});

describe("AlertsPage analytics dashboard", () => {
  beforeEach(() => {
    localStorage.clear();
    useAlertsMock.mockReset();
    getAlertWorkspaceSettingsMock.mockReset();
    saveAlertWorkspaceSettingsMock.mockReset();
    bulkResolveAlertsMock.mockReset();
    getAlertWorkspaceSettingsMock.mockResolvedValue(null);
    saveAlertWorkspaceSettingsMock.mockImplementation(
      async (payload: unknown) => payload,
    );
    bulkResolveAlertsMock.mockResolvedValue({
      processedCount: 2,
      alertIds: ["a-1", "a-2"],
      status: "Resolved",
    });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("tracks SLA status and flags overdue alerts from API-backed due dates", async () => {
    vi.spyOn(Date, "now").mockReturnValue(
      new Date("2026-04-01T12:00:00Z").getTime(),
    );

    useAlertsMock.mockReturnValue({
      alerts: [
        {
          id: "a-1",
          severity: "Critical",
          type: "Schedule",
          title: "Date mismatch",
          description: "Contract and schedule diverge",
          project: "Hospital Central",
          status: "Open",
          created_at: "2026-04-01T08:30:00Z",
          sla_due_at: "2026-04-01T10:30:00Z",
          sla_policy_name: "Critical Response Window",
        },
        {
          id: "a-2",
          severity: "High",
          type: "Budget",
          title: "Budget overrun risk",
          description: "Procurement package exceeds forecast",
          project: "Hospital Central",
          status: "In Progress",
          created_at: "2026-03-31T02:00:00Z",
          sla_due_at: "2026-04-01T02:00:00Z",
          sla_policy_name: "High Priority Follow-up",
        },
        {
          id: "a-3",
          severity: "Medium",
          type: "Stakeholder",
          title: "Missing approval",
          description: "Owner missing for review gate",
          project: "Port Expansion",
          status: "Resolved",
          created_at: "2026-03-30T12:00:00Z",
          sla_due_at: "2026-04-01T13:00:00Z",
          sla_policy_name: "Medium Review Window",
        },
      ],
      loading: false,
      error: null,
    });

    renderWithProviders(<AlertsPage />);

    await waitFor(() => {
      expect(screen.getByLabelText("SLA Violations")).toHaveTextContent(
        "2 overdue",
      );
    });
    expect(screen.getByText("Due 2026-04-01 10:30 UTC")).toBeInTheDocument();
    expect(screen.getByText("Overdue by 10h")).toBeInTheDocument();
    expect(screen.getByText("Resolved within SLA")).toBeInTheDocument();
  });

  it(
    "configures email and Slack alert subscriptions through the API-backed workspace settings",
    async () => {
    useAlertsMock.mockReturnValue({
      alerts: [],
      loading: false,
      error: null,
    });

    renderWithProviders(<AlertsPage />);

    expect(screen.getByText("No active subscriptions")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Subscriptions" }));

    expect(screen.getByText("Alert subscriptions")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText(/notification email/i), {
      target: { value: "pm@c2pro.test" },
    });
    fireEvent.change(screen.getByLabelText(/slack channel/i), {
      target: { value: "#project-alerts" },
    });
    fireEvent.click(screen.getByRole("button", { name: /enable email notifications/i }));
    fireEvent.click(screen.getByRole("button", { name: /enable slack notifications/i }));
    fireEvent.click(screen.getByRole("button", { name: /save subscriptions/i }));

    await waitFor(() => {
      expect(saveAlertWorkspaceSettingsMock).toHaveBeenCalledWith(
        expect.objectContaining({
          subscriptions: expect.objectContaining({
            emailEnabled: true,
            emailAddress: "pm@c2pro.test",
            slackEnabled: true,
            slackChannel: "#project-alerts",
          }),
        }),
      );
    });
    expect(screen.getByText("2 active subscriptions")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Subscriptions" }));

    expect(screen.getByDisplayValue("pm@c2pro.test")).toBeInTheDocument();
    expect(screen.getByDisplayValue("#project-alerts")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /disable email notifications/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /disable slack notifications/i }),
    ).toBeInTheDocument();
    },
    10000,
  );

  it("loads alert rules from the API and persists saved rule configuration through the API", async () => {
    useAlertsMock.mockReturnValue({
      alerts: [],
      loading: false,
      error: null,
    });
    getAlertWorkspaceSettingsMock.mockResolvedValue({
      rules: [
        {
          id: "schedule-drift",
          name: "Schedule Drift",
          description: "Flag delivery plans that move beyond the accepted response window.",
          enabled: false,
          threshold: 5,
          severity: "Critical",
        },
        {
          id: "budget-deviation",
          name: "Budget Deviation",
          description: "Raise an alert when committed cost exposure exceeds the allowed variance.",
          enabled: true,
          threshold: 10,
          severity: "High",
        },
        {
          id: "approval-gap",
          name: "Approval Gap",
          description: "Escalate missing ownership or sign-off on required workflow gates.",
          enabled: true,
          threshold: 3,
          severity: "Medium",
        },
      ],
      subscriptions: {
        emailEnabled: false,
        emailAddress: "",
        slackEnabled: false,
        slackChannel: "",
      },
    });

    renderWithProviders(<AlertsPage />);

    await waitFor(() => {
      expect(screen.getByText("2 active rules")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: "Alert Rules" }));

    expect(screen.getByText("Customize alert rules")).toBeInTheDocument();
    expect(screen.getByText("Schedule Drift")).toBeInTheDocument();
    expect(screen.getByDisplayValue("5")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /enable schedule drift/i }));
    fireEvent.change(screen.getByLabelText(/schedule drift threshold/i), {
      target: { value: "4" },
    });
    fireEvent.click(screen.getByRole("button", { name: /save rules/i }));

    await waitFor(() => {
      expect(saveAlertWorkspaceSettingsMock).toHaveBeenCalledWith(
        expect.objectContaining({
          rules: expect.arrayContaining([
            expect.objectContaining({
              id: "schedule-drift",
              enabled: true,
              threshold: 4,
            }),
          ]),
        }),
      );
    });
    expect(screen.getByText("3 active rules")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Alert Rules" }));

    expect(screen.getByRole("button", { name: /disable schedule drift/i })).toBeInTheDocument();
    expect(screen.getByDisplayValue("4")).toBeInTheDocument();
  });

  it("renders severity and status analytics summaries from alert data", () => {
    useAlertsMock.mockReturnValue({
      alerts: [
        {
          id: "a-1",
          severity: "Critical",
          type: "Schedule",
          title: "Date mismatch",
          description: "Contract and schedule diverge",
          project: "Hospital Central",
          status: "Open",
        },
        {
          id: "a-2",
          severity: "High",
          type: "Budget",
          title: "Budget overrun risk",
          description: "Procurement package exceeds forecast",
          project: "Hospital Central",
          status: "In Progress",
        },
        {
          id: "a-3",
          severity: "Medium",
          type: "Stakeholder",
          title: "Missing approval",
          description: "Owner missing for review gate",
          project: "Port Expansion",
          status: "Resolved",
        },
      ],
      loading: false,
      error: null,
    });

    renderWithProviders(<AlertsPage />);

    expect(screen.getByLabelText("Critical")).toHaveTextContent("1 active");
    expect(screen.getByLabelText("Open Alerts")).toHaveTextContent(
      "2 currently require action",
    );
    expect(screen.getByLabelText("Top Impacted Project")).toHaveTextContent(
      "Hospital Central",
    );
    expect(screen.getByLabelText("Top Impacted Project")).toHaveTextContent(
      "2 alerts in current scope",
    );
  });

  it("opens alert templates and previews the selected workflow", () => {
    useAlertsMock.mockReturnValue({
      alerts: [],
      loading: false,
      error: null,
    });

    renderWithProviders(<AlertsPage />);

    fireEvent.click(screen.getByRole("button", { name: "Alert Templates" }));

    expect(
      screen.getByText("Start from an alert response template"),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Executive Escalation/ }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Compliance Sweep/ }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /SLA Recovery/ }),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Compliance Sweep/ }));

    expect(
      screen.getByRole("heading", { name: "Compliance Sweep" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Prepare a cross-project compliance remediation review."),
    ).toBeInTheDocument();
    expect(screen.getByText("Coverage Audit")).toBeInTheDocument();
    expect(screen.getByText("Regulatory Log")).toBeInTheDocument();
  });

  it(
    "applies dynamic resolution validation rules based on alert severity",
    () => {
    useAlertsMock.mockReturnValue({
      alerts: [
        {
          id: "a-1",
          severity: "Critical",
          type: "Schedule",
          title: "Date mismatch",
          description: "Contract and schedule diverge",
          project: "Hospital Central",
          status: "Open",
        },
        {
          id: "a-2",
          severity: "Medium",
          type: "Budget",
          title: "Forecast drift",
          description: "Budget signal needs review",
          project: "Port Expansion",
          status: "Open",
        },
      ],
      loading: false,
      error: null,
    });

    renderWithProviders(<AlertsPage />);

    fireEvent.click(screen.getAllByRole("button", { name: /resolve alert/i })[0]);

    expect(screen.getByText("Resolve alert")).toBeInTheDocument();
    expect(screen.getByText(/critical alerts require detailed resolution notes/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/root cause/i)).toBeInTheDocument();
    expect(
      screen.getByLabelText(/i have reviewed the evidence and confirm this alert can be resolved/i),
    ).toBeInTheDocument();

    const confirmResolutionButton = screen.getByRole("button", {
      name: /confirm resolution/i,
    });
    expect(confirmResolutionButton).toBeDisabled();

    fireEvent.change(screen.getByLabelText(/resolution notes/i), {
      target: { value: "Too short" },
    });
    expect(confirmResolutionButton).toBeDisabled();

    fireEvent.change(screen.getByLabelText(/resolution notes/i), {
      target: {
        value:
          "Reviewed source evidence, aligned owners, and documented a complete mitigation path for the issue.",
      },
    });
    fireEvent.click(
      screen.getByLabelText(
        /i have reviewed the evidence and confirm this alert can be resolved/i,
      ),
    );
    fireEvent.click(screen.getByRole("combobox", { name: /root cause/i }));
    fireEvent.click(screen.getByRole("option", { name: /schedule delay/i }));

    expect(confirmResolutionButton).not.toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: /cancel/i }));

    fireEvent.click(screen.getAllByRole("button", { name: /resolve alert/i })[1]);

    expect(
      screen.queryByLabelText(/i have reviewed the evidence and confirm this alert can be resolved/i),
    ).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/root cause/i)).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(/resolution notes/i), {
      target: { value: "Validated with project owner." },
    });
    expect(
      screen.getByRole("button", { name: /confirm resolution/i }),
    ).not.toBeDisabled();
    },
    10000,
  );

  it("opens a lateral detail sheet for the selected alert", () => {
    useAlertsMock.mockReturnValue({
      alerts: [
        {
          id: "a-1",
          severity: "Critical",
          type: "Schedule",
          title: "Date mismatch",
          description: "Contract and schedule diverge",
          project: "Hospital Central",
          status: "Open",
          created_at: "2026-04-01T08:30:00Z",
        },
      ],
      loading: false,
      error: null,
    });

    renderWithProviders(<AlertsPage />);

    fireEvent.click(screen.getByRole("button", { name: /view alert a-1/i }));

    const detailDialog = screen.getByRole("dialog", { name: /alert details/i });

    expect(within(detailDialog).getByText("Date mismatch")).toBeInTheDocument();
    expect(
      within(detailDialog).getByText("Contract and schedule diverge"),
    ).toBeInTheDocument();
    expect(within(detailDialog).getByText("Hospital Central")).toBeInTheDocument();
    expect(within(detailDialog).getByText("Schedule")).toBeInTheDocument();
    expect(
      within(detailDialog).getByText(/created 2026-04-01 08:30 utc/i),
    ).toBeInTheDocument();
    expect(
      within(detailDialog).getByText(/severity critical/i),
    ).toBeInTheDocument();
    expect(within(detailDialog).getByText(/status open/i)).toBeInTheDocument();
  });

  it("supports bulk resolve actions through the backend batch endpoint", async () => {
    useAlertsMock.mockReturnValue({
      alerts: [
        {
          id: "a-1",
          severity: "High",
          type: "Schedule",
          title: "Date mismatch",
          description: "Contract and schedule diverge",
          project: "Hospital Central",
          status: "Open",
        },
        {
          id: "a-2",
          severity: "Medium",
          type: "Budget",
          title: "Forecast drift",
          description: "Budget signal needs review",
          project: "Port Expansion",
          status: "Open",
        },
      ],
      loading: false,
      error: null,
    });

    renderWithProviders(<AlertsPage />);

    fireEvent.click(screen.getByRole("checkbox", { name: /select alert a-1/i }));
    fireEvent.click(screen.getByRole("checkbox", { name: /select alert a-2/i }));

    expect(screen.getByText(/2 alerts selected/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /bulk resolve/i }));

    const bulkResolveDialog = screen.getByRole("dialog", {
      name: /bulk resolve alerts/i,
    });

    expect(
      within(bulkResolveDialog).getByText((_, element) =>
        element?.textContent === "2 selected alerts",
      ),
    ).toBeInTheDocument();
    expect(
      within(bulkResolveDialog).getByText(/highest severity in selection: high/i),
    ).toBeInTheDocument();

    const confirmResolutionButton = within(bulkResolveDialog).getByRole("button", {
      name: /confirm resolution/i,
    });
    expect(confirmResolutionButton).toBeDisabled();

    fireEvent.change(within(bulkResolveDialog).getByLabelText(/resolution notes/i), {
      target: {
        value:
          "Validated the impacted alerts, aligned remediation owners, and documented the grouped recovery actions.",
      },
    });
    fireEvent.click(
      within(bulkResolveDialog).getByLabelText(
        /i have reviewed the evidence and confirm this alert can be resolved/i,
      ),
    );
    fireEvent.click(within(bulkResolveDialog).getByRole("combobox", { name: /root cause/i }));
    fireEvent.click(screen.getByRole("option", { name: /schedule delay/i }));

    expect(confirmResolutionButton).not.toBeDisabled();
    fireEvent.click(confirmResolutionButton);

    await waitFor(() => {
      expect(bulkResolveAlertsMock).toHaveBeenCalledWith({
        alertIds: ["a-1", "a-2"],
        resolution: "Validated the impacted alerts, aligned remediation owners, and documented the grouped recovery actions.",
        rootCause: "schedule_delay",
      });
    });

    expect(screen.queryByText(/2 alerts selected/i)).not.toBeInTheDocument();
    expect(screen.getAllByText("Resolved").length).toBeGreaterThanOrEqual(2);
  });
});

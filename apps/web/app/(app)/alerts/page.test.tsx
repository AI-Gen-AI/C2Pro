/**
 * Test Suite ID: TASK-1258
 * Route Coverage: Alerts analytics dashboard
 */
import { describe, expect, it, vi } from "vitest";
import { fireEvent, renderWithProviders, screen } from "@/src/tests/test-utils";
import AlertsPage from "./page";

const useAlertsMock = vi.fn();

vi.mock("@/hooks/useAlerts", () => ({
  useAlerts: () => useAlertsMock(),
}));

describe("AlertsPage analytics dashboard", () => {
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
});

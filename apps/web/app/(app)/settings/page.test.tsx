/**
 * Test Suite ID: TASK-1347
 * Route Coverage: Settings page uses generated auth profile endpoints
 */
import { fireEvent, render, screen, waitFor } from "@/src/tests/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import SettingsPage from "./page";

const getMeMock = vi.fn();
const updateMeMutateAsyncMock = vi.fn();

vi.mock("@/lib/api/generated/authentication/authentication", () => ({
  useGetMeApiV1AuthMeGet: (...args: unknown[]) => getMeMock(...args),
  useUpdateMeApiV1AuthMePut: () => ({
    mutateAsync: (...args: unknown[]) => updateMeMutateAsyncMock(...args),
    isPending: false,
  }),
}));

vi.mock("@/components/ui/tabs", () => ({
  Tabs: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  TabsList: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  TabsTrigger: ({ children }: { children: React.ReactNode }) => <button type="button">{children}</button>,
  TabsContent: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

describe("SettingsPage", () => {
  beforeEach(() => {
    getMeMock.mockReset();
    updateMeMutateAsyncMock.mockReset();
  });

  it("loads the current user profile from the backend and saves profile updates", async () => {
    getMeMock.mockReturnValue({
      data: {
        user: {
          id: "user-1",
          email: "ana@example.com",
          first_name: "Ana",
          last_name: "Torres",
          full_name: "Ana Torres",
          avatar_url: null,
          phone: "+34 600 000 000",
          role: "manager",
          is_active: true,
          is_verified: true,
          is_admin: false,
          is_viewer: false,
          can_edit: true,
          can_manage_users: false,
          last_login: null,
          last_activity: null,
          login_count: 4,
          created_at: "2026-03-01T00:00:00Z",
          updated_at: "2026-03-10T00:00:00Z",
        },
        tenant: {
          id: "tenant-1",
          name: "Constructora Norte",
          slug: "constructora-norte",
          plan: "pro",
          is_active: true,
          created_at: "2026-03-01T00:00:00Z",
          updated_at: "2026-03-10T00:00:00Z",
        },
      },
      isLoading: false,
      error: null,
    });
    updateMeMutateAsyncMock.mockResolvedValue({
      first_name: "Ana Maria",
      last_name: "Torres",
    });

    render(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByDisplayValue("Ana")).toBeInTheDocument();
    });
    expect(screen.getByDisplayValue("Torres")).toBeInTheDocument();
    expect(screen.getByDisplayValue("ana@example.com")).toBeInTheDocument();
    expect(screen.getByDisplayValue("+34 600 000 000")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(/first name/i), {
      target: { value: "Ana Maria" },
    });
    fireEvent.click(screen.getByRole("button", { name: /save profile changes/i }));

    await waitFor(() => {
      expect(updateMeMutateAsyncMock).toHaveBeenCalledWith({
        data: {
          first_name: "Ana Maria",
          last_name: "Torres",
          phone: "+34 600 000 000",
          preferences: {
            email_notifications: true,
            critical_alerts: true,
            weekly_reports: false,
            language: "en",
            timezone: "utc",
            date_format: "mdy",
          },
        },
      });
    });
  });

  it("blocks profile save when the first name is blank after editing", async () => {
    getMeMock.mockReturnValue({
      data: {
        user: {
          email: "ana@example.com",
          first_name: "Ana",
          last_name: "Torres",
          phone: "+34 600 000 000",
          role: "manager",
        },
        tenant: {
          name: "Constructora Norte",
        },
      },
      isLoading: false,
      error: null,
    });

    render(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByDisplayValue("Ana")).toBeInTheDocument();
    });

    fireEvent.change(screen.getByLabelText(/first name/i), {
      target: { value: "" },
    });
    fireEvent.click(screen.getByRole("button", { name: /save profile changes/i }));

    expect(screen.getByText(/first name is required/i)).toBeInTheDocument();
    expect(updateMeMutateAsyncMock).not.toHaveBeenCalled();
  });

  it("blocks profile save when the phone number format is invalid", async () => {
    getMeMock.mockReturnValue({
      data: {
        user: {
          email: "ana@example.com",
          first_name: "Ana",
          last_name: "Torres",
          phone: "+34 600 000 000",
          role: "manager",
        },
        tenant: {
          name: "Constructora Norte",
        },
      },
      isLoading: false,
      error: null,
    });

    render(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByDisplayValue("+34 600 000 000")).toBeInTheDocument();
    });

    fireEvent.change(screen.getByLabelText(/phone/i), {
      target: { value: "abc" },
    });
    fireEvent.click(screen.getByRole("button", { name: /save profile changes/i }));

    expect(screen.getByText(/enter a valid phone number/i)).toBeInTheDocument();
    expect(updateMeMutateAsyncMock).not.toHaveBeenCalled();
  });
});

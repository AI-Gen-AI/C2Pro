/**
 * Test Suite ID: TASK-018
 * Form validation coverage for project creation flow.
 */
import { fireEvent, render, screen, waitFor } from "@/src/tests/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";

const pushMock = vi.fn();
const mutateAsyncMock = vi.fn();
const useCreateProjectMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: pushMock,
  }),
}));

vi.mock("next/link", () => ({
  default: ({
    children,
    href,
  }: {
    children: React.ReactNode;
    href: string;
  }) => <a href={href}>{children}</a>,
}));

vi.mock("@/lib/api/generated/projects/projects", () => ({
  useCreateProjectApiV1ProjectsPost: (...args: unknown[]) =>
    useCreateProjectMock(...args),
}));

import NewProjectPage from "./page";

describe("NewProjectPage", () => {
  beforeEach(() => {
    pushMock.mockReset();
    mutateAsyncMock.mockReset();
    useCreateProjectMock.mockReset();
    useCreateProjectMock.mockReturnValue({
      mutateAsync: (...args: unknown[]) => mutateAsyncMock(...args),
      isPending: false,
    });
  });

  it("renders the project creation form with the default currency", () => {
    render(<NewProjectPage />);

    expect(screen.getByRole("heading", { name: /create new project/i })).toBeInTheDocument();
    expect(screen.getByTestId("project-name-input")).toHaveValue("");
    expect(screen.getByTestId("project-code-input")).toHaveValue("");
    expect(screen.getByTestId("client-name-input")).toHaveValue("");
    expect(screen.getByTestId("project-description-input")).toHaveValue("");
    expect(screen.getByTestId("currency-select")).toHaveTextContent(/eur/i);
  });

  it("keeps the submit button disabled while the project name is blank", () => {
    render(<NewProjectPage />);

    expect(screen.getByTestId("create-project-button")).toBeDisabled();
  });

  it("keeps the submit button disabled when the project name is only whitespace", () => {
    render(<NewProjectPage />);

    fireEvent.change(screen.getByTestId("project-name-input"), {
      target: { value: "   " },
    });

    expect(screen.getByTestId("create-project-button")).toBeDisabled();
    expect(mutateAsyncMock).not.toHaveBeenCalled();
  });

  it("enables submit once the project name contains non-whitespace text", () => {
    render(<NewProjectPage />);

    fireEvent.change(screen.getByTestId("project-name-input"), {
      target: { value: "Alpha Tower" },
    });

    expect(screen.getByTestId("create-project-button")).toBeEnabled();
  });

  it("renders the back link to the projects list", () => {
    render(<NewProjectPage />);

    expect(screen.getByRole("link", { name: /back to projects/i })).toHaveAttribute(
      "href",
      "/projects",
    );
  });

  it("renders the cancel link to the projects list", () => {
    render(<NewProjectPage />);

    expect(screen.getByRole("link", { name: /^cancel$/i })).toHaveAttribute(
      "href",
      "/projects",
    );
  });

  it("shows helper copy explaining the optional project code", () => {
    render(<NewProjectPage />);

    expect(
      screen.getByText(/optional unique identifier for your project/i),
    ).toBeInTheDocument();
  });

  it("submits trimmed required data and omits optional empty fields", async () => {
    mutateAsyncMock.mockResolvedValueOnce({ id: "proj-100" });
    render(<NewProjectPage />);

    fireEvent.change(screen.getByTestId("project-name-input"), {
      target: { value: "  Alpha Tower  " },
    });

    fireEvent.click(screen.getByTestId("create-project-button"));

    await waitFor(() =>
      expect(mutateAsyncMock).toHaveBeenCalledWith({
        data: {
          name: "  Alpha Tower  ",
          code: undefined,
          description: undefined,
          client_name: undefined,
          currency: "EUR",
        },
      }),
    );
  });

  it("submits optional project fields when they are provided", async () => {
    mutateAsyncMock.mockResolvedValueOnce({ id: "proj-101" });
    render(<NewProjectPage />);

    fireEvent.change(screen.getByTestId("project-name-input"), {
      target: { value: "Alpha Tower" },
    });
    fireEvent.change(screen.getByTestId("project-code-input"), {
      target: { value: "ALT-001" },
    });
    fireEvent.change(screen.getByTestId("client-name-input"), {
      target: { value: "Client Corp" },
    });
    fireEvent.change(screen.getByTestId("project-description-input"), {
      target: { value: "Phase one scope" },
    });

    fireEvent.click(screen.getByTestId("create-project-button"));

    await waitFor(() =>
      expect(mutateAsyncMock).toHaveBeenCalledWith({
        data: {
          name: "Alpha Tower",
          code: "ALT-001",
          description: "Phase one scope",
          client_name: "Client Corp",
          currency: "EUR",
        },
      }),
    );
  });

  it("changes the selected currency and submits it in the payload", async () => {
    mutateAsyncMock.mockResolvedValueOnce({ id: "proj-101b" });
    render(<NewProjectPage />);

    fireEvent.change(screen.getByTestId("project-name-input"), {
      target: { value: "Alpha Tower" },
    });
    fireEvent.click(screen.getByRole("combobox"));
    fireEvent.click(await screen.findByText("USD ($)"));
    fireEvent.click(screen.getByTestId("create-project-button"));

    await waitFor(() =>
      expect(mutateAsyncMock).toHaveBeenCalledWith({
        data: {
          name: "Alpha Tower",
          code: undefined,
          description: undefined,
          client_name: undefined,
          currency: "USD",
        },
      }),
    );
  });

  it("shows a loading state while the create request is in flight", async () => {
    let resolveRequest: ((value: unknown) => void) | undefined;
    mutateAsyncMock.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          resolveRequest = resolve;
        }),
    );
    render(<NewProjectPage />);

    fireEvent.change(screen.getByTestId("project-name-input"), {
      target: { value: "Alpha Tower" },
    });
    fireEvent.click(screen.getByTestId("create-project-button"));

    expect(screen.getByText(/creating\.\.\./i)).toBeInTheDocument();
    expect(screen.getByTestId("create-project-button")).toBeDisabled();

    resolveRequest?.({ id: "proj-102" });

    await waitFor(() =>
      expect(pushMock).toHaveBeenCalledWith("/projects/proj-102/documents"),
    );
  });

  it("does not navigate when the create request fails", async () => {
    mutateAsyncMock.mockRejectedValueOnce(new Error("Network unreachable"));
    render(<NewProjectPage />);

    fireEvent.change(screen.getByTestId("project-name-input"), {
      target: { value: "Alpha Tower" },
    });
    fireEvent.click(screen.getByTestId("create-project-button"));

    await waitFor(() =>
      expect(screen.getByText(/network unreachable/i)).toBeInTheDocument(),
    );
    expect(pushMock).not.toHaveBeenCalled();
  });

  it("redirects to the new project's documents page after success", async () => {
    mutateAsyncMock.mockResolvedValueOnce({ id: "proj-103" });
    render(<NewProjectPage />);

    fireEvent.change(screen.getByTestId("project-name-input"), {
      target: { value: "Alpha Tower" },
    });
    fireEvent.click(screen.getByTestId("create-project-button"));

    await waitFor(() =>
      expect(pushMock).toHaveBeenCalledWith("/projects/proj-103/documents"),
    );
  });

  it("surfaces backend detail messages on create failure", async () => {
    mutateAsyncMock.mockRejectedValueOnce({
      response: { data: { detail: "Project code already exists" } },
    });
    render(<NewProjectPage />);

    fireEvent.change(screen.getByTestId("project-name-input"), {
      target: { value: "Alpha Tower" },
    });
    fireEvent.click(screen.getByTestId("create-project-button"));

    await waitFor(() =>
      expect(screen.getByText(/project code already exists/i)).toBeInTheDocument(),
    );
  });

  it("falls back to error.message when backend detail is unavailable", async () => {
    mutateAsyncMock.mockRejectedValueOnce(new Error("Network unreachable"));
    render(<NewProjectPage />);

    fireEvent.change(screen.getByTestId("project-name-input"), {
      target: { value: "Alpha Tower" },
    });
    fireEvent.click(screen.getByTestId("create-project-button"));

    await waitFor(() =>
      expect(screen.getByText(/network unreachable/i)).toBeInTheDocument(),
    );
  });

  it("falls back to a stable generic error when the failure payload is opaque", async () => {
    mutateAsyncMock.mockRejectedValueOnce({});
    render(<NewProjectPage />);

    fireEvent.change(screen.getByTestId("project-name-input"), {
      target: { value: "Alpha Tower" },
    });
    fireEvent.click(screen.getByTestId("create-project-button"));

    await waitFor(() =>
      expect(screen.getByText(/failed to create project/i)).toBeInTheDocument(),
    );
  });

  it("re-enables the create button after a failed request", async () => {
    mutateAsyncMock.mockRejectedValueOnce(new Error("Network unreachable"));
    render(<NewProjectPage />);

    fireEvent.change(screen.getByTestId("project-name-input"), {
      target: { value: "Alpha Tower" },
    });
    fireEvent.click(screen.getByTestId("create-project-button"));

    await waitFor(() =>
      expect(screen.getByText(/network unreachable/i)).toBeInTheDocument(),
    );

    expect(screen.getByTestId("create-project-button")).toBeEnabled();
  });

  it("clears a previous backend error when a retry starts", async () => {
    let resolveRequest: ((value: unknown) => void) | undefined;
    mutateAsyncMock
      .mockRejectedValueOnce(new Error("Network unreachable"))
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            resolveRequest = resolve;
          }),
      );
    render(<NewProjectPage />);

    fireEvent.change(screen.getByTestId("project-name-input"), {
      target: { value: "Recovered Project" },
    });
    fireEvent.click(screen.getByTestId("create-project-button"));

    await waitFor(() =>
      expect(screen.getByText(/network unreachable/i)).toBeInTheDocument(),
    );

    fireEvent.click(screen.getByTestId("create-project-button"));

    await waitFor(() =>
      expect(screen.queryByText(/network unreachable/i)).not.toBeInTheDocument(),
    );

    resolveRequest?.({ id: "proj-104" });
    await waitFor(() =>
      expect(pushMock).toHaveBeenCalledWith("/projects/proj-104/documents"),
    );
  });

  it("keeps helper guidance about post-create document upload visible", () => {
    render(<NewProjectPage />);

    expect(
      screen.getByText(/after creating the project, you'll be redirected to upload documents\./i),
    ).toBeInTheDocument();
  });

  it("preserves entered field values after a failed create attempt", async () => {
    mutateAsyncMock.mockRejectedValueOnce(new Error("Network unreachable"));
    render(<NewProjectPage />);

    fireEvent.change(screen.getByTestId("project-name-input"), {
      target: { value: "Alpha Tower" },
    });
    fireEvent.change(screen.getByTestId("project-code-input"), {
      target: { value: "ALT-200" },
    });
    fireEvent.change(screen.getByTestId("client-name-input"), {
      target: { value: "Client Corp" },
    });
    fireEvent.click(screen.getByTestId("create-project-button"));

    await waitFor(() =>
      expect(screen.getByText(/network unreachable/i)).toBeInTheDocument(),
    );

    expect(screen.getByTestId("project-name-input")).toHaveValue("Alpha Tower");
    expect(screen.getByTestId("project-code-input")).toHaveValue("ALT-200");
    expect(screen.getByTestId("client-name-input")).toHaveValue("Client Corp");
  });
});

/**
 * Test Suite ID: TASK-FRT-175
 * Integration coverage for staged, typed document upload.
 */
import { fireEvent, render, screen, waitFor } from "@/src/tests/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DocumentUploadDropzone } from "@/components/features/documents/DocumentUploadDropzone";

const uploadDocumentMock = vi.fn();
const getTokenMock = vi.fn();

vi.mock("@/lib/api", () => ({
  uploadDocument: (...args: unknown[]) => uploadDocumentMock(...args),
}));

vi.mock("@clerk/nextjs", () => ({
  useAuth: () => ({
    getToken: getTokenMock,
  }),
}));

function createFile(name: string, type: string): File {
  return new File(["file"], name, { type });
}

describe("TASK-FRT-175 staged upload integration", () => {
  afterEach(() => {
    uploadDocumentMock.mockReset();
    getTokenMock.mockReset();
  });

  it("lets one dialog session upload contract, budget, and schedule with real document types", async () => {
    uploadDocumentMock.mockResolvedValue({ id: "doc-1", task_id: "task-1" });
    getTokenMock.mockResolvedValue("fresh-token-123");

    render(<DocumentUploadDropzone projectId="proj-triplet" />);

    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, {
      target: {
        files: [
          createFile("contract.pdf", "application/pdf"),
          createFile("budget.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
          createFile("schedule.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        ],
      },
    });

    fireEvent.click(await screen.findByLabelText(/document type for schedule\.xlsx/i));
    fireEvent.click(await screen.findByRole("option", { name: "Schedule" }));
    fireEvent.click(screen.getByRole("button", { name: /upload 3 files/i }));

    await waitFor(() => expect(uploadDocumentMock).toHaveBeenCalledTimes(3));
    expect(uploadDocumentMock.mock.calls.map((call) => call[2])).toEqual([
      "contract",
      "budget",
      "schedule",
    ]);
  });
});

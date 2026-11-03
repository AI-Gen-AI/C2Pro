import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@/src/tests/test-utils";
import {
  deriveTripletChecklist,
  TripletChecklist,
} from "@/components/features/documents/TripletChecklist";
import type { DocumentInfo } from "@/types/document";

function doc(
  type: DocumentInfo["type"],
  status: DocumentInfo["status"],
  lifecycleStatus?: DocumentInfo["lifecycleStatus"],
): DocumentInfo {
  return {
    id: `${type}-${status}`,
    name: `${type}.${type === "budget" ? "xlsx" : "pdf"}`,
    type,
    extension: type === "budget" ? "xlsx" : "pdf",
    url: "",
    status,
    lifecycleStatus,
  };
}

describe("TripletChecklist", () => {
  it("derives missing, processing, and ready states for the required triplet", () => {
    const result = deriveTripletChecklist([
      doc("contract", "parsed"),
      doc("budget", "processing"),
      doc("other", "parsed"),
    ]);

    expect(result.slots).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ type: "contract", state: "ready" }),
        expect.objectContaining({ type: "budget", state: "processing" }),
        expect.objectContaining({ type: "schedule", state: "missing" }),
      ]),
    );
    expect(result.complete).toBe(false);
  });

  it("tells a document awaiting a human decision apart from one still processing and from a missing one", () => {
    const result = deriveTripletChecklist([
      doc("contract", "processing", "review_required"),
      doc("budget", "processing"),
    ]);

    expect(result.slots).toEqual([
      expect.objectContaining({ type: "contract", state: "awaiting_approval" }),
      expect.objectContaining({ type: "budget", state: "processing" }),
      expect.objectContaining({ type: "schedule", state: "missing" }),
    ]);
    expect(result.complete).toBe(false);
  });

  it("a ready document wins over another revision of the same type that awaits approval", () => {
    const result = deriveTripletChecklist([
      doc("contract", "processing", "review_required"),
      { ...doc("contract", "parsed", "analyzed"), id: "contract-older" },
    ]);

    expect(result.slots[0]).toEqual(expect.objectContaining({ type: "contract", state: "ready" }));
  });

  it("says in plain words that the contract awaits approval and that nothing is evaluated", () => {
    render(<TripletChecklist documents={[doc("contract", "processing", "review_required")]} />);

    expect(screen.getByText("Awaiting approval")).toBeInTheDocument();
    const notice = screen.getByTestId("triplet-awaiting-approval");
    expect(notice).toHaveTextContent(/contract is awaiting approval/i);
    expect(notice).toHaveTextContent(/no score is produced/i);
    expect(screen.queryByText(/not found/i)).not.toBeInTheDocument();
  });

  it("shows no awaiting-approval notice for a project without documents", () => {
    render(<TripletChecklist documents={[]} />);

    expect(screen.queryByTestId("triplet-awaiting-approval")).not.toBeInTheDocument();
    expect(screen.queryByText("Awaiting approval")).not.toBeInTheDocument();
    expect(screen.getAllByText("Missing")).toHaveLength(3);
  });

  it("explains the awaiting-approval state in the compact checklist too", () => {
    render(<TripletChecklist documents={[doc("contract", "processing", "review_required")]} compact />);

    expect(screen.getByText(/contract awaiting approval/i)).toBeInTheDocument();
    expect(screen.getByTestId("triplet-awaiting-approval")).toBeInTheDocument();
  });

  it("renders per-slot upload CTAs for missing documents", () => {
    const onUploadType = vi.fn();

    render(
      <TripletChecklist
        documents={[doc("contract", "parsed")]}
        onUploadType={onUploadType}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /upload budget/i }));

    expect(screen.getByText("Contract")).toBeInTheDocument();
    expect(screen.getByText("Ready")).toBeInTheDocument();
    expect(screen.getByText("Schedule")).toBeInTheDocument();
    expect(screen.getAllByText("Missing")).toHaveLength(2);
    expect(onUploadType).toHaveBeenCalledWith("budget");
  });

  it("collapses into the success row when the triplet is complete", () => {
    render(
      <TripletChecklist
        documents={[
          doc("contract", "parsed"),
          doc("budget", "analyzed" as DocumentInfo["status"]),
          doc("schedule", "parsed"),
        ]}
        coherenceHref="/projects/proj-1/coherence"
      />,
    );

    expect(
      screen.getByText(/triplet complete — run the coherence audit/i),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /open coherence/i })).toHaveAttribute(
      "href",
      "/projects/proj-1/coherence",
    );
    expect(screen.queryByText("Missing")).not.toBeInTheDocument();
  });
});

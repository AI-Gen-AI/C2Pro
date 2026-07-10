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
): DocumentInfo {
  return {
    id: `${type}-${status}`,
    name: `${type}.${type === "budget" ? "xlsx" : "pdf"}`,
    type,
    extension: type === "budget" ? "xlsx" : "pdf",
    url: "",
    status,
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

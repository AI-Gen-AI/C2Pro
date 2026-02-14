import { describe, expect, it } from "vitest";
import { useProcessingStore } from "./processing";

describe("processing store", () => {
  it("clears a project job", () => {
    const { update, clear } = useProcessingStore.getState();

    update("proj_demo_003", { stage: 1, name: "Extracting", progress: 10 });
    clear("proj_demo_003");

    const { activeJobs } = useProcessingStore.getState();
    expect(activeJobs["proj_demo_003"]).toBeUndefined();
  });

  it("updates processing stages per project", () => {
    const { update } = useProcessingStore.getState();

    update("proj_demo_001", { stage: 1, name: "Extracting", progress: 10 });

    const { activeJobs } = useProcessingStore.getState();
    const job = activeJobs["proj_demo_001"];
    expect(job?.projectId).toBe("proj_demo_001");
    expect(job?.stages).toHaveLength(1);
    expect(job?.stages[0]?.progress).toBe(10);
  });

  it("marks a job as complete when the complete stage arrives", () => {
    const { update } = useProcessingStore.getState();

    update("proj_demo_002", { stage: 1, name: "Extracting", progress: 10 });
    update("proj_demo_002", { complete: true, score: 78 });

    const { activeJobs } = useProcessingStore.getState();
    const job = activeJobs["proj_demo_002"];
    expect(job?.complete).toBe(true);
    expect(job?.score).toBe(78);
  });
});

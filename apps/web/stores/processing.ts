import { create } from "zustand";
import { devtools } from "zustand/middleware";

export interface ProcessingStage {
  stage?: number;
  name?: string;
  progress?: number;
  complete?: boolean;
  score?: number;
}

export interface ProcessingJob {
  projectId: string;
  stages: ProcessingStage[];
  complete: boolean;
  score?: number;
  updatedAt: number;
}

interface ProcessingState {
  activeJobs: Record<string, ProcessingJob>;
  update: (projectId: string, stage: ProcessingStage) => void;
  clear: (projectId: string) => void;
}

export const useProcessingStore = create<ProcessingState>()(
  devtools(
    (set) => ({
      activeJobs: {},
      update: (projectId, stage) =>
        set((state) => {
          const existing = state.activeJobs[projectId];
          const stages = existing ? [...existing.stages, stage] : [stage];
          const complete = existing?.complete ?? false;
          const score =
            typeof stage.score === "number" ? stage.score : existing?.score;

          return {
            activeJobs: {
              ...state.activeJobs,
              [projectId]: {
                projectId,
                stages,
                complete: stage.complete ? true : complete,
                score,
                updatedAt: Date.now(),
              },
            },
          };
        }),
      clear: (projectId) =>
        set((state) => {
          const next = { ...state.activeJobs };
          delete next[projectId];
          return { activeJobs: next };
        }),
    }),
    { name: "c2pro-processing" },
  ),
);

import { create } from "zustand";
import { devtools } from "zustand/middleware";

type AppMode = "demo" | "prod";

interface AppModeState {
  mode: AppMode;
  setMode: (mode: AppMode) => void;
}

const defaultMode: AppMode =
  process.env.NEXT_PUBLIC_APP_MODE === "demo" ? "demo" : "prod";

export const useAppModeStore = create<AppModeState>()(
  devtools(
    (set) => ({
      mode: defaultMode,
      setMode: (mode) => set({ mode }),
    }),
    { name: "c2pro-app-mode" },
  ),
);

import { create } from "zustand";
import { devtools } from "zustand/middleware";

type AppMode = "demo" | "prod";

interface AppModeState {
  mode: AppMode;
  demoEnvironmentEnabled: boolean;
  setMode: (mode: AppMode) => void;
  syncWithPathname: (pathname: string | null) => void;
}

const demoEnvironmentEnabled = process.env.NEXT_PUBLIC_APP_MODE === "demo";

export function isExplicitDemoRoute(pathname: string | null | undefined): boolean {
  return pathname === "/demo" || pathname?.startsWith("/demo/") === true;
}

export const useAppModeStore = create<AppModeState>()(
  devtools(
    (set) => ({
      mode: "prod",
      demoEnvironmentEnabled,
      setMode: (mode) => set({ mode }),
      syncWithPathname: (pathname) =>
        set({
          mode:
            demoEnvironmentEnabled && isExplicitDemoRoute(pathname)
              ? "demo"
              : "prod",
        }),
    }),
    { name: "c2pro-app-mode" },
  ),
);

/** Convenience selector — avoids `mode === "demo"` scattered everywhere. */
export const selectIsDemoMode = (state: AppModeState) =>
  state.mode === "demo";

import { create } from "zustand";
import { devtools } from "zustand/middleware";

interface SidebarState {
  isCollapsed: boolean;
  width: number;
  toggle: () => void;
  setCollapsed: (collapsed: boolean) => void;
  setWidth: (width: number) => void;
}

export const useSidebarStore = create<SidebarState>()(
  devtools(
    (set) => ({
      isCollapsed: false,
      width: 240,
      toggle: () => set((state) => ({ isCollapsed: !state.isCollapsed })),
      setCollapsed: (collapsed) => set({ isCollapsed: collapsed }),
      setWidth: (width) => set({ width }),
    }),
    { name: "c2pro-sidebar" },
  ),
);

import { create } from "zustand";
import { devtools } from "zustand/middleware";

export type AlertSeverity = "critical" | "high" | "medium" | "low";

interface FilterState {
  severities: AlertSeverity[];
  categories: string[];
  search: string;
  toggleSeverity: (severity: AlertSeverity) => void;
  toggleCategory: (category: string) => void;
  setSearch: (search: string) => void;
  clear: () => void;
}

export const useFilterStore = create<FilterState>()(
  devtools(
    (set) => ({
      severities: [],
      categories: [],
      search: "",
      toggleSeverity: (severity) =>
        set((state) => ({
          severities: state.severities.includes(severity)
            ? state.severities.filter((item) => item !== severity)
            : [...state.severities, severity],
        })),
      toggleCategory: (category) =>
        set((state) => ({
          categories: state.categories.includes(category)
            ? state.categories.filter((item) => item !== category)
            : [...state.categories, category],
        })),
      setSearch: (search) => set({ search }),
      clear: () => set({ severities: [], categories: [], search: "" }),
    }),
    { name: "c2pro-filters" },
  ),
);

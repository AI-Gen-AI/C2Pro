import { beforeEach, describe, expect, it } from "vitest";
import { useFilterStore } from "./filters";

describe("useFilterStore", () => {
  beforeEach(() => {
    useFilterStore.getState().clear();
  });

  it("toggles severities and categories", () => {
    useFilterStore.getState().toggleSeverity("critical");
    useFilterStore.getState().toggleSeverity("high");
    expect(useFilterStore.getState().severities).toEqual([
      "critical",
      "high",
    ]);

    useFilterStore.getState().toggleSeverity("critical");
    expect(useFilterStore.getState().severities).toEqual(["high"]);

    useFilterStore.getState().toggleCategory("legal");
    expect(useFilterStore.getState().categories).toEqual(["legal"]);
  });

  it("updates search and clears filters", () => {
    useFilterStore.getState().setSearch("contract");
    useFilterStore.getState().toggleSeverity("low");

    expect(useFilterStore.getState().search).toBe("contract");
    expect(useFilterStore.getState().severities).toEqual(["low"]);

    useFilterStore.getState().clear();
    const state = useFilterStore.getState();
    expect(state.search).toBe("");
    expect(state.severities).toEqual([]);
    expect(state.categories).toEqual([]);
  });
});

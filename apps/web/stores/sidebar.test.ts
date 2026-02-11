import { describe, expect, it } from "vitest";
import { useSidebarStore } from "./sidebar";

describe("useSidebarStore", () => {
  it("toggles collapsed state", () => {
    useSidebarStore.setState({ isCollapsed: false, width: 240 });

    useSidebarStore.getState().toggle();
    expect(useSidebarStore.getState().isCollapsed).toBe(true);

    useSidebarStore.getState().toggle();
    expect(useSidebarStore.getState().isCollapsed).toBe(false);
  });

  it("updates width", () => {
    useSidebarStore.setState({ isCollapsed: false, width: 240 });

    useSidebarStore.getState().setWidth(200);
    expect(useSidebarStore.getState().width).toBe(200);
  });
});

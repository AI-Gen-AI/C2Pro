import { describe, expect, it, vi, afterEach } from "vitest";
import { renderWithProviders, screen, waitFor } from "@/src/tests/test-utils";
import { useCountUp } from "./useCountUp";

function CountUpProbe({ target, duration }: { target: number; duration?: number }) {
  const value = useCountUp(target, duration);
  return <span>{value}</span>;
}

describe("useCountUp", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("counts up to the target value", async () => {
    vi.spyOn(global, "requestAnimationFrame").mockImplementation((cb) => {
      cb(performance.now() + 1500);
      return 1;
    });
    vi.spyOn(global, "cancelAnimationFrame").mockImplementation(() => {});

    renderWithProviders(<CountUpProbe target={100} duration={1500} />);

    await waitFor(() => {
      expect(screen.getByText("100")).toBeInTheDocument();
    });
  });
});

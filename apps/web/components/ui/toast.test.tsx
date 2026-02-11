import { describe, expect, it } from "vitest";
import { renderWithProviders, screen } from "@/src/tests/test-utils";
import { Toast, ToastDescription, ToastTitle } from "./toast";

describe("Toast", () => {
  it("renders title and description", () => {
    renderWithProviders(
      <Toast>
        <ToastTitle>Saved</ToastTitle>
        <ToastDescription>Changes applied</ToastDescription>
      </Toast>,
    );

    expect(screen.getByText("Saved")).toBeInTheDocument();
    expect(screen.getByText("Changes applied")).toBeInTheDocument();
  });
});

import { describe, expect, it } from "vitest";
import { renderWithProviders, screen } from "@/src/tests/test-utils";
import { Toast, ToastDescription, ToastProvider, ToastTitle, ToastViewport } from "./toast";

describe("Toast", () => {
  it("renders title and description", () => {
    renderWithProviders(
      <ToastProvider>
        <Toast>
          <ToastTitle>Saved</ToastTitle>
          <ToastDescription>Changes applied</ToastDescription>
        </Toast>
        <ToastViewport />
      </ToastProvider>,
    );

    expect(screen.getByText("Saved")).toBeInTheDocument();
    expect(screen.getByText("Changes applied")).toBeInTheDocument();
  });
});

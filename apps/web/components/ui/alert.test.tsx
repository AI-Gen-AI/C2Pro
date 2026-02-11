import { describe, expect, it } from "vitest";
import { renderWithProviders, screen } from "@/src/tests/test-utils";
import { Alert, AlertDescription, AlertTitle } from "./alert";

describe("Alert", () => {
  it("renders alert title and description", () => {
    renderWithProviders(
      <Alert>
        <AlertTitle>Heads up</AlertTitle>
        <AlertDescription>Check your settings</AlertDescription>
      </Alert>,
    );

    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(screen.getByText("Heads up")).toBeInTheDocument();
    expect(screen.getByText("Check your settings")).toBeInTheDocument();
  });
});

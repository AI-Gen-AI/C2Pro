import { describe, expect, it } from "vitest";
import userEvent from "@testing-library/user-event";
import { renderWithProviders, screen } from "@/src/tests/test-utils";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "./alert-dialog";

describe("AlertDialog", () => {
  it("opens and shows confirm/cancel actions", async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <AlertDialog>
        <AlertDialogTrigger asChild>
          <button type="button">Delete</button>
        </AlertDialogTrigger>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Confirm</AlertDialogTitle>
            <AlertDialogDescription>Are you sure?</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogAction>Confirm</AlertDialogAction>
        </AlertDialogContent>
      </AlertDialog>,
    );

    await user.click(screen.getByRole("button", { name: /delete/i }));
    expect(screen.getByRole("alertdialog")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /cancel/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /confirm/i })).toBeInTheDocument();
  });
});

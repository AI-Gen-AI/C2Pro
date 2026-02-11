import { describe, expect, it } from "vitest";
import userEvent from "@testing-library/user-event";
import { renderWithProviders, screen } from "@/src/tests/test-utils";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "./accordion";

describe("Accordion", () => {
  it("expands content when trigger is clicked", async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <Accordion type="single" collapsible>
        <AccordionItem value="item-1">
          <AccordionTrigger>Overview</AccordionTrigger>
          <AccordionContent>Details</AccordionContent>
        </AccordionItem>
      </Accordion>,
    );

    await user.click(screen.getByRole("button", { name: /overview/i }));
    expect(screen.getByText("Details")).toBeInTheDocument();
  });
});

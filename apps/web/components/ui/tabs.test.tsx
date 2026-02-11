import { describe, expect, it } from "vitest";
import userEvent from "@testing-library/user-event";
import { renderWithProviders, screen } from "@/src/tests/test-utils";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "./tabs";

describe("Tabs", () => {
  it("switches active tab content", async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <Tabs defaultValue="details">
        <TabsList>
          <TabsTrigger value="details">Details</TabsTrigger>
          <TabsTrigger value="activity">Activity</TabsTrigger>
        </TabsList>
        <TabsContent value="details">Details content</TabsContent>
        <TabsContent value="activity">Activity content</TabsContent>
      </Tabs>,
    );

    expect(screen.getByText("Details content")).toBeInTheDocument();

    await user.click(screen.getByRole("tab", { name: /activity/i }));
    expect(screen.getByText("Activity content")).toBeInTheDocument();
  });
});

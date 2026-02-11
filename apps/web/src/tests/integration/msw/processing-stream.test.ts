import { describe, expect, it } from "vitest";

type ParsedSseEvent = {
  event: string;
  data: Record<string, unknown>;
};

function parseSsePayload(payload: string): ParsedSseEvent[] {
  const blocks = payload
    .split("\n\n")
    .map((block) => block.trim())
    .filter(Boolean);

  return blocks.map((block) => {
    const eventLine = block
      .split("\n")
      .find((line) => line.startsWith("event:"));
    const dataLine = block.split("\n").find((line) => line.startsWith("data:"));

    return {
      event: eventLine?.replace("event:", "").trim() ?? "",
      data: JSON.parse(dataLine?.replace("data:", "").trim() ?? "{}"),
    };
  });
}

describe("MSW processing stream integration", () => {
  it("streams all expected processing events", async () => {
    const response = await fetch("/api/v1/projects/proj-123/process/stream");
    const payload = await response.text();
    const events = parseSsePayload(payload);

    expect(response.ok).toBe(true);
    expect(events).toHaveLength(6);
    expect(events.map((event) => event.event)).toEqual([
      "stage",
      "stage",
      "stage",
      "stage",
      "stage",
      "complete",
    ]);
  });

  it("finishes with the expected global coherence score", async () => {
    const response = await fetch("/api/v1/projects/proj-456/process/stream");
    const payload = await response.text();
    const events = parseSsePayload(payload);
    const completeEvent = events.find((event) => event.event === "complete");

    expect(response.ok).toBe(true);
    expect(completeEvent).toBeDefined();
    expect(completeEvent?.data).toMatchObject({
      global_score: 78,
      documents_analyzed: 8,
    });
  });
});

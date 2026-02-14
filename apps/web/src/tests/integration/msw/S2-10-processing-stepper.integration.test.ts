/**
 * Test Suite ID: S2-10
 * Roadmap Reference: S2-10 SSE processing stepper + withCredentials (FLAG-3)
 */
import { describe, expect, it } from "vitest";

type StreamEvent = {
  event: string;
  data: Record<string, unknown>;
};

async function readSseEvents(response: Response): Promise<StreamEvent[]> {
  const reader = response.body?.getReader();
  if (!reader) return [];

  const decoder = new TextDecoder();
  let buffer = "";
  const events: StreamEvent[] = [];

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });

    let separatorIndex = buffer.indexOf("\n\n");
    while (separatorIndex !== -1) {
      const frame = buffer.slice(0, separatorIndex);
      buffer = buffer.slice(separatorIndex + 2);

      const eventLine = frame
        .split("\n")
        .find((line) => line.startsWith("event:"));
      const dataLine = frame.split("\n").find((line) => line.startsWith("data:"));
      events.push({
        event: eventLine?.replace("event:", "").trim() ?? "",
        data: JSON.parse(dataLine?.replace("data:", "").trim() ?? "{}"),
      });

      separatorIndex = buffer.indexOf("\n\n");
    }
  }

  return events;
}

describe("S2-10 RED - SSE processing integration (MSW)", () => {
  it("[S2-10-RED-04] reconstructs ordered events from chunked SSE payload boundaries", async () => {
    const response = await fetch(
      "/api/v1/projects/proj_demo_001/process/stream?chunked=1",
    );
    const events = await readSseEvents(response);

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
    expect(events.map((event) => event.data.stage).filter(Boolean)).toEqual([
      1, 2, 3, 4, 5,
    ]);
  });

  it("[S2-10-RED-05] returns deterministic auth error when credentials are missing", async () => {
    const response = await fetch("/api/v1/projects/proj_demo_001/process/stream", {
      method: "GET",
      credentials: "omit",
    });

    expect([401, 403]).toContain(response.status);
    await expect(response.json()).resolves.toMatchObject({
      code: "UNAUTHORIZED_STREAM",
      detail: "Authenticated SSE session required",
    });
  });

  it("[S2-10-RED-06] enters retry/error path on interruption and never marks completion", async () => {
    const response = await fetch(
      "/api/v1/projects/proj_demo_001/process/stream?interrupt=1",
    );
    const events = await readSseEvents(response);

    expect(response.ok).toBe(true);
    expect(events.some((event) => event.event === "error")).toBe(true);
    expect(events.some((event) => event.event === "complete")).toBe(false);
  });
});

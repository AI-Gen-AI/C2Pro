/**
 * Test Suite ID: S2-10
 * Roadmap Reference: S2-10 SSE processing stepper + withCredentials (FLAG-3)
 */
import { http, HttpResponse } from "msw";

export const processingStreamHandler = http.get(
  "/api/v1/projects/:projectId/process/stream",
  ({ request }) => {
    const url = new URL(request.url);
    const isChunked = url.searchParams.get("chunked") === "1";
    const isInterrupted = url.searchParams.get("interrupt") === "1";

    if (request.credentials === "omit") {
      return HttpResponse.json(
        {
          code: "UNAUTHORIZED_STREAM",
          detail: "Authenticated SSE session required",
        },
        { status: 401 },
      );
    }

    const encoder = new TextEncoder();
    const stream = new ReadableStream({
      async start(controller) {
        const stages = [
          { event: "stage", data: { name: "Extracting text", progress: 16, stage: 1 } },
          { event: "stage", data: { name: "Identifying clauses", progress: 33, stage: 2 } },
          { event: "stage", data: { name: "Cross-referencing", progress: 50, stage: 3 } },
          { event: "stage", data: { name: "Detecting anomalies", progress: 66, stage: 4 } },
          { event: "stage", data: { name: "Calculating weights", progress: 83, stage: 5 } },
          { event: "complete", data: { global_score: 78, documents_analyzed: 8 } },
        ];

        const streamStages = isInterrupted
          ? stages.filter((entry) => entry.event !== "complete").slice(0, 3)
          : stages;

        for (const s of streamStages) {
          await new Promise((r) => setTimeout(r, 50));
          const frame = `event: ${s.event}\ndata: ${JSON.stringify(s.data)}\n\n`;

          if (isChunked) {
            const splitAt = Math.floor(frame.length / 2);
            controller.enqueue(encoder.encode(frame.slice(0, splitAt)));
            await new Promise((r) => setTimeout(r, 10));
            controller.enqueue(encoder.encode(frame.slice(splitAt)));
            continue;
          }

          controller.enqueue(encoder.encode(frame));
        }

        if (isInterrupted) {
          controller.enqueue(
            encoder.encode(
              `event: error\ndata: ${JSON.stringify({
                code: "STREAM_INTERRUPTED",
                retryable: true,
              })}\n\n`,
            ),
          );
        }
        controller.close();
      },
    });

    return new HttpResponse(stream, {
      headers: {
        "Content-Type": "text/event-stream",
        Connection: "keep-alive",
        "Cache-Control": "no-cache",
      },
    });
  },
);

import { http, HttpResponse } from "msw";

export const processingStreamHandler = http.get(
  "/api/v1/projects/:projectId/process/stream",
  () => {
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

        for (const s of stages) {
          await new Promise((r) => setTimeout(r, 50));
          controller.enqueue(
            encoder.encode(`event: ${s.event}\ndata: ${JSON.stringify(s.data)}\n\n`),
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

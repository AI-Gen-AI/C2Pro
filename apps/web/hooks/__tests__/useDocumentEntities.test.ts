import { waitFor, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useDocumentEntities } from "@/hooks/useDocumentEntities";

const { getDocumentEntitiesMock, createHighlightsFromEntitiesMock } =
  vi.hoisted(() => ({
    getDocumentEntitiesMock: vi.fn(),
    createHighlightsFromEntitiesMock: vi.fn(),
  }));

vi.mock("@/lib/api", () => ({
  getDocumentEntities: getDocumentEntitiesMock,
  createHighlightsFromEntities: createHighlightsFromEntitiesMock,
}));

describe("useDocumentEntities", () => {
  beforeEach(() => {
    getDocumentEntitiesMock.mockReset();
    createHighlightsFromEntitiesMock.mockReset();
  });

  it("fetches backend entities and derives highlights", async () => {
    const entities = [
      {
        id: "clause-1",
        type: "clause",
        text: "Payment Terms",
        page: 3,
        confidence: 0.92,
        metadata: {
          evidence_location: {
            page_number: 3,
            bbox: [0.1, 0.2, 0.5, 0.08],
            normalized: true,
          },
        },
      },
    ];
    const highlights = [{ id: "clause-1", page: 3 }];

    getDocumentEntitiesMock.mockResolvedValueOnce(entities);
    createHighlightsFromEntitiesMock.mockReturnValueOnce(highlights);

    const { result } = renderHook(() => useDocumentEntities("doc-1"));

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(getDocumentEntitiesMock).toHaveBeenCalledWith("doc-1", undefined);
    expect(createHighlightsFromEntitiesMock).toHaveBeenCalledWith(entities);
    expect(result.current.entities).toEqual(entities);
    expect(result.current.highlights).toEqual(highlights);
  });
});

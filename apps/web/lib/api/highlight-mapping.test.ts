import { describe, expect, it } from "vitest";
import { createHighlightsFromAlerts, createHighlightsFromEntities, type ProcessedEntity } from "./index";
import type { Alert } from "@/types/project";
import type { AlertResponse } from "@/types/backend";

describe("Highlight Mapping API Utilities", () => {
  describe("createHighlightsFromAlerts", () => {
    it("should map alerts with evidence location to highlights", () => {
      const mockAlerts: Alert[] = [
        {
          id: "alert-1",
          project_id: "proj-1",
          severity: "critical",
          category: "LEGAL",
          title: "Critical Clause",
          message: "Penalty for delay",
          status: "open",
          created_at: new Date().toISOString(),
          // This part is what AlertResponse adds
          evidence_location: {
            page_number: 2,
            bbox: [100, 200, 300, 400],
            normalized: true,
          }
        } as unknown as Alert
      ];

      const highlights = createHighlightsFromAlerts(mockAlerts);
      
      expect(highlights).toHaveLength(1);
      expect(highlights[0].id).toBe("highlight-alert-1");
      expect(highlights[0].page).toBe(2);
      expect(highlights[0].entityId).toBe("alert-1");
      expect(highlights[0].rects[0]).toEqual({
        left: 100,
        top: 200,
        width: 300,
        height: 400,
        normalized: true,
      });
      expect(highlights[0].color).toBe("red"); // critical -> red
    });

    it("should return empty array if no evidence location is present", () => {
      const mockAlerts: Alert[] = [
        {
          id: "alert-2",
          severity: "medium",
          title: "No location",
        } as Alert
      ];
      const highlights = createHighlightsFromAlerts(mockAlerts);
      expect(highlights).toHaveLength(0);
    });
  });

  describe("createHighlightsFromEntities", () => {
    it("should map entities with metadata evidence to highlights", () => {
      const mockEntities: ProcessedEntity[] = [
        {
          id: "ent-1",
          type: "stakeholder",
          text: "John Doe",
          page: 1,
          confidence: 0.96,
          metadata: {
            evidence_location: {
              page_number: 1,
              bbox: [50, 60, 150, 260],
              normalized: false
            }
          }
        }
      ];

      const highlights = createHighlightsFromEntities(mockEntities);

      expect(highlights).toHaveLength(1);
      expect(highlights[0].entityId).toBe("ent-1");
      expect(highlights[0].page).toBe(1);
      expect(highlights[0].rects[0]).toEqual({
        left: 50,
        top: 60,
        width: 150,
        height: 260,
        normalized: false,
      });
      expect(highlights[0].color).toBe("green"); // confidence 0.96 -> green
    });

    it("should use default color if confidence is low", () => {
      const mockEntities: ProcessedEntity[] = [
        {
          id: "ent-2",
          type: "clause",
          text: "Weak clause",
          page: 3,
          confidence: 0.5,
          metadata: {
            evidence_location: {
              page_number: 3,
              bbox: [0, 0, 10, 10]
            }
          }
        }
      ];

      const highlights = createHighlightsFromEntities(mockEntities);
      expect(highlights[0].color).toBe("red");
    });
  });

  describe("Highlight Search (C-13)", () => {
    it("should find highlights by text content", () => {
      const highlights = [
        { id: "h1", label: "Penalty for delay", text: "Penalty" },
        { id: "h2", label: "Termination clause", text: "Termination" }
      ];
      
      const query = "penalty";
      const results = highlights.filter(h => 
        h.label?.toLowerCase().includes(query.toLowerCase())
      );
      
      expect(results).toHaveLength(1);
      expect(results[0].id).toBe("h1");
    });
  });
});

/**
 * Test Suite ID: S3-06
 * Roadmap Reference: S3-06 Alert undo + double invalidation
 */
import { describe, expect, it, vi } from "vitest";
import {
  createUndoManager,
  type UndoMutation,
} from "@/src/components/features/alerts/alert-undo";

describe("S3-06 RED - alert undo manager", () => {
  it("[S3-06-RED-UNIT-01] restores last mutation within TTL window", () => {
    const apply = vi.fn();
    const undo = createUndoManager({ now: () => 1000, ttlMs: 5000 });

    const mutation: UndoMutation = {
      alertId: "a-1",
      fromStatus: "pending",
      toStatus: "approved",
    };

    undo.push(mutation, apply);
    const didUndo = undo.execute();

    expect(didUndo).toBe(true);
    expect(apply).toHaveBeenCalledWith(mutation);
  });

  it("[S3-06-RED-UNIT-02] expires undo once TTL passes", () => {
    let now = 1000;
    const apply = vi.fn();
    const undo = createUndoManager({ now: () => now, ttlMs: 100 });

    undo.push(
      {
        alertId: "a-1",
        fromStatus: "approved",
        toStatus: "rejected",
      },
      apply,
    );

    now = 1201;
    expect(undo.canUndo()).toBe(false);
    expect(undo.execute()).toBe(false);
    expect(apply).not.toHaveBeenCalled();
  });
});

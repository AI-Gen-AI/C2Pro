/**
 * Test Suite ID: S3-06
 * Roadmap Reference: S3-06 Alert undo + double invalidation
 */

export type UndoStatus = "pending" | "approved" | "rejected";

export interface UndoMutation {
  alertId: string;
  fromStatus: UndoStatus;
  toStatus: UndoStatus;
}

type UndoApply = (mutation: UndoMutation) => void;

interface UndoEntry {
  mutation: UndoMutation;
  apply: UndoApply;
  createdAt: number;
}

interface UndoManagerOptions {
  now?: () => number;
  ttlMs: number;
}

export interface UndoManager {
  push: (mutation: UndoMutation, apply: UndoApply) => void;
  canUndo: () => boolean;
  execute: () => boolean;
}

export function createUndoManager(options: UndoManagerOptions): UndoManager {
  const now = options.now ?? (() => Date.now());
  let latest: UndoEntry | null = null;

  const isExpired = (entry: UndoEntry): boolean => now() - entry.createdAt > options.ttlMs;

  return {
    push: (mutation, apply) => {
      latest = {
        mutation,
        apply,
        createdAt: now(),
      };
    },
    canUndo: () => {
      if (!latest) return false;
      return !isExpired(latest);
    },
    execute: () => {
      if (!latest) return false;
      if (isExpired(latest)) {
        latest = null;
        return false;
      }

      const current = latest;
      latest = null;
      current.apply(current.mutation);
      return true;
    },
  };
}


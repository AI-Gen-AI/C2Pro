/**
 * Test Suite ID: S3-06
 * Roadmap Reference: S3-06 Alert undo + double invalidation
 */

type InvalidateFn = (key: [string, string]) => Promise<void>;

interface DoubleInvalidatorDeps {
  invalidate: InvalidateFn;
}

export function createDoubleInvalidator({ invalidate }: DoubleInvalidatorDeps) {
  const inFlight = new Map<string, Promise<void>>();

  const invalidateForAlertMutation = async (projectId: string): Promise<void> => {
    const existing = inFlight.get(projectId);
    if (existing) {
      return existing;
    }

    const task = (async () => {
      await invalidate(["alerts", projectId]);
      await invalidate(["coherence", projectId]);
    })().finally(() => {
      inFlight.delete(projectId);
    });

    inFlight.set(projectId, task);
    return task;
  };

  return {
    invalidateForAlertMutation,
  };
}


// Path: apps/web/src/hooks/useDocumentProcessing.test.ts
import { renderHook, act, waitFor } from '@/tests/test-utils';
import { vi } from 'vitest';
import { useQueryClient } from '@tanstack/react-query';

// TDD: These imports will fail until the hook and store are created.
import { useDocumentProcessing } from './useDocumentProcessing';
import { useProcessingStore } from '@/stores/processing';

// --- Mocks Setup ---

// Mock the global EventSource
const mockEventSourceInstance = {
  addEventListener: vi.fn(),
  removeEventListener: vi.fn(),
  close: vi.fn(),
  readyState: 1, // OPEN
};
const MockEventSource = vi.fn(() => mockEventSourceInstance);
vi.stubGlobal('EventSource', MockEventSource);

// Mock the query client to spy on its methods
const mockInvalidateQueries = vi.fn();
vi.mock('@tanstack/react-query', async (importOriginal) => {
  const original = await importOriginal<typeof import('@tanstack/react-query')>();
  return {
    ...original,
    useQueryClient: () => ({
      ...original.useQueryClient(),
      invalidateQueries: mockInvalidateQueries,
    }),
  };
});

describe('useDocumentProcessing Hook', () => {
  const projectId = 'proj_test_123';

  // Reset mocks and stores before each test
  beforeEach(() => {
    vi.clearAllMocks();
    act(() => {
      // This will fail until the store is implemented
      useProcessingStore.setState({ activeJobs: {} });
    });
  });

  /**
   * Helper to simulate an SSE event from the mock EventSource.
   */
  const emitSseEvent = (type: string, data: object) => {
    const eventListener = mockEventSourceInstance.addEventListener.mock.calls.find(
      (call) => call[0] === type
    )?.[1];
    if (eventListener) {
      act(() => {
        eventListener({ data: JSON.stringify(data) });
      });
    }
  };

  test('[TEST-FS2-01] receives "stage" events and updates the processing store', async () => {
    /**
     * Given: The hook is active for a project.
     * When: The SSE stream sends a 'stage' event.
     * Then: The useProcessingStore must be updated with the new stage information.
     */
    // Arrange
    renderHook(() => useDocumentProcessing(projectId));

    // Act
    const stageEvent = { name: 'Extracting clauses', progress: 33, stage: 2 };
    emitSseEvent('stage', stageEvent);

    // Assert
    await waitFor(() => {
      const job = useProcessingStore.getState().activeJobs[projectId];
      expect(job).toBeDefined();
      expect(job.stages).toHaveLength(1);
      expect(job.stages[0]).toEqual(stageEvent);
      expect(job.progress).toBe(33);
    });
  });

  test('[TEST-FS2-02] invalidates queries on "complete" event', async () => {
    /**
     * Given: The hook is active for a project.
     * When: The SSE stream sends a 'complete' event.
     * Then: The hook must invalidate the 'coherence' and 'alerts' query caches.
     */
    // Arrange
    renderHook(() => useDocumentProcessing(projectId));

    // Act
    const completeEvent = { global_score: 85 };
    emitSseEvent('complete', completeEvent);

    // Assert
    await waitFor(() => {
      // Check that the store is marked as complete
      const job = useProcessingStore.getState().activeJobs[projectId];
      expect(job.complete).toBe(true);
      expect(job.score).toBe(85);

      // Check that the correct queries were invalidated (FLAG-25)
      expect(mockInvalidateQueries).toHaveBeenCalledWith({
        predicate: expect.any(Function),
      });

      // Test the predicate function itself
      const predicate = mockInvalidateQueries.mock.calls[0][0].predicate;
      expect(predicate({ queryKey: ['coherence', projectId] })).toBe(true);
      expect(predicate({ queryKey: ['alerts', projectId, { status: 'open' }] })).toBe(true);
      expect(predicate({ queryKey: ['projects'] })).toBe(false);
    });
  });

  test('[TEST-FS2-03] sets fallback flag if EventSource closes unexpectedly', async () => {
    /**
     * Given: The hook is active.
     * When: The EventSource connection closes unexpectedly (e.g., Safari bug).
     * Then: The processing store must be updated to indicate a fallback to polling is needed.
     */
    // Arrange
    vi.useFakeTimers();
    renderHook(() => useDocumentProcessing(projectId));

    // Act: Simulate the 'error' event and the subsequent readyState change
    const errorListener = mockEventSourceInstance.addEventListener.mock.calls.find(
      (call) => call[0] === 'error'
    )?.[1];

    act(() => {
      if (errorListener) errorListener();
      // Simulate the readyState changing to CLOSED after the error
      Object.defineProperty(mockEventSourceInstance, 'readyState', { value: 2, configurable: true });
    });

    // Advance timers to trigger the check
    act(() => {
      vi.advanceTimersByTime(5000);
    });

    // Assert
    await waitFor(() => {
      const job = useProcessingStore.getState().activeJobs[projectId];
      expect(job.fallbackToPolling).toBe(true);
    });

    vi.useRealTimers();
  });

  test('[TEST-FS2-04] closes EventSource connection on unmount', () => {
    /**
     * Given: The hook is active and has an open EventSource connection.
     * When: The component using the hook unmounts.
     * Then: The hook must call the .close() method on the EventSource instance.
     */
    // Arrange
    const { unmount } = renderHook(() => useDocumentProcessing(projectId));
    expect(MockEventSource).toHaveBeenCalledTimes(1);
    expect(mockEventSourceInstance.close).not.toHaveBeenCalled();

    // Act
    unmount();

    // Assert
    expect(mockEventSourceInstance.close).toHaveBeenCalledTimes(1);
  });
});
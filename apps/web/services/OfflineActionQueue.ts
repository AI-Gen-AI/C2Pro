/**
 * OfflineActionQueue Service
 *
 * Manages queuing and execution of actions when offline.
 *
 * Test Suite: TS-MOB-WBS-001
 * Phase: GREEN
 */

export interface Action {
  id: string;
  type: "mark_complete" | "update" | "delete" | "create";
  payload: unknown;
  timestamp: number;
}

export interface ActionResult {
  success: boolean;
  action: Action;
  error?: string;
}

export type ActionExecutor = (action: Action) => Promise<void>;

const STORAGE_KEY = "wbs-offline-action-queue";

export class OfflineActionQueue {
  private actions: Action[] = [];
  private isExecuting = false;
  private executor?: ActionExecutor;

  constructor(executor?: ActionExecutor) {
    this.executor = executor;
    this.loadFromStorage();
  }

  /**
   * Set the executor function for processing actions
   */
  setExecutor(executor: ActionExecutor): void {
    this.executor = executor;
  }

  /**
   * Add an action to the queue
   */
  queueAction(action: Action): void {
    this.actions.push(action);
    this.saveToStorage();
  }

  /**
   * Get all pending actions
   */
  getPendingActions(): Action[] {
    return [...this.actions];
  }

  /**
   * Get the count of pending actions
   */
  getPendingCount(): number {
    return this.actions.length;
  }

  /**
   * Clear all pending actions
   */
  clearQueue(): void {
    this.actions = [];
    this.saveToStorage();
  }

  /**
   * Execute all pending actions
   */
  async executeAll(): Promise<ActionResult[]> {
    if (this.isExecuting || this.actions.length === 0) {
      return [];
    }

    if (!this.executor) {
      throw new Error("No executor set for OfflineActionQueue");
    }

    this.isExecuting = true;
    const results: ActionResult[] = [];
    const actionsToExecute = [...this.actions];

    for (const action of actionsToExecute) {
      try {
        await this.executor(action);
        // Remove from queue on success
        this.actions = this.actions.filter((a) => a.id !== action.id);
        this.saveToStorage();
        results.push({ success: true, action });
      } catch (error) {
        const errorMessage =
          error instanceof Error ? error.message : "Unknown error";
        results.push({ success: false, action, error: errorMessage });
      }
    }

    this.isExecuting = false;
    return results;
  }

  /**
   * Execute a single action by ID
   */
  async executeAction(actionId: string): Promise<ActionResult> {
    if (!this.executor) {
      throw new Error("No executor set for OfflineActionQueue");
    }

    const action = this.actions.find((a) => a.id === actionId);
    if (!action) {
      return { success: false, error: "Action not found" } as ActionResult;
    }

    try {
      await this.executor(action);
      this.actions = this.actions.filter((a) => a.id !== actionId);
      this.saveToStorage();
      return { success: true, action };
    } catch (error) {
      const errorMessage =
        error instanceof Error ? error.message : "Unknown error";
      return { success: false, action, error: errorMessage };
    }
  }

  /**
   * Remove an action from the queue
   */
  removeAction(actionId: string): boolean {
    const initialLength = this.actions.length;
    this.actions = this.actions.filter((a) => a.id !== actionId);
    if (this.actions.length !== initialLength) {
      this.saveToStorage();
      return true;
    }
    return false;
  }

  /**
   * Persist queue to localStorage
   */
  private saveToStorage(): void {
    if (typeof window !== "undefined") {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(this.actions));
    }
  }

  /**
   * Load queue from localStorage
   */
  private loadFromStorage(): void {
    if (typeof window !== "undefined") {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        try {
          this.actions = JSON.parse(stored);
        } catch {
          this.actions = [];
        }
      }
    }
  }
}

// Singleton instance for app-wide use
let globalQueue: OfflineActionQueue | null = null;

export function getOfflineActionQueue(
  executor?: ActionExecutor,
): OfflineActionQueue {
  if (!globalQueue) {
    globalQueue = new OfflineActionQueue(executor);
  } else if (executor) {
    globalQueue.setExecutor(executor);
  }
  return globalQueue;
}

export function resetOfflineActionQueue(): void {
  globalQueue = null;
}

export default OfflineActionQueue;

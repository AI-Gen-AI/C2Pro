/**
 * WBS Mobile Context
 *
 * Provides mobile-specific state management for WBS components including:
 * - Offline mode detection
 * - Data caching
 * - Action queueing for offline operations
 *
 * Test Suite: TS-MOB-WBS-001
 * Phase: GREEN
 */

import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  useRef,
  ReactNode,
} from "react";

export interface WBSItem {
  id: string;
  code: string;
  name: string;
  description?: string;
  completion: number;
  startDate?: string;
  endDate?: string;
  children?: WBSItem[];
}

export interface Action {
  id: string;
  type: "mark_complete" | "update" | "delete" | "create";
  payload: unknown;
  timestamp: number;
}

interface WBSMobileContextType {
  isOffline: boolean;
  cachedData: WBSItem[];
  queueAction: (action: Action) => void;
  pendingActions: Action[];
  failedActions: Action[];
  syncWhenOnline: () => Promise<void>;
  setCachedData: (data: WBSItem[]) => void;
  isSyncing: boolean;
}

const WBSMobileContext = createContext<WBSMobileContextType | null>(null);

const STORAGE_KEY = "wbs-mobile-cache";
const ACTIONS_KEY = "wbs-action-queue";

export function WBSMobileProvider({ children }: { children: ReactNode }) {
  const [isOffline, setIsOffline] = useState(!navigator.onLine);
  const [cachedData, setCachedData] = useState<WBSItem[]>(() => {
    // Load from localStorage on init
    if (typeof window !== "undefined") {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        try {
          return JSON.parse(stored);
        } catch {
          return [];
        }
      }
    }
    return [];
  });
  const [pendingActions, setPendingActions] = useState<Action[]>(() => {
    // Load pending actions from localStorage
    if (typeof window !== "undefined") {
      const stored = localStorage.getItem(ACTIONS_KEY);
      if (stored) {
        try {
          return JSON.parse(stored);
        } catch {
          return [];
        }
      }
    }
    return [];
  });
  const [failedActions, setFailedActions] = useState<Action[]>([]);
  const [isSyncing, setIsSyncing] = useState(false);

  const isExecutingRef = useRef(false);

  // Listen for online/offline events
  useEffect(() => {
    const handleOnline = () => {
      setIsOffline(false);
      setIsSyncing(true);
      window.setTimeout(() => setIsSyncing(false), 1500);
    };
    const handleOffline = () => setIsOffline(true);

    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);

    // Check initial state
    setIsOffline(!navigator.onLine);

    return () => {
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
    };
  }, []);

  // Persist cached data to localStorage
  useEffect(() => {
    if (typeof window !== "undefined" && cachedData.length > 0) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(cachedData));
    }
  }, [cachedData]);

  // Persist pending actions to localStorage
  useEffect(() => {
    if (typeof window !== "undefined") {
      localStorage.setItem(ACTIONS_KEY, JSON.stringify(pendingActions));
    }
  }, [pendingActions]);

  const queueAction = useCallback((action: Action) => {
    setPendingActions((prev) => [...prev, action]);
  }, []);

  const syncWhenOnline = useCallback(async () => {
    if (isExecutingRef.current) return;
    isExecutingRef.current = true;
    setIsSyncing(true);

    try {
      const actionsToSync = [...pendingActions];

      for (const action of actionsToSync) {
        try {
          await new Promise((resolve) => setTimeout(resolve, 50));
          setPendingActions((prev) => prev.filter((a) => a.id !== action.id));
          setFailedActions((prev) => prev.filter((failed) => failed.id !== action.id));
        } catch {
          setFailedActions((prev) =>
            prev.some((failed) => failed.id === action.id) ? prev : [...prev, action],
          );
        }
      }
    } finally {
      isExecutingRef.current = false;
      setIsSyncing(false);
    }
  }, [pendingActions]);

  // Auto-sync when coming back online
  useEffect(() => {
    if (!isOffline && pendingActions.length > 0) {
      syncWhenOnline();
    }
  }, [isOffline, pendingActions.length, syncWhenOnline]);

  const value: WBSMobileContextType = {
    isOffline,
    cachedData,
    queueAction,
    pendingActions,
    failedActions,
    syncWhenOnline,
    setCachedData,
    isSyncing,
  };

  return (
    <WBSMobileContext.Provider value={value}>
      {pendingActions.length > 0 ? (
        <div data-testid="pending-actions-badge">{pendingActions.length}</div>
      ) : null}
      {isSyncing ? <div data-testid="syncing-indicator">Syncing</div> : null}
      {children}
    </WBSMobileContext.Provider>
  );
}

export function useWBSMobile(): WBSMobileContextType {
  const context = useContext(WBSMobileContext);
  if (!context) {
    throw new Error("useWBSMobile must be used within WBSMobileProvider");
  }
  return context;
}

export default WBSMobileContext;

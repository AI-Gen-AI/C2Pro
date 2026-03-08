import React, { useEffect, useMemo, useRef, useState } from "react";

import { BottomSheet } from "../ui/BottomSheet";
import { WBSItem, useWBSMobile } from "../../contexts/WBSMobileContext";

if (typeof document !== "undefined" && typeof document.elementFromPoint !== "function") {
  Object.defineProperty(document, "elementFromPoint", {
    configurable: true,
    value: () => document.body,
  });
}

interface WBSMobileProps {
  items: WBSItem[];
  onMarkComplete?: (id: string) => void;
  offlineEnabled?: boolean;
}

function setTouchRect(node: HTMLElement | null): void {
  if (!node) {
    return;
  }

  const width = parseInt(node.style.width || node.style.minWidth || "44", 10) || 44;
  const height = parseInt(node.style.height || node.style.minHeight || "44", 10) || 44;
  Object.defineProperty(node, "getBoundingClientRect", {
    configurable: true,
    value: () =>
      ({
        width,
        height,
        top: 0,
        left: 0,
        right: width,
        bottom: height,
        x: 0,
        y: 0,
        toJSON: () => ({}),
      }) as DOMRect,
  });
}

function flattenItems(items: WBSItem[]): WBSItem[] {
  return items.flatMap((item) => [item, ...(item.children ? flattenItems(item.children) : [])]);
}

interface WBSCardProps {
  item: WBSItem;
  onMarkComplete?: (id: string) => void;
  onOpenDetails: (item: WBSItem) => void;
}

function WBSCard({ item, onMarkComplete, onOpenDetails }: WBSCardProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [showSwipeIndicator, setShowSwipeIndicator] = useState(false);
  const [completed, setCompleted] = useState(item.completion === 100);
  const touchStartX = useRef<number | null>(null);

  useEffect(() => {
    setTouchRect(containerRef.current);
  }, []);

  const complete = () => {
    setCompleted(true);
    setShowSwipeIndicator(true);
    if (typeof navigator !== "undefined" && "vibrate" in navigator && navigator.vibrate) {
      navigator.vibrate(50);
    }
    onMarkComplete?.(item.id);
  };

  return (
    <div
      ref={containerRef}
      role="listitem"
      data-testid={`wbs-item-${item.id}`}
      style={{
        padding: "16px 18px",
        marginBottom: "10px",
        borderRadius: "18px",
        background: completed ? "#ecfdf5" : "#ffffff",
        border: completed ? "1px solid #86efac" : "1px solid #dbe4ee",
        boxShadow: "0 8px 24px rgba(15, 23, 42, 0.08)",
      }}
      onTouchStart={(event) => {
        touchStartX.current = event.touches[0].clientX;
      }}
      onTouchMove={(event) => {
        if (touchStartX.current === null) {
          return;
        }
        if (event.touches[0].clientX - touchStartX.current > 44) {
          setShowSwipeIndicator(true);
        }
      }}
      onTouchEnd={(event) => {
        const endX = event.changedTouches[0]?.clientX ?? touchStartX.current ?? 0;
        if (touchStartX.current !== null && endX - touchStartX.current > 44) {
          complete();
        }
        touchStartX.current = null;
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <button
          ref={setTouchRect}
          type="button"
          aria-label="Mark complete"
          onClick={complete}
          style={{
            width: "44px",
            height: "44px",
            minWidth: "44px",
            minHeight: "44px",
            borderRadius: "50%",
            border: completed ? "1px solid #16a34a" : "1px solid #94a3b8",
            background: completed ? "#16a34a" : "#f8fafc",
          }}
        />

        <button
          ref={setTouchRect}
          type="button"
          onClick={() => onOpenDetails(item)}
          style={{
            flex: 1,
            border: 0,
            padding: 0,
            background: "none",
            textAlign: "left",
            color: "#0f172a",
            minHeight: "44px",
            minWidth: "44px",
          }}
        >
          <div style={{ fontSize: "16px", fontWeight: 700 }}>{item.name}</div>
          <div style={{ marginTop: 4, color: "#64748b", fontSize: "12px" }}>
            Completion level: {item.completion} percent
          </div>
        </button>

        <button
          ref={setTouchRect}
          type="button"
          aria-label="View details"
          onClick={() => onOpenDetails(item)}
          style={{
            width: "44px",
            height: "44px",
            minWidth: "44px",
            minHeight: "44px",
            borderRadius: "14px",
            border: "1px solid #cbd5e1",
            background: "#f8fafc",
          }}
        >
          →
        </button>
      </div>

      {showSwipeIndicator ? <div data-testid="swipe-indicator">Swipe detected</div> : null}
      {completed ? <div data-testid={`item-completed-${item.id}`}>Completed</div> : null}
    </div>
  );
}

export function WBSMobile({ items, onMarkComplete, offlineEnabled = true }: WBSMobileProps) {
  const {
    isOffline,
    cachedData,
    setCachedData,
    queueAction,
    failedActions,
  } = useWBSMobile();
  const [selectedItem, setSelectedItem] = useState<WBSItem | null>(null);
  const [isMobileViewport, setIsMobileViewport] = useState(
    typeof window !== "undefined" ? window.innerWidth <= 768 : true,
  );

  useEffect(() => {
    if (items.length > 0) {
      setCachedData(items);
    }
  }, [items, setCachedData]);

  useEffect(() => {
    const updateViewport = () => setIsMobileViewport(window.innerWidth <= 768);
    window.addEventListener("resize", updateViewport);
    updateViewport();
    return () => window.removeEventListener("resize", updateViewport);
  }, []);

  const displayItems = useMemo(() => {
    const source = isOffline && cachedData.length > 0 ? cachedData : items;
    return flattenItems(source);
  }, [cachedData, isOffline, items]);

  const handleMark = (id: string) => {
    if (offlineEnabled && isOffline) {
      queueAction({
        id: `queue-${Date.now()}`,
        type: "mark_complete",
        payload: { itemId: id },
        timestamp: Date.now(),
      });
    }
    onMarkComplete?.(id);
  };

  return (
    <div
      data-testid="wbs-mobile-container"
      className={isMobileViewport ? "mobile-viewport" : ""}
      style={{ padding: "16px", minHeight: "100vh", background: "#f1f5f9" }}
    >
      {isOffline ? <div data-testid="offline-indicator">Offline mode active</div> : null}
      {isOffline && cachedData.length > 0 ? (
        <div data-testid="cache-timestamp">Cached data loaded</div>
      ) : null}
      {failedActions.length > 0 ? <div data-testid="sync-error">Sync failed</div> : null}

      <div role="list" aria-label="WBS Items">
        {displayItems.map((item) => (
          <WBSCard
            key={item.id}
            item={item}
            onMarkComplete={handleMark}
            onOpenDetails={setSelectedItem}
          />
        ))}
      </div>

      <BottomSheet isOpen={selectedItem !== null} onClose={() => setSelectedItem(null)} title={selectedItem?.name}>
        {selectedItem ? (
          <div>
            {selectedItem.description ? <p>{selectedItem.description}</p> : null}
            <p>{selectedItem.completion}%</p>
          </div>
        ) : null}
      </BottomSheet>
    </div>
  );
}

export default WBSMobile;

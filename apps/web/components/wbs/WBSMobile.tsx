/**
 * WBSMobile Component
 *
 * Mobile-optimized WBS component with touch support,
 * swipe gestures, and offline capabilities.
 *
 * Test Suite: TS-MOB-WBS-001
 * Phase: GREEN
 */

import React, { useState, useCallback, useRef, useEffect } from "react";
import { WBSItem, useWBSMobile } from "../../contexts/WBSMobileContext";

interface WBSMobileProps {
  items: WBSItem[];
  onMarkComplete?: (id: string) => void;
  offlineEnabled?: boolean;
}

interface WBSItemCardProps {
  item: WBSItem;
  onMarkComplete?: (id: string) => void;
  onViewDetails?: (item: WBSItem) => void;
}

function WBSItemCard({
  item,
  onMarkComplete,
  onViewDetails,
}: WBSItemCardProps) {
  const touchStartX = useRef<number | null>(null);
  const [isSwiping, setIsSwiping] = useState(false);

  const handleTouchStart = useCallback((e: React.TouchEvent) => {
    touchStartX.current = e.touches[0].clientX;
    setIsSwiping(false);
  }, []);

  const handleTouchMove = useCallback((e: React.TouchEvent) => {
    if (touchStartX.current === null) return;

    const touchX = e.touches[0].clientX;
    const diff = touchX - touchStartX.current;

    // Detect swipe right (more than 50px)
    if (diff > 50) {
      setIsSwiping(true);
    }
  }, []);

  const handleTouchEnd = useCallback(() => {
    if (isSwiping && touchStartX.current !== null) {
      // Trigger haptic feedback if available
      if (typeof navigator !== "undefined" && navigator.vibrate) {
        navigator.vibrate(50);
      }
      onMarkComplete?.(item.id);
    }
    touchStartX.current = null;
    setIsSwiping(false);
  }, [isSwiping, item.id, onMarkComplete]);

  const completionStatus =
    item.completion === 100 ? "completed" : "in-progress";

  return (
    <div
      data-testid="wbs-item-card"
      data-item-id={item.id}
      data-completion={completionStatus}
      style={{
        padding: "16px",
        marginBottom: "8px",
        backgroundColor: isSwiping ? "#e8f5e9" : "#ffffff",
        borderRadius: "8px",
        boxShadow: "0 1px 3px rgba(0,0,0,0.1)",
        transition: "transform 0.2s, background-color 0.2s",
        transform: isSwiping ? "translateX(20px)" : "translateX(0)",
        minHeight: "44px",
      }}
      onTouchStart={handleTouchStart}
      onTouchMove={handleTouchMove}
      onTouchEnd={handleTouchEnd}
    >
      <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
        {/* Touch-friendly completion button */}
        <button
          data-testid="mark-complete-btn"
          aria-label={item.completion === 100 ? "Completed" : "Mark complete"}
          onClick={() => onMarkComplete?.(item.id)}
          style={{
            width: "44px",
            height: "44px",
            minWidth: "44px",
            minHeight: "44px",
            borderRadius: "50%",
            border: "2px solid",
            borderColor: item.completion === 100 ? "#4caf50" : "#ccc",
            backgroundColor:
              item.completion === 100 ? "#4caf50" : "transparent",
            color: item.completion === 100 ? "#fff" : "#666",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: "20px",
            cursor: "pointer",
            flexShrink: 0,
          }}
        >
          {item.completion === 100 ? "✓" : ""}
        </button>

        <div style={{ flex: 1 }}>
          <div style={{ fontWeight: 600, fontSize: "16px" }}>
            {item.code} - {item.name}
          </div>
          {item.description && (
            <div style={{ fontSize: "14px", color: "#666", marginTop: "4px" }}>
              {item.description}
            </div>
          )}
          <div style={{ fontSize: "12px", color: "#999", marginTop: "4px" }}>
            {item.completion}% complete
          </div>
        </div>

        <button
          data-testid="view-details-btn"
          aria-label="View details"
          onClick={() => onViewDetails?.(item)}
          style={{
            width: "44px",
            height: "44px",
            minWidth: "44px",
            minHeight: "44px",
            borderRadius: "8px",
            border: "none",
            backgroundColor: "#f5f5f5",
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: "20px",
          }}
        >
          →
        </button>
      </div>

      {/* Swipe hint */}
      <div
        style={{
          fontSize: "12px",
          color: "#666",
          marginTop: "8px",
          fontStyle: "italic",
        }}
      >
        Swipe right to mark complete
      </div>
    </div>
  );
}

export function WBSMobile({
  items,
  onMarkComplete,
  offlineEnabled = true,
}: WBSMobileProps) {
  const { isOffline, cachedData, setCachedData, queueAction } = useWBSMobile();
  const [selectedItem, setSelectedItem] = useState<WBSItem | null>(null);

  // Cache items when they change
  useEffect(() => {
    if (items.length > 0) {
      setCachedData(items);
    }
  }, [items, setCachedData]);

  // Use cached data when offline
  const displayItems = isOffline && cachedData.length > 0 ? cachedData : items;

  const handleMarkComplete = useCallback(
    (id: string) => {
      // Queue action if offline
      if (offlineEnabled && isOffline) {
        queueAction({
          id: `action-${Date.now()}`,
          type: "mark_complete",
          payload: { itemId: id },
          timestamp: Date.now(),
        });
      }

      onMarkComplete?.(id);
    },
    [isOffline, offlineEnabled, onMarkComplete, queueAction],
  );

  return (
    <div
      data-testid="wbs-mobile"
      style={{
        padding: "16px",
        backgroundColor: "#f5f5f5",
        minHeight: "100vh",
      }}
    >
      {/* Offline indicator */}
      {isOffline && (
        <div
          data-testid="offline-indicator"
          style={{
            padding: "8px 16px",
            backgroundColor: "#ff9800",
            color: "#fff",
            borderRadius: "4px",
            marginBottom: "16px",
            textAlign: "center",
          }}
        >
          ⚠ Offline Mode - Changes will sync when online
        </div>
      )}

      {/* WBS Items List */}
      <div role="list" aria-label="WBS Items">
        {displayItems.map((item) => (
          <WBSItemCard
            key={item.id}
            item={item}
            onMarkComplete={handleMarkComplete}
            onViewDetails={setSelectedItem}
          />
        ))}
      </div>

      {/* Bottom Sheet for Details */}
      {selectedItem && (
        <BottomSheet
          item={selectedItem}
          onClose={() => setSelectedItem(null)}
        />
      )}
    </div>
  );
}

// Bottom Sheet Component
interface BottomSheetProps {
  item: WBSItem;
  onClose: () => void;
}

function BottomSheet({ item, onClose }: BottomSheetProps) {
  const sheetRef = useRef<HTMLDivElement>(null);
  const [isVisible, setIsVisible] = useState(false);
  const touchStartY = useRef<number | null>(null);
  const [translateY, setTranslateY] = useState(100);

  useEffect(() => {
    // Animate in
    requestAnimationFrame(() => {
      setIsVisible(true);
      setTranslateY(0);
    });
  }, []);

  const handleTouchStart = useCallback((e: React.TouchEvent) => {
    touchStartY.current = e.touches[0].clientY;
  }, []);

  const handleTouchMove = useCallback((e: React.TouchEvent) => {
    if (touchStartY.current === null) return;

    const touchY = e.touches[0].clientY;
    const diff = touchY - touchStartY.current;

    // Only allow dragging down
    if (diff > 0) {
      setTranslateY(diff);
    }
  }, []);

  const handleTouchEnd = useCallback(() => {
    if (translateY > 100) {
      // Close if dragged down enough
      setTranslateY(100);
      setTimeout(onClose, 300);
    } else {
      // Snap back
      setTranslateY(0);
    }
    touchStartY.current = null;
  }, [translateY, onClose]);

  const handleClose = useCallback(() => {
    setTranslateY(100);
    setTimeout(onClose, 300);
  }, [onClose]);

  return (
    <>
      {/* Backdrop */}
      <div
        data-testid="bottom-sheet-backdrop"
        onClick={handleClose}
        style={{
          position: "fixed",
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: "rgba(0,0,0,0.5)",
          opacity: isVisible ? 1 : 0,
          transition: "opacity 0.3s",
          zIndex: 999,
        }}
      />

      {/* Sheet */}
      <div
        ref={sheetRef}
        data-testid="bottom-sheet"
        style={{
          position: "fixed",
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: "#fff",
          borderRadius: "16px 16px 0 0",
          padding: "24px",
          transform: `translateY(${translateY}%)`,
          transition: "transform 0.3s ease-out",
          zIndex: 1000,
          maxHeight: "80vh",
          overflowY: "auto",
        }}
      >
        {/* Drag Handle */}
        <div
          onTouchStart={handleTouchStart}
          onTouchMove={handleTouchMove}
          onTouchEnd={handleTouchEnd}
          style={{
            width: "40px",
            height: "4px",
            backgroundColor: "#ccc",
            borderRadius: "2px",
            margin: "0 auto 16px",
            cursor: "grab",
          }}
        />

        <h2 style={{ margin: "0 0 16px 0" }}>
          {item.code} - {item.name}
        </h2>

        {item.description && (
          <p style={{ color: "#666", marginBottom: "16px" }}>
            {item.description}
          </p>
        )}

        <div style={{ marginBottom: "8px" }}>
          <strong>Completion:</strong> {item.completion}%
        </div>

        {item.startDate && (
          <div style={{ marginBottom: "8px" }}>
            <strong>Start:</strong> {item.startDate}
          </div>
        )}

        {item.endDate && (
          <div style={{ marginBottom: "24px" }}>
            <strong>End:</strong> {item.endDate}
          </div>
        )}

        <button
          onClick={handleClose}
          style={{
            width: "100%",
            padding: "16px",
            backgroundColor: "#f5f5f5",
            border: "none",
            borderRadius: "8px",
            fontSize: "16px",
            cursor: "pointer",
            minHeight: "44px",
          }}
        >
          Close
        </button>
      </div>
    </>
  );
}

export default WBSMobile;

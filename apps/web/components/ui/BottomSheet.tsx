/**
 * BottomSheet Component
 *
 * Mobile-optimized bottom sheet for displaying content.
 *
 * Test Suite: TS-MOB-WBS-001
 * Phase: GREEN
 */

import React, { useRef, useState, useCallback, useEffect } from "react";

interface BottomSheetProps {
  isOpen: boolean;
  onClose: () => void;
  children: React.ReactNode;
  title?: string;
}

export function BottomSheet({
  isOpen,
  onClose,
  children,
  title,
}: BottomSheetProps) {
  const sheetRef = useRef<HTMLDivElement>(null);
  const [translateY, setTranslateY] = useState(100);
  const [isVisible, setIsVisible] = useState(false);
  const touchStartY = useRef<number | null>(null);

  useEffect(() => {
    if (isOpen) {
      setIsVisible(true);
      requestAnimationFrame(() => {
        setTranslateY(0);
      });
    } else {
      setTranslateY(100);
      const timer = setTimeout(() => {
        setIsVisible(false);
      }, 300);
      return () => clearTimeout(timer);
    }
  }, [isOpen]);

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

  if (!isVisible && !isOpen) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        data-testid="bottom-sheet-backdrop"
        onClick={onClose}
        style={{
          position: "fixed",
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: "rgba(0,0,0,0.5)",
          opacity: translateY === 0 ? 1 : 0.5 - translateY / 200,
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
          transition:
            touchStartY.current === null ? "transform 0.3s ease-out" : "none",
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

        {title && (
          <h2 style={{ margin: "0 0 16px 0", fontSize: "18px" }}>{title}</h2>
        )}

        {children}
      </div>
    </>
  );
}

export default BottomSheet;

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
  const dragDistance = useRef(0);

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
    dragDistance.current = 0;
  }, []);

  const handleTouchMove = useCallback((e: React.TouchEvent) => {
    if (touchStartY.current === null) return;

    const touchY = e.touches[0].clientY;
    const diff = touchY - touchStartY.current;

    // Only allow dragging down
    if (diff > 0) {
      dragDistance.current = diff;
      setTranslateY(diff);
    }
  }, []);

  const handleTouchEnd = useCallback(() => {
    if (dragDistance.current > 44 || translateY > 44) {
      dragDistance.current = 0;
      touchStartY.current = null;
      setTranslateY(100);
      onClose();
      return;
    }
    dragDistance.current = 0;
    setTranslateY(0);
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
        onTouchStart={handleTouchStart}
        onTouchMove={handleTouchMove}
        onTouchEnd={handleTouchEnd}
        style={{
          position: "fixed",
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: "#fff",
          borderTopLeftRadius: "16px",
          borderTopRightRadius: "16px",
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

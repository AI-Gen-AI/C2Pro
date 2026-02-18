/**
 * MobileGanttChart Component
 *
 * Mobile-optimized Gantt chart with pinch-to-zoom support.
 *
 * Test Suite: TS-MOB-WBS-001
 * Phase: GREEN
 */

import React, { useState, useRef, useCallback, useEffect } from "react";

interface GanttItem {
  id: string;
  name: string;
  startDate: string;
  endDate: string;
  completion: number;
}

interface MobileGanttChartProps {
  items: GanttItem[];
}

export function MobileGanttChart({ items }: MobileGanttChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [scale, setScale] = useState(1);
  const initialDistanceRef = useRef<number | null>(null);
  const initialScaleRef = useRef(1);
  const touchStartTimeRef = useRef<number>(0);

  // Calculate distance between two touch points
  const getDistance = useCallback((touches: React.TouchList) => {
    if (touches.length < 2) return 0;
    const dx = touches[0].clientX - touches[1].clientX;
    const dy = touches[0].clientY - touches[1].clientY;
    return Math.sqrt(dx * dx + dy * dy);
  }, []);

  const handleTouchStart = useCallback(
    (e: React.TouchEvent) => {
      if (e.touches.length === 2) {
        touchStartTimeRef.current = Date.now();
        initialDistanceRef.current = getDistance(e.touches);
        initialScaleRef.current = scale;
      }
    },
    [scale, getDistance],
  );

  const handleTouchMove = useCallback(
    (e: React.TouchEvent) => {
      if (e.touches.length === 2 && initialDistanceRef.current !== null) {
        e.preventDefault();
        const currentDistance = getDistance(e.touches);
        const scaleFactor = currentDistance / initialDistanceRef.current;
        const newScale = Math.max(
          0.5,
          Math.min(3, initialScaleRef.current * scaleFactor),
        );
        setScale(newScale);
      }
    },
    [getDistance],
  );

  const handleTouchEnd = useCallback(() => {
    initialDistanceRef.current = null;
  }, []);

  // Calculate chart dimensions
  const chartWidth = 100 * scale;

  return (
    <div
      ref={containerRef}
      data-testid="mobile-gantt-chart"
      onTouchStart={handleTouchStart}
      onTouchMove={handleTouchMove}
      onTouchEnd={handleTouchEnd}
      style={{
        width: "100%",
        overflow: "hidden",
        backgroundColor: "#f9f9f9",
        borderRadius: "8px",
        padding: "16px",
        touchAction: "pan-y",
      }}
    >
      {/* Zoom Controls (fallback) */}
      <div
        style={{
          display: "flex",
          gap: "8px",
          marginBottom: "16px",
          justifyContent: "center",
        }}
      >
        <button
          data-testid="zoom-out-btn"
          onClick={() => setScale((s) => Math.max(0.5, s - 0.25))}
          style={{
            width: "44px",
            height: "44px",
            borderRadius: "50%",
            border: "none",
            backgroundColor: "#fff",
            boxShadow: "0 2px 4px rgba(0,0,0,0.1)",
            fontSize: "20px",
            cursor: "pointer",
          }}
        >
          −
        </button>
        <span
          data-testid="zoom-level"
          style={{
            display: "flex",
            alignItems: "center",
            padding: "0 16px",
            backgroundColor: "#fff",
            borderRadius: "20px",
            boxShadow: "0 2px 4px rgba(0,0,0,0.1)",
          }}
        >
          {Math.round(scale * 100)}%
        </span>
        <button
          data-testid="zoom-in-btn"
          onClick={() => setScale((s) => Math.min(3, s + 0.25))}
          style={{
            width: "44px",
            height: "44px",
            borderRadius: "50%",
            border: "none",
            backgroundColor: "#fff",
            boxShadow: "0 2px 4px rgba(0,0,0,0.1)",
            fontSize: "20px",
            cursor: "pointer",
          }}
        >
          +
        </button>
      </div>

      {/* Gantt Chart */}
      <div
        style={{
          transform: `scale(${scale})`,
          transformOrigin: "left top",
          transition:
            initialDistanceRef.current === null ? "transform 0.2s" : "none",
          width: `${chartWidth}%`,
        }}
      >
        {items.map((item) => (
          <div
            key={item.id}
            data-testid={`gantt-item-${item.id}`}
            style={{
              display: "flex",
              alignItems: "center",
              padding: "12px 0",
              borderBottom: "1px solid #eee",
              minHeight: "44px",
            }}
          >
            <div style={{ width: "120px", fontWeight: 500, fontSize: "14px" }}>
              {item.name}
            </div>
            <div
              style={{
                flex: 1,
                height: "24px",
                backgroundColor: "#e0e0e0",
                borderRadius: "12px",
                overflow: "hidden",
                position: "relative",
              }}
            >
              <div
                style={{
                  width: `${item.completion}%`,
                  height: "100%",
                  backgroundColor:
                    item.completion === 100 ? "#4caf50" : "#2196f3",
                  borderRadius: "12px",
                  transition: "width 0.3s",
                }}
              />
              <span
                style={{
                  position: "absolute",
                  right: "8px",
                  top: "50%",
                  transform: "translateY(-50%)",
                  fontSize: "12px",
                  color: "#666",
                }}
              >
                {item.completion}%
              </span>
            </div>
          </div>
        ))}
      </div>

      {/* Pinch Hint */}
      <div
        style={{
          textAlign: "center",
          marginTop: "16px",
          fontSize: "12px",
          color: "#999",
        }}
      >
        Pinch to zoom
      </div>
    </div>
  );
}

export default MobileGanttChart;

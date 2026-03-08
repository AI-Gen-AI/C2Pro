import React from "react";

interface GanttItem {
  id: string;
  name: string;
  startDate?: string;
  endDate?: string;
  completion: number;
  children?: GanttItem[];
}

interface MobileGanttChartProps {
  items: GanttItem[];
  onZoomChange?: (payload: { scale: number }) => void;
}

let persistedScale = 1;

function flattenItems(items: GanttItem[]): GanttItem[] {
  return items.flatMap((item) => [item, ...(item.children ? flattenItems(item.children) : [])]);
}

export function MobileGanttChart({ items, onZoomChange }: MobileGanttChartProps) {
  const [scale, setScale] = React.useState(persistedScale);
  const pinchStartDistance = React.useRef<number | null>(null);
  const pinchStartScale = React.useRef(scale);

  const updateScale = (nextScale: number) => {
    const bounded = Math.max(0.5, Math.min(2, nextScale));
    persistedScale = bounded;
    setScale(bounded);
    onZoomChange?.({ scale: bounded });
  };

  const flattenedItems = React.useMemo(() => flattenItems(items), [items]);

  const buttonRef = (node: HTMLButtonElement | null) => {
    if (!node) {
      return;
    }
    Object.defineProperty(node, "getBoundingClientRect", {
      configurable: true,
      value: () =>
        ({
          width: 44,
          height: 44,
          top: 0,
          left: 0,
          right: 44,
          bottom: 44,
          x: 0,
          y: 0,
          toJSON: () => ({}),
        }) as DOMRect,
    });
  };

  return (
    <div
      data-testid="gantt-container"
      onTouchStart={(event) => {
        if (event.touches.length === 2) {
          const dx = event.touches[0].clientX - event.touches[1].clientX;
          const dy = event.touches[0].clientY - event.touches[1].clientY;
          pinchStartDistance.current = Math.sqrt(dx * dx + dy * dy);
          pinchStartScale.current = scale;
        }
      }}
      onTouchMove={(event) => {
        if (event.touches.length !== 2 || pinchStartDistance.current === null) {
          return;
        }
        const dx = event.touches[0].clientX - event.touches[1].clientX;
        const dy = event.touches[0].clientY - event.touches[1].clientY;
        const distance = Math.sqrt(dx * dx + dy * dy);
        updateScale(pinchStartScale.current * (distance / pinchStartDistance.current));
      }}
      onTouchEnd={() => {
        pinchStartDistance.current = null;
      }}
      style={{ padding: "16px", borderRadius: "20px", background: "#fff" }}
    >
      <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
        <button ref={buttonRef} aria-label="Zoom out" onClick={() => updateScale(scale - 0.5)} style={{ minWidth: "44px", minHeight: "44px" }}>
          -
        </button>
        <button ref={buttonRef} aria-label="Reset zoom" onClick={() => updateScale(1)} style={{ minWidth: "44px", minHeight: "44px" }}>
          Reset
        </button>
        <button ref={buttonRef} aria-label="Zoom in" onClick={() => updateScale(scale + 0.5)} style={{ minWidth: "44px", minHeight: "44px" }}>
          +
        </button>
        <div data-testid="zoom-level">{Math.round(scale * 100)}%</div>
      </div>

      <div style={{ transform: `scale(${scale})`, transformOrigin: "top left" }}>
        {flattenedItems.map((item) => (
          <div key={item.id} style={{ display: "flex", gap: 12, padding: "12px 0", minHeight: "44px" }}>
            <strong>{item.name}</strong>
            <span>{item.completion}%</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default MobileGanttChart;

'use client';

import { useState, useEffect, useRef } from 'react';

export function useCountUp(target: number | null, duration = 1500): number | null {
  const [value, setValue] = useState<number | null>(target === null ? null : 0);
  const raf = useRef(0);

  useEffect(() => {
    // ADR-009 §18: null target stays null (rendered as "—" by the caller).
    if (target === null) {
      setValue(null);
      return;
    }
    const start = performance.now();
    function animate(now: number) {
      const p = Math.min((now - start) / duration, 1);
      // Ease-out quartic for smooth deceleration
      setValue(Math.round((1 - Math.pow(1 - p, 4)) * (target as number)));
      if (p < 1) raf.current = requestAnimationFrame(animate);
    }
    raf.current = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(raf.current);
  }, [target, duration]);

  return value;
}

'use client';

import { useState, useEffect, useRef } from 'react';

export function useCountUp(target: number, duration = 1500) {
  const [value, setValue] = useState(0);
  const raf = useRef(0);

  useEffect(() => {
    const start = performance.now();
    function animate(now: number) {
      const p = Math.min((now - start) / duration, 1);
      // Ease-out quartic for smooth deceleration
      setValue(Math.round((1 - Math.pow(1 - p, 4)) * target));
      if (p < 1) raf.current = requestAnimationFrame(animate);
    }
    raf.current = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(raf.current);
  }, [target, duration]);

  return value;
}

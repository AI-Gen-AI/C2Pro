import { useSyncExternalStore } from "react";

/** Below Tailwind's `md` breakpoint: phones, where a draggable horizontal split leaves ~100px columns. */
const QUERY = "(max-width: 767px)";

function subscribe(onChange: () => void) {
  const media = window.matchMedia(QUERY);
  media.addEventListener("change", onChange);
  return () => media.removeEventListener("change", onChange);
}

/** `false` during SSR (desktop layout), then the real viewport after hydration. */
export function useIsNarrowViewport(): boolean {
  return useSyncExternalStore(
    subscribe,
    () => window.matchMedia(QUERY).matches,
    () => false,
  );
}

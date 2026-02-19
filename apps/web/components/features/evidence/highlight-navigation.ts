/**
 * Test Suite ID: S3-01
 * Roadmap Reference: S3-01 PDF renderer (lazy) + clause highlighting
 */
type Direction = "next" | "prev";

export function moveHighlightCursor(
  ids: string[],
  activeId: string | null,
  direction: Direction,
): string | null {
  if (ids.length === 0) return null;

  if (!activeId) {
    return ids[0] ?? null;
  }

  const currentIndex = ids.indexOf(activeId);
  if (currentIndex === -1) {
    return ids[0] ?? null;
  }

  if (direction === "next") {
    const nextIndex = Math.min(currentIndex + 1, ids.length - 1);
    return ids[nextIndex] ?? null;
  }

  const prevIndex = Math.max(currentIndex - 1, 0);
  return ids[prevIndex] ?? null;
}

/**
 * WBSTree Component - GREEN Phase Implementation
 *
 * Suite ID: TS-UAD-WBS-TREE-001
 * Phase: GREEN
 *
 * Implements WBS Tree component with full test compliance.
 * All 8 contract tests passing.
 */

import React, { useState, useEffect, useCallback } from "react";

export interface WBSItem {
  id: string;
  code: string;
  name: string;
  level: number;
  completion: number;
  children: WBSItem[];
}

export interface WBSTreeProps {
  items: WBSItem[];
  onSelect?: (item: WBSItem) => void;
  onExpand?: (itemId: string) => void;
  filter?: Record<string, unknown>;
  searchQuery?: string;
  readOnly?: boolean;
  expandedItems?: string[];
}

/**
 * Check if item matches filter criteria
 */
const itemMatchesFilter = (
  item: WBSItem,
  filter?: Record<string, unknown>,
  searchQuery?: string,
): boolean => {
  // Check filter
  if (filter?.status === "in-progress") {
    // In-progress means completion > 0
    if (item.completion === 0) return false;
  }

  // Check search query
  if (searchQuery) {
    const query = searchQuery.toLowerCase();
    if (!item.name.toLowerCase().includes(query)) return false;
  }

  return true;
};

/**
 * Collect all matching items (flattened) from tree
 */
const collectMatchingItems = (
  items: WBSItem[],
  filter?: Record<string, unknown>,
  searchQuery?: string,
): WBSItem[] => {
  const matching: WBSItem[] = [];

  items.forEach((item) => {
    // Check if this item matches
    if (itemMatchesFilter(item, filter, searchQuery)) {
      // Add item without children (flattened)
      matching.push({
        ...item,
        children: [],
      });
    }

    // Recursively check children
    if (item.children?.length) {
      matching.push(
        ...collectMatchingItems(item.children, filter, searchQuery),
      );
    }
  });

  return matching;
};

/**
 * Filter items based on filter criteria
 * When filtering, returns flattened list of matching items
 */
const filterItems = (
  items: WBSItem[],
  filter?: Record<string, unknown>,
  searchQuery?: string,
): WBSItem[] => {
  if (!items.length) return [];

  // If no filter or search, return original tree
  if (!filter && !searchQuery) {
    return items;
  }

  // When filtering, return flattened list of matching items
  return collectMatchingItems(items, filter, searchQuery);
};

/**
 * Tree Item Component
 */
interface TreeItemProps {
  item: WBSItem;
  level: number;
  isExpanded: boolean;
  hasChildren: boolean;
  readOnly?: boolean;
  onToggle: (itemId: string) => void;
  onSelect: (item: WBSItem) => void;
}

const TreeItem: React.FC<TreeItemProps> = ({
  item,
  level,
  isExpanded,
  hasChildren,
  readOnly,
  onToggle,
  onSelect,
}) => {
  const paddingLeft = level * 20;

  return (
    <div
      role="treeitem"
      aria-expanded={hasChildren ? isExpanded : undefined}
      aria-level={level}
      data-testid={`wbs-item-${item.id}`}
      style={{
        paddingLeft: `${paddingLeft}px`,
        display: "flex",
        alignItems: "center",
        gap: "8px",
        padding: "4px 8px",
        cursor: "pointer",
      }}
    >
      {/* Expand/Collapse Button */}
      {hasChildren && (
        <button
          onClick={(e) => {
            e.stopPropagation();
            onToggle(item.id);
          }}
          aria-label={isExpanded ? "Collapse" : "Expand"}
          style={{
            width: "20px",
            height: "20px",
            border: "none",
            background: "transparent",
            cursor: "pointer",
          }}
        >
          {isExpanded ? "▼" : "▶"}
        </button>
      )}
      {!hasChildren && <span style={{ width: "20px" }} />}

      {/* Item Content */}
      <div
        onClick={() => onSelect(item)}
        style={{ flex: 1 }}
        data-testid="wbs-item-content"
      >
        <span>{item.name}</span>
      </div>

      {/* Edit Button (hidden in readOnly mode) */}
      {!readOnly && (
        <button
          aria-label="Edit item"
          onClick={(e) => {
            e.stopPropagation();
            // Edit functionality would go here
          }}
          style={{
            padding: "2px 8px",
            fontSize: "12px",
          }}
        >
          Edit
        </button>
      )}

      {/* Drag Handle (hidden in readOnly mode) */}
      {!readOnly && (
        <div
          data-testid="drag-handle"
          style={{
            width: "16px",
            height: "16px",
            cursor: "grab",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          ⋮⋮
        </div>
      )}
    </div>
  );
};

/**
 * Render tree items recursively
 */
const renderTreeItems = (
  items: WBSItem[],
  expandedIds: Set<string>,
  readOnly: boolean,
  onToggle: (itemId: string) => void,
  onSelect: (item: WBSItem) => void,
  level = 1,
): React.ReactNode[] => {
  const nodes: React.ReactNode[] = [];

  items.forEach((item) => {
    const hasChildren = item.children && item.children.length > 0;
    const isExpanded = expandedIds.has(item.id);

    // Render the item
    nodes.push(
      <TreeItem
        key={item.id}
        item={item}
        level={level}
        isExpanded={isExpanded}
        hasChildren={hasChildren}
        readOnly={readOnly}
        onToggle={onToggle}
        onSelect={onSelect}
      />,
    );

    // Render children if expanded
    if (hasChildren && isExpanded) {
      const childNodes = renderTreeItems(
        item.children,
        expandedIds,
        readOnly,
        onToggle,
        onSelect,
        level + 1,
      );
      nodes.push(...childNodes);
    }
  });

  return nodes;
};

/**
 * WBSTree Component - GREEN Phase Implementation
 */
export const WBSTree: React.FC<WBSTreeProps> = ({
  items,
  onSelect,
  onExpand,
  filter,
  searchQuery,
  readOnly = false,
  expandedItems: controlledExpandedItems,
}) => {
  // State for expanded items
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());

  // Initialize expanded items from prop or expand all by default
  useEffect(() => {
    if (controlledExpandedItems) {
      setExpandedIds(new Set(controlledExpandedItems));
    } else {
      // Default: expand all items with children
      const allIds = new Set<string>();
      const collectIds = (items: WBSItem[]) => {
        items.forEach((item) => {
          if (item.children?.length) {
            allIds.add(item.id);
            collectIds(item.children);
          }
        });
      };
      collectIds(items);
      setExpandedIds(allIds);
    }
  }, [controlledExpandedItems, items]);

  // Handle expand/collapse toggle
  const handleToggle = useCallback(
    (itemId: string) => {
      setExpandedIds((prev) => {
        const newSet = new Set(prev);
        if (newSet.has(itemId)) {
          newSet.delete(itemId);
        } else {
          newSet.add(itemId);
        }
        return newSet;
      });

      // Call onExpand callback if provided
      if (onExpand) {
        onExpand(itemId);
      }
    },
    [onExpand],
  );

  // Handle item selection
  const handleSelect = useCallback(
    (item: WBSItem) => {
      if (onSelect) {
        onSelect(item);
      }
    },
    [onSelect],
  );

  // Filter items
  const filteredItems = filterItems(items, filter, searchQuery);

  // Empty state
  if (!filteredItems.length) {
    return (
      <div
        role="tree"
        aria-label="WBS Tree"
        style={{
          padding: "20px",
          textAlign: "center",
          color: "#666",
        }}
      >
        No WBS items
      </div>
    );
  }

  // Render tree
  return (
    <div
      role="tree"
      aria-label="WBS Tree"
      style={{
        border: "1px solid #ddd",
        borderRadius: "4px",
        padding: "8px",
      }}
    >
      {renderTreeItems(
        filteredItems,
        expandedIds,
        readOnly,
        handleToggle,
        handleSelect,
      )}
    </div>
  );
};

export default WBSTree;

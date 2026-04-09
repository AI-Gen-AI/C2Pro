/**
 * WBSTree Component
 *
 * TASK-FRT-164: WBS Tree UI Component
 * Implements hierarchical tree with expand/collapse
 *
 * Suite ID: TS-UAD-WBS-TREE-001
 */

import React, { useState, useEffect, useCallback } from "react";

export interface WBSItem {
  id: string;
  code: string;
  name: string;
  level: number;
  completion: number;
  status?: string;
  budgetAllocated?: number;
  budgetSpent?: number;
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
  selectedItemId?: string;
}

/**
 * Check if item matches filter criteria
 */
const itemMatchesFilter = (
  item: WBSItem,
  filter?: Record<string, unknown>,
  searchQuery?: string,
): boolean => {
  if (filter?.status === "in-progress") {
    if (item.completion === 0) return false;
  }
  if (searchQuery) {
    const query = searchQuery.toLowerCase();
    if (!item.name.toLowerCase().includes(query)) return false;
  }
  return true;
};

const collectMatchingItems = (
  items: WBSItem[],
  filter?: Record<string, unknown>,
  searchQuery?: string,
): WBSItem[] => {
  const matching: WBSItem[] = [];
  items.forEach((item) => {
    if (itemMatchesFilter(item, filter, searchQuery)) {
      matching.push({ ...item, children: [] });
    }
    if (item.children?.length) {
      matching.push(
        ...collectMatchingItems(item.children, filter, searchQuery),
      );
    }
  });
  return matching;
};

const filterItems = (
  items: WBSItem[],
  filter?: Record<string, unknown>,
  searchQuery?: string,
): WBSItem[] => {
  if (!items.length) return [];
  if (!filter && !searchQuery) return items;
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
  selected: boolean;
  onToggle: (itemId: string) => void;
  onSelect: (item: WBSItem) => void;
}

const TreeItem: React.FC<TreeItemProps> = ({
  item,
  level,
  isExpanded,
  hasChildren,
  selected,
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
        backgroundColor: selected ? "#e0e7ff" : "transparent",
        borderRadius: "4px",
      }}
    >
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

      <div
        onClick={() => onSelect(item)}
        style={{ flex: 1 }}
        data-testid="wbs-item-content"
      >
        <span style={{ fontWeight: selected ? 600 : 400 }}>
          {item.code} - {item.name}
        </span>
        <span style={{ marginLeft: "8px", fontSize: "12px", color: "#666" }}>
          {item.completion}%
        </span>
      </div>
    </div>
  );
};

/**
 * Render tree items recursively
 */
const renderTreeItems = (
  items: WBSItem[],
  expandedIds: Set<string>,
  selectedItemId: string | undefined,
  onToggle: (itemId: string) => void,
  onSelect: (item: WBSItem) => void,
  level = 1,
): React.ReactNode[] => {
  const nodes: React.ReactNode[] = [];

  items.forEach((item) => {
    const hasChildren = item.children && item.children.length > 0;
    const isExpanded = expandedIds.has(item.id);

    nodes.push(
      <TreeItem
        key={item.id}
        item={item}
        level={level}
        isExpanded={isExpanded}
        hasChildren={hasChildren}
        selected={selectedItemId === item.id}
        onToggle={onToggle}
        onSelect={onSelect}
      />,
    );

    if (hasChildren && isExpanded) {
      nodes.push(
        ...renderTreeItems(
          item.children,
          expandedIds,
          selectedItemId,
          onToggle,
          onSelect,
          level + 1,
        ),
      );
    }
  });

  return nodes;
};

/**
 * WBSTree Component
 */
export const WBSTree: React.FC<WBSTreeProps> = ({
  items,
  onSelect,
  onExpand,
  filter,
  searchQuery,
  readOnly = false,
  expandedItems: controlledExpandedItems,
  selectedItemId,
}) => {
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());

  useEffect(() => {
    if (controlledExpandedItems) {
      setExpandedIds(new Set(controlledExpandedItems));
    } else {
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
      if (onExpand) onExpand(itemId);
    },
    [onExpand],
  );

  const handleSelect = useCallback(
    (item: WBSItem) => {
      if (onSelect) onSelect(item);
    },
    [onSelect],
  );

  const filteredItems = filterItems(items, filter, searchQuery);

  if (!filteredItems.length) {
    return (
      <div
        role="tree"
        aria-label="WBS Tree"
        style={{
          padding: "20px",
          textAlign: "center",
          color: "#666",
          border: "1px solid #ddd",
          borderRadius: "4px",
        }}
      >
        No WBS items
      </div>
    );
  }

  return (
    <div
      role="tree"
      aria-label="WBS Tree"
      style={{
        border: "1px solid #ddd",
        borderRadius: "4px",
        padding: "8px",
        minHeight: "200px",
      }}
    >
      {renderTreeItems(
        filteredItems,
        expandedIds,
        selectedItemId,
        handleToggle,
        handleSelect,
      )}
    </div>
  );
};

export default WBSTree;

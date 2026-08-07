/**
 * WBS Page - Work Breakdown Structure View
 *
 * TASK-FRT-164: WBS Tree UI Component
 * Implements hierarchical tree with drag-drop support via page-level DnD
 *
 * Test Suite ID: TASK-1427
 */

"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { env } from "@/config/env";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  ChevronRight,
  ChevronDown,
  Edit2,
  Plus,
  Expand,
  Loader2,
  GripVertical,
} from "lucide-react";
import { useWBSTree, type WBSTreeItem } from "@/hooks/useWBSTree";

interface WBSTreeRowProps {
  item: WBSTreeItem;
  level?: number;
  expandedItems: Set<string>;
  onToggleExpand: (id: string) => void;
  onEdit: (item: WBSTreeItem) => void;
  readOnly?: boolean;
}

function WBSTreeRow({
  item,
  level = 0,
  expandedItems,
  onToggleExpand,
  onEdit,
  readOnly = false,
}: WBSTreeRowProps) {
  const isExpanded = expandedItems.has(item.id);
  const hasChildren = item.children && item.children.length > 0;

  // Determine status color
  const getStatusColor = (completion: number) => {
    if (completion >= 100) return "bg-green-500";
    if (completion >= 50) return "bg-blue-500";
    if (completion > 0) return "bg-yellow-500";
    return "bg-gray-400";
  };

  return (
    <div>
      <div
        className="group flex items-center gap-2 py-2 hover:bg-muted/50"
        style={{ paddingLeft: `${level * 24}px` }}
        data-testid={`wbs-item-${item.id}`}
        draggable={!readOnly}
        onDragStart={(e) => {
          if (!readOnly) {
            e.dataTransfer.setData("text/plain", item.id);
            e.dataTransfer.effectAllowed = "move";
          }
        }}
      >
        {!readOnly && (
          <GripVertical className="h-4 w-4 cursor-grab text-muted-foreground opacity-0 group-hover:opacity-100" />
        )}

        {hasChildren ? (
          <button
            onClick={() => onToggleExpand(item.id)}
            className="rounded p-1 hover:bg-muted"
            data-testid={`wbs-expand-${item.id}`}
          >
            {isExpanded ? (
              <ChevronDown className="h-4 w-4" />
            ) : (
              <ChevronRight className="h-4 w-4" />
            )}
          </button>
        ) : (
          <span className="w-6" />
        )}

        <span
          className="w-20 font-mono text-sm text-muted-foreground"
          data-testid={`wbs-item-code-${item.code}`}
        >
          {item.code}
        </span>

        <div className="flex flex-1 items-center gap-2">
          <span className="font-medium">{item.name}</span>
          {item.status && (
            <span
              className={`rounded px-1.5 py-0.5 text-xs font-medium text-white ${getStatusColor(item.completion)}`}
            >
              {item.status}
            </span>
          )}
        </div>

        <div className="flex w-48 items-center gap-4">
          <Progress value={item.completion} className="h-2 flex-1" />
          <span
            className="w-12 text-right text-sm text-muted-foreground"
            data-testid={`wbs-item-${item.id}-completion`}
          >
            {item.completion}%
          </span>
        </div>

        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8"
          data-testid={`wbs-edit-${item.id}`}
          onClick={() => onEdit(item)}
        >
          <Edit2 className="h-4 w-4" />
        </Button>
      </div>

      {isExpanded &&
        item.children?.map((child) => (
          <WBSTreeRow
            key={child.id}
            item={child}
            level={level + 1}
            expandedItems={expandedItems}
            onToggleExpand={onToggleExpand}
            onEdit={onEdit}
            readOnly={readOnly}
          />
        ))}
    </div>
  );
}

export default function ProjectWBSPage() {
  const router = useRouter();
  const params = useParams();
  const projectId = params.id as string;

  useEffect(() => {
    if (!env.FEATURE_PHASE2_MODULES) {
      router.replace(`/projects/${projectId}`);
    }
  }, [router, projectId]);

  const {
    items,
    isLoading,
    isError,
    error,
    updateItem,
    createItem,
    deleteItem, // eslint-disable-line @typescript-eslint/no-unused-vars -- Phase 2: delete WBS item
    moveItem,
    expandedItems,
    toggleExpanded,
    expandAll,
    collapseAll, // eslint-disable-line @typescript-eslint/no-unused-vars -- Phase 2: collapse all button
  } = useWBSTree({ projectId });

  const [editModalOpen, setEditModalOpen] = useState(false);
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [selectedEditItem, setSelectedEditItem] = useState<WBSTreeItem | null>(
    null,
  );
  const [completionInput, setCompletionInput] = useState("");
  const [completionNote, setCompletionNote] = useState("");
  const [showSuccessToast, setShowSuccessToast] = useState(false);
  const [newItemName, setNewItemName] = useState("");
  const [newItemCode, setNewItemCode] = useState("");
  const [dragOverId, setDragOverId] = useState<string | null>(null);

  if (!env.FEATURE_PHASE2_MODULES) return null;

  const handleEdit = (item: WBSTreeItem) => {
    setSelectedEditItem(item);
    setCompletionInput(item.completion.toString());
    setCompletionNote("");
    setEditModalOpen(true);
  };

  const handleSave = async () => {
    if (selectedEditItem) {
      const success = await updateItem(selectedEditItem.id, {
        completion: parseInt(completionInput, 10),
      });
      if (success) {
        setShowSuccessToast(true);
        setTimeout(() => setShowSuccessToast(false), 3000);
      }
    }
    setEditModalOpen(false);
  };

  const handleCreate = async () => {
    if (newItemName && newItemCode) {
      const success = await createItem({
        code: newItemCode,
        name: newItemName,
      });
      if (success) {
        setShowSuccessToast(true);
        setTimeout(() => setShowSuccessToast(false), 3000);
      }
    }
    setCreateModalOpen(false);
    setNewItemName("");
    setNewItemCode("");
  };

  const handleDragOver = (e: React.DragEvent, itemId: string) => {
    e.preventDefault();
    setDragOverId(itemId);
  };

  const handleDragLeave = () => {
    setDragOverId(null);
  };

  const handleDrop = async (e: React.DragEvent, targetItem: WBSTreeItem) => {
    e.preventDefault();
    const draggedId = e.dataTransfer.getData("text/plain");
    if (draggedId && draggedId !== targetItem.id) {
      await moveItem(draggedId, targetItem.id);
    }
    setDragOverId(null);
  };

  if (isLoading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (isError) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-4">
        <p className="text-red-800">Failed to load WBS: {error?.message}</p>
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="wbs-tree-view">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Work Breakdown Structure</h1>
          <p className="text-muted-foreground">
            View and manage project WBS items and track completion
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            onClick={expandAll}
            data-testid="wbs-expand-all-button"
          >
            <Expand className="mr-2 h-4 w-4" />
            Expand All
          </Button>
          <Button onClick={() => setCreateModalOpen(true)}>
            <Plus className="mr-2 h-4 w-4" />
            Add Item
          </Button>
        </div>
      </div>

      {showSuccessToast ? (
        <div
          className="rounded-lg bg-green-100 p-4 text-green-800"
          data-testid="success-toast"
        >
          <p className="font-medium">Operation completed successfully</p>
        </div>
      ) : null}

      <Card data-testid="wbs-tree">
        <CardHeader>
          <CardTitle>Project Structure</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {items.length > 0 ? (
            items.map((item) => (
              <div
                key={item.id}
                onDragOver={(e) => handleDragOver(e, item.id)}
                onDragLeave={handleDragLeave}
                onDrop={(e) => handleDrop(e, item)}
                className={dragOverId === item.id ? "bg-blue-50" : ""}
              >
                <WBSTreeRow
                  item={item}
                  expandedItems={expandedItems}
                  onToggleExpand={toggleExpanded}
                  onEdit={handleEdit}
                />
              </div>
            ))
          ) : (
            <div className="py-8 text-center text-muted-foreground">
              No WBS items yet. Click "Add Item" to create one.
            </div>
          )}
        </CardContent>
      </Card>

      {/* Edit Dialog */}
      <Dialog open={editModalOpen} onOpenChange={setEditModalOpen}>
        <DialogContent data-testid="wbs-edit-modal">
          <DialogHeader>
            <DialogTitle>Edit WBS Progress</DialogTitle>
            <DialogDescription>
              Update completion for {selectedEditItem?.code}{" "}
              {selectedEditItem?.name}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium" htmlFor="completion-input">
                Completion Percentage
              </label>
              <Input
                id="completion-input"
                data-testid="completion-input"
                type="number"
                min="0"
                max="100"
                value={completionInput}
                onChange={(event) => setCompletionInput(event.target.value)}
              />
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium" htmlFor="completion-note">
                Progress Note
              </label>
              <Textarea
                id="completion-note"
                data-testid="completion-note"
                value={completionNote}
                onChange={(event) => setCompletionNote(event.target.value)}
              />
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setEditModalOpen(false)}>
              Cancel
            </Button>
            <Button data-testid="save-wbs-changes" onClick={handleSave}>
              Save
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Create Dialog */}
      <Dialog open={createModalOpen} onOpenChange={setCreateModalOpen}>
        <DialogContent data-testid="wbs-create-modal">
          <DialogHeader>
            <DialogTitle>Add WBS Item</DialogTitle>
            <DialogDescription>
              Create a new item in the Work Breakdown Structure
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium" htmlFor="new-item-code">
                WBS Code
              </label>
              <Input
                id="new-item-code"
                data-testid="new-item-code"
                placeholder="e.g., 1.1.1"
                value={newItemCode}
                onChange={(event) => setNewItemCode(event.target.value)}
              />
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium" htmlFor="new-item-name">
                Name
              </label>
              <Input
                id="new-item-name"
                data-testid="new-item-name"
                placeholder="Task name"
                value={newItemName}
                onChange={(event) => setNewItemName(event.target.value)}
              />
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateModalOpen(false)}>
              Cancel
            </Button>
            <Button data-testid="create-wbs-item" onClick={handleCreate}>
              Create
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

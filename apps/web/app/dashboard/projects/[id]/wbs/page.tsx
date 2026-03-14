"use client";

import { useState } from "react";
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
} from "lucide-react";

interface WBSItem {
  id: string;
  code: string;
  name: string;
  completion: number;
  children?: WBSItem[];
}

const mockWBS: WBSItem[] = [
  {
    id: "1",
    code: "1",
    name: "Project Management",
    completion: 75,
    children: [
      {
        id: "1.1",
        code: "1.1",
        name: "Planning",
        completion: 100,
      },
      {
        id: "1.2",
        code: "1.2",
        name: "Monitoring & Control",
        completion: 50,
      },
    ],
  },
  {
    id: "2",
    code: "2",
    name: "Construction",
    completion: 45,
    children: [
      {
        id: "2.1",
        code: "2.1",
        name: "Foundation Work",
        completion: 80,
      },
      {
        id: "2.2",
        code: "2.2",
        name: "Structural Work",
        completion: 20,
      },
    ],
  },
  {
    id: "3",
    code: "3",
    name: "Finishing",
    completion: 10,
    children: [
      {
        id: "3.1",
        code: "3.1",
        name: "Interior Work",
        completion: 5,
      },
    ],
  },
];

function WBSItemRow({
  item,
  level = 0,
  expandedItems,
  onToggleExpand,
  onEdit,
}: {
  item: WBSItem;
  level?: number;
  expandedItems: Set<string>;
  onToggleExpand: (id: string) => void;
  onEdit: (item: WBSItem) => void;
}) {
  const isExpanded = expandedItems.has(item.id);
  const hasChildren = item.children && item.children.length > 0;

  return (
    <div>
      <div
        className="flex items-center gap-2 py-2 hover:bg-muted/50"
        style={{ paddingLeft: `${level * 24}px` }}
        data-testid={`wbs-item-${item.id}`}
      >
        {hasChildren ? (
          <button
            onClick={() => onToggleExpand(item.id)}
            className="p-1 hover:bg-muted rounded"
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
          className="font-mono text-sm text-muted-foreground w-16"
          data-testid={`wbs-item-code-${item.code}`}
        >
          {item.code}
        </span>

        <span className="flex-1 font-medium">{item.name}</span>

        <div className="flex items-center gap-4 w-48">
          <Progress value={item.completion} className="h-2 flex-1" />
          <span
            className="text-sm text-muted-foreground w-12 text-right"
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
          <WBSItemRow
            key={child.id}
            item={child}
            level={level + 1}
            expandedItems={expandedItems}
            onToggleExpand={onToggleExpand}
            onEdit={onEdit}
          />
        ))}
    </div>
  );
}

export default function WBSPage() {
  const [expandedItems, setExpandedItems] = useState<Set<string>>(new Set());
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [selectedItem, setSelectedItem] = useState<WBSItem | null>(null);
  const [completionInput, setCompletionInput] = useState("");
  const [completionNote, setCompletionNote] = useState("");
  const [showSuccessToast, setShowSuccessToast] = useState(false);

  const toggleExpand = (id: string) => {
    setExpandedItems((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(id)) {
        newSet.delete(id);
      } else {
        newSet.add(id);
      }
      return newSet;
    });
  };

  const expandAll = () => {
    const allIds = new Set<string>();
    const collectIds = (items: WBSItem[]) => {
      items.forEach((item) => {
        allIds.add(item.id);
        if (item.children) {
          collectIds(item.children);
        }
      });
    };
    collectIds(mockWBS);
    setExpandedItems(allIds);
  };

  const handleEdit = (item: WBSItem) => {
    setSelectedItem(item);
    setCompletionInput(item.completion.toString());
    setCompletionNote("");
    setEditModalOpen(true);
  };

  const handleSave = () => {
    // In real implementation, this would call an API
    setEditModalOpen(false);
    setShowSuccessToast(true);
    setTimeout(() => setShowSuccessToast(false), 3000);
  };

  return (
    <div className="space-y-6" data-testid="wbs-tree-view">
      {/* Header */}
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
          <Button>
            <Plus className="mr-2 h-4 w-4" />
            Add Item
          </Button>
        </div>
      </div>

      {/* Success Toast */}
      {showSuccessToast && (
        <div
          className="rounded-lg bg-green-100 p-4 text-green-800"
          data-testid="success-toast"
        >
          <p className="font-medium">Progress updated successfully</p>
        </div>
      )}

      {/* WBS Tree */}
      <Card data-testid="wbs-tree">
        <CardHeader>
          <CardTitle>WBS Items</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="border-b pb-2 mb-2 flex items-center gap-2 text-sm text-muted-foreground">
            <span className="w-6" />
            <span className="w-16">Code</span>
            <span className="flex-1">Name</span>
            <span className="w-48">Progress</span>
            <span className="w-8" />
          </div>
          {mockWBS.map((item) => (
            <WBSItemRow
              key={item.id}
              item={item}
              expandedItems={expandedItems}
              onToggleExpand={toggleExpand}
              onEdit={handleEdit}
            />
          ))}
        </CardContent>
      </Card>

      {/* Edit Modal */}
      <Dialog open={editModalOpen} onOpenChange={setEditModalOpen}>
        <DialogContent data-testid="wbs-edit-modal">
          <DialogHeader>
            <DialogTitle>Update WBS Item Progress</DialogTitle>
            <DialogDescription>
              Update completion percentage for {selectedItem?.name}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">Completion (%)</label>
              <Input
                type="number"
                min="0"
                max="100"
                value={completionInput}
                onChange={(e) => setCompletionInput(e.target.value)}
                data-testid="completion-input"
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Note</label>
              <Textarea
                placeholder="Add a note about this update..."
                value={completionNote}
                onChange={(e) => setCompletionNote(e.target.value)}
                data-testid="completion-note"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditModalOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleSave} data-testid="save-wbs-changes">
              Save Changes
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

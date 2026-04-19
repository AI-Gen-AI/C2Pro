/**
 * Budget Page - Budget Dashboard UI
 *
 * TASK-FRT-165: Budget Dashboard UI
 * Implements budget overview with category breakdown, variance charts,
 * budget item CRUD, approval workflow UI, export to Excel/PDF
 *
 * Test Suite ID: TASK-1487
 */

"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
// eslint-disable-next-line @typescript-eslint/no-unused-vars
import { Progress } from "@/components/ui/progress"; // Phase 2: budget progress bars
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
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
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  AlertTriangle,
  DollarSign,
  TrendingDown,
  TrendingUp,
  Plus,
  Pencil,
  Trash2,
  Download,
  Loader2,
} from "lucide-react";
import {
  useBudget,
  calculateCategoryBreakdown,
  calculateVarianceData,
} from "@/hooks/useBudget";

type BudgetItem = {
  id: string;
  name: string;
  category: string;
  amount: number;
  actualAmount?: number;
  variance?: number;
  description?: string;
  status: string;
};

function readNumber(
  data: Record<string, unknown> | undefined,
  ...keys: string[]
) {
  for (const key of keys) {
    const value = data?.[key];
    if (typeof value === "number") return value;
    if (typeof value === "string" && value.trim()) {
      const parsed = Number(value);
      if (!Number.isNaN(parsed)) return parsed;
    }
  }
  return 0;
}

function readString(
  data: Record<string, unknown> | undefined,
  ...keys: string[]
) {
  for (const key of keys) {
    const value = data?.[key];
    if (typeof value === "string" && value.trim()) return value;
  }
  return "";
}

export default function ProjectBudgetPage() {
  const params = useParams<{ id: string }>();
  const projectId = params.id;

  const {
    budget,
    isLoading,
    isError,
    error,
    createItem,
    updateItem,
    deleteItem,
    selectedItem,
    setSelectedItem,
  } = useBudget({ projectId });

  const [editModalOpen, setEditModalOpen] = useState(false);
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [formData, setFormData] = useState({
    name: "",
    category: "materials",
    amount: 0,
    actualAmount: 0,
    description: "",
    status: "planned",
  });

  const handleEdit = (item: BudgetItem) => {
    setSelectedItem(item);
    setFormData({
      name: item.name,
      category: item.category,
      amount: item.amount,
      actualAmount: item.actualAmount ?? 0,
      description: item.description ?? "",
      status: item.status,
    });
    setEditModalOpen(true);
  };

  const handleSave = async () => {
    if (selectedItem) {
      await updateItem(selectedItem.id, formData);
    }
    setEditModalOpen(false);
    setSelectedItem(null);
  };

  const handleCreate = async () => {
    await createItem(formData);
    setCreateModalOpen(false);
    setFormData({
      name: "",
      category: "materials",
      amount: 0,
      actualAmount: 0,
      description: "",
      status: "planned",
    });
  };

  const handleDelete = async (itemId: string) => {
    if (confirm("Are you sure you want to delete this budget item?")) {
      await deleteItem(itemId);
    }
  };

  const exportToExcel = () => {
    if (!budget?.items) return;
    const csvContent = [
      ["Name", "Category", "Planned", "Actual", "Variance", "Status"].join(","),
      ...budget.items.map((item) =>
        [
          item.name,
          item.category,
          item.amount,
          item.actualAmount ?? "",
          item.variance ?? "",
          item.status,
        ].join(","),
      ),
    ].join("\n");

    const blob = new Blob([csvContent], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `budget-${projectId}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const exportToPDF = () => {
    alert("PDF export - implement with jsPDF or similar");
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-24">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (isError) {
    return (
      <div className="flex items-center justify-center py-24 text-destructive">
        {error instanceof Error ? error.message : "Failed to load budget"}
      </div>
    );
  }

  const data = (budget ?? {}) as Record<string, unknown>;
  const totalBudget = readNumber(data, "total_budget", "totalBudget");
  const spentAmount = readNumber(data, "spent_amount", "spent");
  const utilization = readNumber(data, "utilization_percentage", "utilization");
  const varianceStatus = readString(data, "variance_status", "variance");
  const currency = readString(data, "currency") || "EUR";
  const items = (data.items as BudgetItem[]) ?? [];

  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const remainingBudget = Math.max(totalBudget - spentAmount, 0); // Phase 2: variance display
  const safeUtilization =
    utilization > 0
      ? utilization
      : totalBudget > 0
        ? Math.round((spentAmount / totalBudget) * 100)
        : 0;

  const formatCurrency = (amount: number) =>
    new Intl.NumberFormat("en-US", {
      style: "currency",
      currency,
      maximumFractionDigits: 0,
    }).format(amount);

  const categoryBreakdown = calculateCategoryBreakdown(items);
  const varianceData = calculateVarianceData(items);

  const getStatusColor = (status: string) => {
    switch (status) {
      case "approved":
        return "bg-green-500";
      case "pending":
        return "bg-yellow-500";
      case "rejected":
        return "bg-red-500";
      default:
        return "bg-gray-400";
    }
  };

  return (
    <div className="space-y-6" data-testid="budget-page">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Budget Overview</h1>
          <p className="text-muted-foreground">
            Track budget utilization and manage budget items
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={exportToExcel}>
            <Download className="mr-2 h-4 w-4" />
            Export CSV
          </Button>
          <Button variant="outline" onClick={exportToPDF}>
            <Download className="mr-2 h-4 w-4" />
            Export PDF
          </Button>
          <Button onClick={() => setCreateModalOpen(true)}>
            <Plus className="mr-2 h-4 w-4" />
            Add Item
          </Button>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card data-testid="total-budget">
          <CardContent className="pt-6">
            <div className="flex items-center gap-2">
              <DollarSign className="h-5 w-5 text-muted-foreground" />
              <span className="text-sm text-muted-foreground">
                Total Budget
              </span>
            </div>
            <p className="mt-2 text-2xl font-bold">
              {formatCurrency(totalBudget)}
            </p>
          </CardContent>
        </Card>

        <Card data-testid="spent-amount">
          <CardContent className="pt-6">
            <div className="flex items-center gap-2">
              <TrendingUp className="h-5 w-5 text-muted-foreground" />
              <span className="text-sm text-muted-foreground">Spent</span>
            </div>
            <p className="mt-2 text-2xl font-bold">
              {formatCurrency(spentAmount)}
            </p>
          </CardContent>
        </Card>

        <Card data-testid="budget-utilization">
          <CardContent className="pt-6">
            <div className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-muted-foreground" />
              <span className="text-sm text-muted-foreground">Utilization</span>
            </div>
            <p className="mt-2 text-2xl font-bold">{safeUtilization}%</p>
          </CardContent>
        </Card>

        <Card data-testid="budget-variance">
          <CardContent className="pt-6">
            <div className="flex items-center gap-2">
              <TrendingDown className="h-5 w-5 text-muted-foreground" />
              <span className="text-sm text-muted-foreground">Status</span>
            </div>
            <p className="mt-2 text-2xl font-bold capitalize">
              {varianceStatus || "Unknown"}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Category Breakdown */}
      {categoryBreakdown.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Category Breakdown</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid gap-4 md:grid-cols-3">
              {categoryBreakdown.map((cat) => (
                <div key={cat.name} className="rounded-lg border p-4">
                  <div className="text-sm font-medium text-muted-foreground capitalize">
                    {cat.name}
                  </div>
                  <div className="mt-2 flex items-baseline gap-2">
                    <span className="text-xl font-bold">
                      {formatCurrency(cat.planned)}
                    </span>
                    <span className="text-sm text-muted-foreground">
                      planned
                    </span>
                  </div>
                  <div className="mt-1 text-sm text-muted-foreground">
                    {formatCurrency(cat.actual)} actual
                  </div>
                  <div
                    className={`mt-2 text-sm ${cat.variance >= 0 ? "text-green-600" : "text-red-600"}`}
                  >
                    {cat.variance >= 0 ? "+" : ""}
                    {formatCurrency(cat.variance)} variance
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Variance Chart */}
      {varianceData.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Planned vs Actual</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {varianceData.slice(0, 10).map((item) => (
                <div key={item.name} className="flex items-center gap-4">
                  <span className="w-32 truncate text-sm">{item.name}</span>
                  <div className="flex-1">
                    <div className="flex justify-between text-xs text-muted-foreground">
                      <span>Planned: {formatCurrency(item.planned)}</span>
                      <span>Actual: {formatCurrency(item.actual)}</span>
                    </div>
                    <div className="mt-1 h-2 rounded-full bg-muted overflow-hidden flex">
                      <div
                        className="bg-blue-500"
                        style={{
                          width: `${(item.planned / totalBudget) * 100}%`,
                        }}
                      />
                      <div
                        className="bg-orange-500"
                        style={{
                          width: `${(item.actual / totalBudget) * 100}%`,
                        }}
                      />
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Budget Items Table */}
      <Card>
        <CardHeader>
          <CardTitle>Budget Items</CardTitle>
        </CardHeader>
        <CardContent>
          {items.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Category</TableHead>
                  <TableHead className="text-right">Planned</TableHead>
                  <TableHead className="text-right">Actual</TableHead>
                  <TableHead className="text-right">Variance</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="w-24">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((item) => (
                  <TableRow key={item.id}>
                    <TableCell className="font-medium">{item.name}</TableCell>
                    <TableCell className="capitalize">
                      {item.category}
                    </TableCell>
                    <TableCell className="text-right">
                      {formatCurrency(item.amount)}
                    </TableCell>
                    <TableCell className="text-right">
                      {item.actualAmount != null
                        ? formatCurrency(item.actualAmount)
                        : "-"}
                    </TableCell>
                    <TableCell
                      className={`text-right ${(item.variance ?? 0) >= 0 ? "text-green-600" : "text-red-600"}`}
                    >
                      {item.variance != null
                        ? formatCurrency(item.variance)
                        : "-"}
                    </TableCell>
                    <TableCell>
                      <Badge className={getStatusColor(item.status)}>
                        {item.status}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <div className="flex gap-1">
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => handleEdit(item)}
                        >
                          <Pencil className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => handleDelete(item.id)}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <div className="py-8 text-center text-muted-foreground">
              No budget items yet. Click "Add Item" to create one.
            </div>
          )}
        </CardContent>
      </Card>

      {/* Edit Dialog */}
      <Dialog open={editModalOpen} onOpenChange={setEditModalOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Edit Budget Item</DialogTitle>
            <DialogDescription>Update budget item details</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">Name</label>
              <Input
                value={formData.name}
                onChange={(e) =>
                  setFormData({ ...formData, name: e.target.value })
                }
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Category</label>
              <Select
                value={formData.category}
                onValueChange={(value) =>
                  setFormData({ ...formData, category: value })
                }
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="materials">Materials</SelectItem>
                  <SelectItem value="labor">Labor</SelectItem>
                  <SelectItem value="equipment">Equipment</SelectItem>
                  <SelectItem value="subcontract">Subcontract</SelectItem>
                  <SelectItem value="other">Other</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <label className="text-sm font-medium">Planned Amount</label>
                <Input
                  type="number"
                  value={formData.amount}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      amount: parseFloat(e.target.value) || 0,
                    })
                  }
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">Actual Amount</label>
                <Input
                  type="number"
                  value={formData.actualAmount}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      actualAmount: parseFloat(e.target.value) || 0,
                    })
                  }
                />
              </div>
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Description</label>
              <Textarea
                value={formData.description}
                onChange={(e) =>
                  setFormData({ ...formData, description: e.target.value })
                }
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditModalOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleSave}>Save</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Create Dialog */}
      <Dialog open={createModalOpen} onOpenChange={setCreateModalOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add Budget Item</DialogTitle>
            <DialogDescription>Create a new budget item</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">Name</label>
              <Input
                value={formData.name}
                onChange={(e) =>
                  setFormData({ ...formData, name: e.target.value })
                }
                placeholder="Item name"
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Category</label>
              <Select
                value={formData.category}
                onValueChange={(value) =>
                  setFormData({ ...formData, category: value })
                }
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="materials">Materials</SelectItem>
                  <SelectItem value="labor">Labor</SelectItem>
                  <SelectItem value="equipment">Equipment</SelectItem>
                  <SelectItem value="subcontract">Subcontract</SelectItem>
                  <SelectItem value="other">Other</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Amount</label>
              <Input
                type="number"
                value={formData.amount || ""}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    amount: parseFloat(e.target.value) || 0,
                  })
                }
                placeholder="0"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateModalOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleCreate}>Create</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

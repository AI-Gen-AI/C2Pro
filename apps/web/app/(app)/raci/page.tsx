"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Search, Download } from "lucide-react";

import { demoRaciData, raciTypes } from "@/lib/demo-data/raci";

export default function RaciPage() {
  const [searchQuery, setSearchQuery] = useState("");
  const [projectFilter, setProjectFilter] = useState("all");

  const filteredData = demoRaciData.filter((row) =>
    row.activity.toLowerCase().includes(searchQuery.toLowerCase()),
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">RACI Matrix</h1>
          <p className="text-muted-foreground">
            Define roles and responsibilities for project activities
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline">
            <Download className="mr-2 h-4 w-4" />
            Export
          </Button>
          <Button>+ Add Activity</Button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-4">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search activities..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-9"
          />
        </div>
        <Select value={projectFilter} onValueChange={setProjectFilter}>
          <SelectTrigger className="w-[200px]">
            <SelectValue placeholder="All Projects" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Projects</SelectItem>
            <SelectItem value="proj1">Petrochemical Plant EPC</SelectItem>
            <SelectItem value="proj2">Refinery Modernization</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Legend */}
      <div className="flex items-center gap-4 rounded-lg border bg-card p-4">
        <span className="text-sm font-medium">Legend:</span>
        {Object.entries(raciTypes).map(([key, { label, color }]) => (
          <div key={key} className="flex items-center gap-2">
            <Badge className={color}>{key}</Badge>
            <span className="text-sm text-muted-foreground">{label}</span>
          </div>
        ))}
      </div>

      {/* RACI Matrix Table */}
      <div className="rounded-lg border bg-card">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="border-b bg-muted/50">
              <tr>
                <th className="px-4 py-3 text-left text-sm font-medium">
                  Activity
                </th>
                <th className="px-4 py-3 text-center text-sm font-medium">
                  Project Manager
                </th>
                <th className="px-4 py-3 text-center text-sm font-medium">
                  Technical Lead
                </th>
                <th className="px-4 py-3 text-center text-sm font-medium">
                  Stakeholder
                </th>
                <th className="px-4 py-3 text-center text-sm font-medium">
                  Contractor
                </th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {filteredData.map((row, index) => (
                <tr key={index} className="hover:bg-muted/50 transition-colors">
                  <td className="px-4 py-3 font-medium">{row.activity}</td>
                  <td className="px-4 py-3 text-center">
                    <Badge
                      className={
                        raciTypes[row.projectManager as keyof typeof raciTypes]
                          .color
                      }
                    >
                      {row.projectManager}
                    </Badge>
                  </td>
                  <td className="px-4 py-3 text-center">
                    <Badge
                      className={
                        raciTypes[row.technicalLead as keyof typeof raciTypes]
                          .color
                      }
                    >
                      {row.technicalLead}
                    </Badge>
                  </td>
                  <td className="px-4 py-3 text-center">
                    <Badge
                      className={
                        raciTypes[row.stakeholder as keyof typeof raciTypes]
                          .color
                      }
                    >
                      {row.stakeholder}
                    </Badge>
                  </td>
                  <td className="px-4 py-3 text-center">
                    <Badge
                      className={
                        raciTypes[row.contractor as keyof typeof raciTypes]
                          .color
                      }
                    >
                      {row.contractor}
                    </Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

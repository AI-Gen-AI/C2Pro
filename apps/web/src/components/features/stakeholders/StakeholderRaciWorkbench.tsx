/**
 * Test Suite ID: S3-07
 * Roadmap Reference: S3-07 Severity badge + Stakeholder Map + RACI
 */
"use client";

import { useMemo, useState } from "react";
import { SeverityBadge } from "@/src/components/features/stakeholders/SeverityBadge";
import { RaciGrid } from "@/src/components/features/stakeholders/RaciGrid";
import { resolveRaciGridViolations } from "@/src/components/features/stakeholders/raci-grid-rules";

type RaciRole = "R" | "A" | "C" | "I" | "";

type GridState = Record<string, Record<string, RaciRole>>;

const initialGrid: GridState = {
  w1: {
    s1: "A",
    s2: "R",
  },
};

export function StakeholderRaciWorkbench() {
  const [selectedStakeholderId, setSelectedStakeholderId] = useState<string | null>(null);
  const [selectedCell, setSelectedCell] = useState<{ rowId: string; colId: string } | null>(null);
  const [gridValues, setGridValues] = useState<GridState>(initialGrid);
  const [saveState, setSaveState] = useState("idle");
  const [error, setError] = useState<string | null>(null);

  const stakeholderRoles = useMemo(() => {
    const roles: Record<string, RaciRole> = { s1: "", s2: "" };
    for (const row of Object.values(gridValues)) {
      for (const [stakeholderId, role] of Object.entries(row)) {
        if (role === "A") {
          roles[stakeholderId] = "A";
        }
      }
    }
    return roles;
  }, [gridValues]);

  const setAccountable = () => {
    if (!selectedCell) return;
    setGridValues((prev) => ({
      ...prev,
      [selectedCell.rowId]: {
        ...(prev[selectedCell.rowId] ?? {}),
        [selectedCell.colId]: "A",
      },
    }));
    setSaveState("saved");
  };

  const saveRaci = () => {
    const violations = resolveRaciGridViolations([
      {
        workItemId: "w1",
        assignments: [
          { stakeholderId: "s1", role: gridValues.w1.s1 },
          { stakeholderId: "s2", role: gridValues.w1.s2 },
        ],
      },
    ]);

    if (violations.length > 0) {
      setError("Multiple Accountable assignments are not allowed");
      return;
    }

    setError(null);
    setSaveState("saved");
  };

  return (
    <section aria-label="Stakeholder RACI Workbench">
      <table aria-label="Alerts table">
        <tbody>
          <tr onClick={() => setSelectedStakeholderId("s1")}>
            <td>Delay penalty mismatch</td>
            <td>
              <SeverityBadge severity="critical" />
            </td>
          </tr>
        </tbody>
      </table>

      <div data-testid="alerts-filter-state">{selectedStakeholderId ?? "all"}</div>

      <div>
        <button
          type="button"
          data-testid="stakeholder-node-s1"
          data-highlighted={String(selectedStakeholderId === "s1")}
          data-raci={stakeholderRoles.s1}
          onClick={() => setSelectedStakeholderId("s1")}
        >
          Stakeholder S1
        </button>
        <button
          type="button"
          data-testid="stakeholder-node-s2"
          data-highlighted={String(selectedStakeholderId === "s2")}
          data-raci={stakeholderRoles.s2}
          onClick={() => setSelectedStakeholderId("s2")}
        >
          Stakeholder S2
        </button>
      </div>

      <div data-testid="raci-row-w1" data-focused={String(selectedStakeholderId === "s2")}>
        Work item W1
      </div>

      <RaciGrid
        rows={[{ id: "w1", label: "Permit package" }]}
        columns={[
          { id: "s1", label: "Owner" },
          { id: "s2", label: "GC" },
        ]}
        values={gridValues}
        onCellClick={(rowId, colId) => {
          setSelectedCell({ rowId, colId });
          if (colId === "s2") {
            setSelectedStakeholderId("s2");
          }
        }}
      />

      <button type="button" onClick={setAccountable}>
        Set accountable
      </button>
      <button type="button" onClick={saveRaci}>
        Save RACI
      </button>

      <div data-testid="raci-save-state">{saveState}</div>
      {error ? <div role="alert">{error}</div> : null}
    </section>
  );
}

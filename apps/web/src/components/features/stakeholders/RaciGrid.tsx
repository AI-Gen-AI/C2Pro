/**
 * Test Suite ID: S3-07
 * Roadmap Reference: S3-07 Severity badge + Stakeholder Map + RACI
 */
"use client";

export interface RaciGridRow {
  id: string;
  label: string;
}

export interface RaciGridColumn {
  id: string;
  label: string;
}

type RaciValue = "R" | "A" | "C" | "I" | "";

interface RaciGridProps {
  rows: RaciGridRow[];
  columns: RaciGridColumn[];
  values: Record<string, Record<string, RaciValue>>;
  onCellClick?: (rowId: string, columnId: string) => void;
}

export function RaciGrid({ rows, columns, values, onCellClick }: RaciGridProps) {
  return (
    <table aria-label="RACI Grid" data-testid="raci-grid">
      <thead>
        <tr>
          <th>Work Item</th>
          {columns.map((column) => (
            <th key={column.id} scope="col">
              {column.label}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.id}>
            <th scope="row">{row.label}</th>
            {columns.map((column) => (
              <td
                key={`${row.id}-${column.id}`}
                data-testid={`raci-cell-${row.id}-${column.id}`}
                tabIndex={0}
                onClick={() => onCellClick?.(row.id, column.id)}
              >
                {values[row.id]?.[column.id] ?? ""}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

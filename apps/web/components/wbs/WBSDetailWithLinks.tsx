/**
 * WBSDetailWithLinks Component - Placeholder for RED Phase
 *
 * Suite ID: TS-INT-NAV-001
 * Phase: RED
 */

import React from "react";

export interface ProcurementItem {
  id: string;
  title: string;
  status: string;
  value: number;
}

export interface WBSItemWithProcurement {
  id: string;
  code: string;
  name: string;
  procurementItems?: ProcurementItem[];
}

export interface WBSDetailWithLinksProps {
  item: WBSItemWithProcurement;
  onNavigate?: (type: string, id: string) => void;
}

export const WBSDetailWithLinks: React.FC<WBSDetailWithLinksProps> = () => {
  throw new Error(
    "WBSDetailWithLinks component not implemented. " +
      "This is expected during RED phase (TS-INT-NAV-001).",
  );
};

export default WBSDetailWithLinks;

/**
 * AlertDetailWithLinks Component - Placeholder for RED Phase
 *
 * Suite ID: TS-INT-NAV-001
 * Phase: RED
 */

import React from "react";

export interface AffectedEntity {
  type: string;
  id: string;
  name: string;
}

export interface AlertWithEntities {
  id: string;
  severity: string;
  message: string;
  affectedEntities?: AffectedEntity[];
}

export interface AlertDetailWithLinksProps {
  alert: AlertWithEntities;
  onNavigate?: (type: string, id: string) => void;
}

export const AlertDetailWithLinks: React.FC<AlertDetailWithLinksProps> = () => {
  throw new Error(
    "AlertDetailWithLinks component not implemented. " +
      "This is expected during RED phase (TS-INT-NAV-001).",
  );
};

export default AlertDetailWithLinks;

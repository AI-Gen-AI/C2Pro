import { factory, primaryKey } from "@mswjs/data";

export const db = factory({
  tenant: {
    id: primaryKey(String),
    name: String,
  },
  user: {
    id: primaryKey(String),
    tenantId: String,
    name: String,
    email: String,
    role: String,
  },
  project: {
    id: primaryKey(String),
    tenantId: String,
    name: String,
    status: String,
  },
  document: {
    id: primaryKey(String),
    projectId: String,
    name: String,
    status: String,
  },
  clause: {
    id: primaryKey(String),
    documentId: String,
    text: String,
    clauseType: String,
  },
  alert: {
    id: primaryKey(String),
    projectId: String,
    category: String,
    severity: String,
    status: String,
    message: String,
  },
  stakeholder: {
    id: primaryKey(String),
    projectId: String,
    name: String,
    role: String,
    power: Number,
    interest: Number,
  },
  wbsItem: {
    id: primaryKey(String),
    projectId: String,
    code: String,
    name: String,
    level: Number,
  },
});

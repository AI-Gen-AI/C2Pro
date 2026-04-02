/**
 * Test Suite ID: TASK-1446
 * Purpose: Local in-memory mock database for frontend MSW-backed tests.
 */

type EqualsFilter<T> = {
  equals: T;
};

type WhereClause<T extends Record<string, unknown>> = Partial<{
  [K in keyof T]: EqualsFilter<T[K]>;
}>;

interface Query<T extends Record<string, unknown>> {
  where?: WhereClause<T>;
}

interface UpdateQuery<T extends Record<string, unknown>> extends Query<T> {
  data: Partial<T>;
}

interface Collection<T extends { id: string }> {
  create(record: T): T;
  getAll(): T[];
  findFirst(query?: Query<T>): T | null;
  findMany(query?: Query<T>): T[];
  update(query: UpdateQuery<T>): T;
  reset(): void;
}

interface TenantRecord {
  id: string;
  name: string;
}

interface UserRecord {
  id: string;
  tenantId: string;
  name: string;
  email: string;
  role: string;
}

interface ProjectRecord {
  id: string;
  tenantId: string;
  name: string;
  status: string;
}

interface DocumentRecord {
  id: string;
  projectId: string;
  name: string;
  filename: string;
  status: string;
  document_type: string;
  uploaded_at: string;
  file_size_bytes: number;
}

interface ClauseRecord {
  id: string;
  documentId: string;
  text: string;
  clauseType: string;
}

interface AlertRecord {
  id: string;
  projectId: string;
  category: string;
  severity: string;
  status: string;
  message: string;
}

interface StakeholderRecord {
  id: string;
  projectId: string;
  name: string;
  role: string;
  power: number;
  interest: number;
}

interface WbsItemRecord {
  id: string;
  projectId: string;
  code: string;
  name: string;
  level: number;
}

function matchesWhere<T extends Record<string, unknown>>(
  record: T,
  where?: WhereClause<T>,
): boolean {
  if (!where) {
    return true;
  }

  return Object.entries(where).every(([field, predicate]) => {
    if (!predicate) {
      return true;
    }

    return record[field as keyof T] === predicate.equals;
  });
}

function createCollection<T extends { id: string }>(): Collection<T> {
  let records: T[] = [];

  return {
    create(record) {
      const nextRecord = { ...record };
      const existingIndex = records.findIndex(({ id }) => id === nextRecord.id);

      if (existingIndex >= 0) {
        records[existingIndex] = nextRecord;
      } else {
        records.push(nextRecord);
      }

      return { ...nextRecord };
    },
    getAll() {
      return records.map((record) => ({ ...record }));
    },
    findFirst(query) {
      const record = records.find((item) => matchesWhere(item, query?.where));
      return record ? { ...record } : null;
    },
    findMany(query) {
      return records
        .filter((item) => matchesWhere(item, query?.where))
        .map((record) => ({ ...record }));
    },
    update(query) {
      const index = records.findIndex((item) => matchesWhere(item, query.where));
      if (index < 0) {
        throw new Error("Mock record not found for update");
      }

      const nextRecord = {
        ...records[index],
        ...query.data,
      };

      records[index] = nextRecord;
      return { ...nextRecord };
    },
    reset() {
      records = [];
    },
  };
}

export const db = {
  tenant: createCollection<TenantRecord>(),
  user: createCollection<UserRecord>(),
  project: createCollection<ProjectRecord>(),
  document: createCollection<DocumentRecord>(),
  clause: createCollection<ClauseRecord>(),
  alert: createCollection<AlertRecord>(),
  stakeholder: createCollection<StakeholderRecord>(),
  wbsItem: createCollection<WbsItemRecord>(),
};

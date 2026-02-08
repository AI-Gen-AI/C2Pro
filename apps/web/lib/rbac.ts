/**
 * Role-based access control utilities
 */

export type UserRole = 'user' | 'tenant_admin' | 'c2pro_admin';

export const rolePermissions: Record<UserRole, string[]> = {
  user: ['view_own_projects', 'create_project', 'upload_documents'],
  tenant_admin: [
    'view_all_projects',
    'create_project',
    'manage_users',
    'view_analytics',
    'manage_tenant_settings',
  ],
  c2pro_admin: [
    'view_all_projects',
    'view_all_tenants',
    'manage_tenants',
    'manage_users',
    'view_analytics',
    'manage_system_settings',
    'manage_billing',
  ],
};

export function hasPermission(role: UserRole, permission: string): boolean {
  return rolePermissions[role].includes(permission);
}

export function getRoleLabel(role: UserRole): string {
  const labels: Record<UserRole, string> = {
    user: 'User',
    tenant_admin: 'Tenant Administrator',
    c2pro_admin: 'C2Pro Administrator',
  };
  return labels[role];
}

export function getRoleDescription(role: UserRole): string {
  const descriptions: Record<UserRole, string> = {
    user: 'Can create and manage their own projects',
    tenant_admin: 'Can manage all projects and users within the tenant',
    c2pro_admin: 'System administrator with full access to all features',
  };
  return descriptions[role];
}

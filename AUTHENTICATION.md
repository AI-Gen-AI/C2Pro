# C2Pro v3.0 - Authentication & Role-Based Architecture

## Overview

C2Pro v3.0 implements a complete role-based authentication system with three user tiers:

1. **Regular User** - Project team members
2. **Tenant Admin** - Company administrators
3. **C2Pro Admin** - System administrators

## Authentication Flow

### Pages

- **Landing Page** (`/`) - Public information about C2Pro
- **Login** (`/login`) - User authentication
- **Signup** (`/signup`) - User registration with company creation
- **Dashboard** (`/dashboard`) - Redirects based on user role

### Role-Based Dashboards

#### 1. Regular User Dashboard
- **Route**: `/dashboard/projects`
- **Permissions**: Create projects, upload documents, run analysis
- **Features**:
  - View personal projects
  - Upload project documents
  - Run coherence analysis
  - View analysis results

#### 2. Tenant Admin Dashboard
- **Route**: `/admin/tenant`
- **Permissions**: View all tenant projects, manage users, view analytics
- **Features**:
  - View all projects across tenant
  - Manage tenant users (`/admin/tenant/users`)
  - Tenant settings (`/admin/tenant/settings`)
  - View tenant analytics
  - Manage subscription plan

#### 3. C2Pro Admin Dashboard
- **Route**: `/admin/c2pro`
- **Permissions**: Full system access
- **Features**:
  - View all tenants
  - Manage all tenants
  - System settings (`/admin/c2pro/settings`)
  - Monitor system health
  - Manage billing

## Technical Architecture

### Authentication Context

Located in `/apps/web/contexts/AuthContext.tsx`

```typescript
interface AuthContextType {
  user: UserResponse | null;
  tenant: TenantResponse | null;
  accessToken: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  userRole?: 'user' | 'tenant_admin' | 'c2pro_admin';
  login: (credentials: LoginRequest) => Promise<void>;
  register: (data: RegisterRequest) => Promise<void>;
  logout: () => void;
  refreshUserData: () => Promise<void>;
}
```

### Protected Routes

Use the `<ProtectedRoute>` component to guard pages:

```tsx
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';

export default function Page() {
  return (
    <ProtectedRoute requiredRole="tenant_admin">
      {/* Page content */}
    </ProtectedRoute>
  );
}
```

### Role-Based Access Control (RBAC)

Located in `/apps/web/lib/rbac.ts`

```typescript
import { hasPermission } from '@/lib/rbac';

if (hasPermission(userRole, 'manage_users')) {
  // Show user management UI
}
```

## Directory Structure

```
apps/web/
├── app/
│   ├── (auth)/                 # Auth routes (login, signup)
│   ├── (landing)/              # Landing page
│   ├── (dashboard)/            # Main dashboard (deprecated - use /dashboard)
│   ├── admin/                  # Admin routes
│   │   ├── c2pro/              # C2Pro admin dashboard
│   │   └── tenant/             # Tenant admin dashboard
│   └── dashboard/              # User dashboard
│       └── projects/           # User projects page
├── components/
│   ├── auth/
│   │   └── ProtectedRoute.tsx  # Route protection component
│   └── navbar.tsx              # Contextual navbar
├── contexts/
│   └── AuthContext.tsx         # Auth state management
├── lib/
│   ├── api/auth.ts             # Auth API client
│   └── rbac.ts                 # Role-based access utilities
└── middleware.ts               # Route protection middleware
```

## Key Features

### Automatic Role-Based Redirection

After login, users are automatically redirected to their appropriate dashboard:

- Regular users → `/dashboard/projects`
- Tenant admins → `/admin/tenant`
- C2Pro admins → `/admin/c2pro`

### Protected Routes

The middleware automatically protects routes:

```typescript
// Try to access /admin/c2pro as tenant_admin → Redirects to /dashboard
// Try to access /admin/tenant as regular user → Redirects to /dashboard
```

### Token Management

- Access tokens stored in localStorage
- Automatic token refresh 1 hour before expiration
- Secure logout clears all auth data

### User Data Persistence

- User and tenant data stored in localStorage
- Auto-refresh on page reload
- Automatic logout if token becomes invalid

## Development Notes

### Adding New Roles

1. Update `UserRole` type in `/lib/rbac.ts`
2. Add permissions to `rolePermissions` object
3. Update label and description functions
4. Add new dashboard route

### Protecting New Routes

```tsx
// Component-level protection
<ProtectedRoute requiredRole="tenant_admin">
  {/* Only tenant admins can see this */}
</ProtectedRoute>

// Middleware-level protection (see middleware.ts)
if (pathname.startsWith('/admin/c2pro') && userRole !== 'c2pro_admin') {
  return NextResponse.redirect(new URL('/dashboard', request.url));
}
```

### API Integration

The auth API is defined in `/lib/api/auth.ts`. Update endpoints to match your backend:

```typescript
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';
```

## Testing

Visit `/flow-demo` to see an overview of the entire authentication flow and role structure.

## Environment Variables

Required environment variables:

```
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
```

## Next Steps

1. Connect to your backend API
2. Update user role assignment logic
3. Implement actual permission checks
4. Add audit logging for admin actions
5. Set up two-factor authentication for admins

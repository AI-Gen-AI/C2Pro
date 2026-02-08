# Testing Different User Roles in C2Pro

## Quick Start

You now have **two ways** to view and test different user interfaces:

### 1. 🎮 **Dev Mode Button** (Fastest)
- Look for the blue "**Dev Mode**" button in the **bottom right corner** of any page
- Click it to see a dropdown menu with three role options
- Select a role to instantly switch
- Refresh or navigate to any page to see how it appears for that role

### 2. 📊 **Demo Roles Page** (Most Detailed)
- Visit `/demo-roles` 
- View all three roles with descriptions
- See a permissions table showing what each role can do
- Click to navigate to that role's dashboard

## The Three User Roles

### 👤 **Regular User**
**For:** Individual project managers and analysts

**Can do:**
- View and manage their own projects
- Upload documents for analysis
- View analysis results and reports
- Access personal settings

**Main URLs:**
- `/dashboard/projects` - View your projects
- `/dashboard/projects/demo` - View demo analysis

---

### 🛡️ **Tenant Admin**
**For:** Organization managers overseeing all company projects

**Can do:**
- View **ALL** projects in the entire tenant/organization
- Manage users and their access permissions
- Configure tenant settings and preferences
- View analytics and reports for the entire organization
- Manage billing and subscriptions

**Main URLs:**
- `/admin/tenant` - Overview of all tenant projects
- `/admin/tenant/users` - Manage users
- `/admin/tenant/settings` - Configure tenant settings

---

### 👑 **C2Pro Admin**
**For:** Platform administrators managing the entire system

**Can do:**
- Manage all tenants in the platform
- Create new tenants and users
- Configure system-wide settings
- Monitor platform health and usage
- Manage security and system integrations

**Main URLs:**
- `/admin/c2pro` - Overview of all tenants
- `/admin/c2pro/settings` - System settings

---

## Public Pages (No Login Required)

- **`/`** - Landing page with product overview
- **`/login`** - Login page
- **`/signup`** - Registration page
- **`/guide`** - This guide page
- **`/demo-roles`** - Role switcher and permissions table

---

## Testing Workflow

### Test Regular User Flow
1. Click the Dev Mode button → Select **"User"**
2. Visit `/dashboard/projects` to see user dashboard
3. Visit `/dashboard/projects/demo` to see the analysis demo page

### Test Tenant Admin Flow
1. Click the Dev Mode button → Select **"Tenant Admin"**
2. Visit `/admin/tenant` to see all tenant projects
3. Visit `/admin/tenant/users` to manage users
4. Visit `/admin/tenant/settings` for settings

### Test C2Pro Admin Flow
1. Click the Dev Mode button → Select **"C2Pro Admin"**
2. Visit `/admin/c2pro` to see system overview
3. Visit `/admin/c2pro/settings` for system settings

---

## How It Works

### Dev Mode Switch
- Only available in **development environment**
- Doesn't require real authentication
- Stores the selected role in React state
- Allows you to instantly preview different interfaces
- **Production:** Dev Mode button is completely hidden

### Protected Routes
- Routes check your current role from the `useAuth()` hook
- If you don't have permission for a route, you get redirected
- In dev mode, you can switch roles to test any interface

---

## URL Reference

| Route | Purpose | Requires Role |
|-------|---------|----------------|
| `/` | Landing page | None |
| `/login` | Login page | None |
| `/signup` | Sign up page | None |
| `/guide` | This guide | None |
| `/demo-roles` | Role switcher | None |
| `/dashboard/projects` | User projects | User+ |
| `/dashboard/projects/demo` | Demo analysis | User+ |
| `/admin/tenant` | Tenant projects | Tenant Admin+ |
| `/admin/tenant/users` | User management | Tenant Admin+ |
| `/admin/tenant/settings` | Tenant settings | Tenant Admin+ |
| `/admin/c2pro` | Platform overview | C2Pro Admin |
| `/admin/c2pro/settings` | System settings | C2Pro Admin |

---

## Features by Role

### Feature Access Table

| Feature | User | Tenant Admin | C2Pro Admin |
|---------|------|----------------|-------------|
| View own projects | ✓ | ✓ | ✓ |
| View all tenant projects | - | ✓ | ✓ |
| Upload/analyze documents | ✓ | ✓ | ✓ |
| Manage users | - | ✓ | ✓ |
| Manage tenants | - | - | ✓ |
| Configure settings | - | ✓ | ✓ |
| System administration | - | - | ✓ |

---

## Tips for Testing

1. **Start with the guide:** Visit `/guide` for a guided walkthrough
2. **Use the role demo:** Go to `/demo-roles` to understand permissions
3. **Switch roles easily:** Click the Dev Mode button anytime
4. **Check URLs:** Each interface has specific URLs you can bookmark
5. **Test permissions:** Try accessing a route that requires a higher role

---

## Development Notes

- The Dev Mode button is automatically hidden in production
- Role switching is stored in React state (resets on page refresh in some cases)
- All routes respect the current role when rendering
- Use the `useAuth()` hook to check the current role in your components

---

## Next Steps

Ready to explore? Start here:

1. **Try the Role Demo:** `/demo-roles`
2. **Read the Guide:** `/guide`
3. **Check the Landing:** `/`
4. **Test each role's dashboard using the Dev Mode button**

Happy testing! 🚀

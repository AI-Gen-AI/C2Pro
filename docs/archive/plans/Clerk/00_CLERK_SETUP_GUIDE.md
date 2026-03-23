# 🔑 PASO 0: Clerk Setup Guide
## Initial Configuration at dashboard.clerk.com

**Tiempo estimado:** 15-20 minutos  
**Resultado:** Credenciales para .env.local

---

## Step 1: Create Clerk Project

### 1.1 Go to https://dashboard.clerk.com

### 1.2 Click "Create application"
- Name: `C2Pro`
- Choose your preferred OAuth providers:
  - ✅ Google (recommended for enterprise)
  - ✅ GitHub
  - ✅ Email/Password (also enable)

### 1.3 Wait for project creation (~30 seconds)

---

## Step 2: Configure Custom Metadata

Clerk will show you the API keys. **Save them for later.**

Now go to **Settings** → **API Keys** and copy:
```
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_xxxxx
CLERK_SECRET_KEY=sk_test_xxxxx
```

Then go to **Settings** → **User Profiles** → **Custom Fields**

### 2.1 Add Custom Metadata Fields

Click **"Add Field"** and create these:

**Field 1: Service Tier**

```
Key: tier
Type: Text
Predefined values:
  - free
  - pro
  - enterprise
Default: free
```

**Field 2: Tenant ID**

```
Key: tenant_id
Type: Text
Default: (leave empty - filled by your app)
```

**Field 3: User Role**
```
Key: role
Type: Text
Predefined values:
  - user
  - admin
  - c2pro_admin
Default: user
```

---

## Step 3: Create First Tenant Organization

### 3.1 Go to **Organizations** in Clerk Dashboard

Click **"Create Organization"**

**Organization 1: C2Pro Platform (Admin)**

```
Name: C2Pro Platform Admin
Slug: c2pro-platform
```

This is for Clerk admins to manage the platform.

**Organization 2: Demo Workspace (for testing)**
```
Name: Demo Workspace
Slug: demo-workspace
Metadata:
  - tenant_id: demo-tenant-uuid
  - demo_mode: true
```

Generate a UUID for demo tenant:
```bash
# Run in terminal:
python -c "import uuid; print(uuid.uuid4())"
# Output example: 550e8400-e29b-41d4-a716-446655440000
```

---

## Step 4: Create First Admin User

### 4.1 Go to **Users** section

Click **"Create User"** and fill:
```
Email: your-email@yourcompany.com
Password: (generate strong password)
```

### 4.2 Assign to Organization

After creating user, go to **Users** → select the user → **Organizations**

Click **"Add to Organization"** and:
- Select: `C2Pro Platform Admin`
- Role: `admin`
- Custom attributes:
  - tier: `enterprise`
  - role: `c2pro_admin`
  - tenant_id: `c2pro-platform`

---

## Step 5: Setup Webhooks (Optional but Recommended)

### 5.1 Go to **Webhooks** → **Create Endpoint**

We'll use webhooks to sync Clerk users to Supabase automatically.

**Endpoint URL:** (you'll set this later after deploying)
```
https://your-api.com/api/webhooks/clerk/user-created
```

**Events to enable:**
- ✅ user.created
- ✅ user.updated
- ✅ organization.created
- ✅ organizationMembership.created
- ✅ organizationMembership.updated

For now, keep this disabled. We'll enable it when backend is ready.

---

## Step 6: Environment Variables

Copy these to your `.env.local` file:

```bash
# Clerk Keys
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_xxxxx
CLERK_SECRET_KEY=sk_test_xxxxx

# Clerk URLs (optional, defaults are usually fine)
NEXT_PUBLIC_CLERK_SIGN_IN_URL=/sign-in
NEXT_PUBLIC_CLERK_SIGN_UP_URL=/sign-up
NEXT_PUBLIC_CLERK_AFTER_SIGN_IN_URL=/dashboard
NEXT_PUBLIC_CLERK_AFTER_SIGN_UP_URL=/onboarding

# Keep your existing Supabase keys
NEXT_PUBLIC_SUPABASE_URL=https://xxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJ...
```

---

## Step 7: Organization Metadata (Important!)

In Clerk Dashboard, go to **Organizations** and for each organization:

### For C2Pro Platform Org:
Click organization → **Settings** → **Add Metadata**
```
Type: Public Metadata
tenant_id: c2pro-platform
is_platform_admin: true
```

### For Demo Workspace Org:
```
Type: Public Metadata
tenant_id: 550e8400-e29b-41d4-a716-446655440000  (use your uuid)
is_demo: true
demo_data: true
```

### For Customer Tenants (later):
You'll create these programmatically, but structure:
```
Type: Public Metadata
tenant_id: actual-tenant-uuid
is_demo: false
tier: free  (or pro/enterprise)
```

---

## Step 8: Configure Sign In/Sign Up Pages

Go to **Customization** → **Branding**

### 8.1 Logo & Colors (Optional)
- Upload C2Pro logo
- Set primary color: #0ea5e9 (blue)
- Set accent color: #f59e0b (amber)

### 8.2 Sign In/Sign Up Pages

Go to **Sign-in & sign-up** section

Enable:
- ✅ Email/password authentication
- ✅ Google OAuth
- ✅ GitHub OAuth (optional)

---

## ✅ Verification Checklist

Before moving to Step 1 (Frontend Setup):

- [ ] Clerk project created
- [ ] API keys copied to `.env.local`
- [ ] Custom metadata fields added (tier, tenant_id, role)
- [ ] C2Pro Platform Admin organization created
- [ ] Demo Workspace organization created
- [ ] First admin user created
- [ ] First user assigned to C2Pro Platform Admin org
- [ ] Organization metadata configured
- [ ] Environment variables saved

---

## 🐛 Troubleshooting

### "API keys not showing"
→ Refresh the page or create a new application

### "Can't create custom metadata fields"
→ Fields must be unique across all orgs. Try `user_tier`, `user_role` instead

### "Organization slug already exists"
→ Use unique slugs: `c2pro-platform-001`, `demo-workspace-001`

---

## 📞 Next Step

Once you've completed all steps here, proceed to:

**PASO 1: Frontend Environment Setup** → `01_FRONTEND_ENV_SETUP.md`

---

**Status:** ✅ Ready to configure  
**Time remaining:** 4-5 weeks to full implementation

# 📦 PASO 1: Frontend Environment Setup
## Install Dependencies & Configure .env

**Tiempo estimado:** 10 minutos  
**Prerequisito:** PASO 0 completado

---

## Step 1: Install Dependencies

Navigate to your frontend directory:

```bash
cd apps/web

# Install Clerk for Next.js
npm install @clerk/nextjs

# Verify installation
npm list @clerk/nextjs
# Should show: @clerk/nextjs@5.x.x or higher
```

**Dependencies included with @clerk/nextjs:**
- ✅ React hooks for auth
- ✅ Next.js middleware
- ✅ Components (SignIn, SignUp, UserButton, etc.)
- ✅ Organization management

---

## Step 2: Update .env.local

Open or create `apps/web/.env.local`:

```bash
# ========== CLERK KEYS (from PASO 0) ==========
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_xxxxx
CLERK_SECRET_KEY=sk_test_xxxxx

# ========== CLERK CONFIGURATION ==========
NEXT_PUBLIC_CLERK_SIGN_IN_URL=/sign-in
NEXT_PUBLIC_CLERK_SIGN_UP_URL=/sign-up
NEXT_PUBLIC_CLERK_AFTER_SIGN_IN_URL=/dashboard
NEXT_PUBLIC_CLERK_AFTER_SIGN_UP_URL=/onboarding

# ========== SUPABASE KEYS (existing) ==========
NEXT_PUBLIC_SUPABASE_URL=https://xxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJ...

# ========== API CONFIGURATION ==========
NEXT_PUBLIC_API_URL=http://localhost:8000
API_BACKEND_URL=http://localhost:8000

# ========== ENVIRONMENT ==========
NEXT_ENV=development
```

**Verify file format:**
```bash
# Check that .env.local exists
cat apps/web/.env.local | head -20

# Should show all variables above
```

---

## Step 3: Update Root Layout

Replace `apps/web/app/layout.tsx` with Clerk provider:

```tsx
// File: apps/web/app/layout.tsx

import { ClerkProvider } from '@clerk/nextjs'
import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'C2Pro - Contract Intelligence Platform',
  description: 'AI-driven procurement intelligence for EPC projects',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <ClerkProvider>
      <html lang="en">
        <body className="bg-slate-900">
          {children}
        </body>
      </html>
    </ClerkProvider>
  )
}
```

---

## Step 4: Create Middleware

Create new file: `apps/web/middleware.ts`

```typescript
import { authMiddleware } from '@clerk/nextjs'

export default authMiddleware({
  // Public routes that don't require authentication
  publicRoutes: [
    '/',
    '/sign-in',
    '/sign-up',
    '/api/webhooks/clerk',
    '/pricing',
    '/about',
  ],
  
  // Routes that should ignore auth checks
  ignoredRoutes: [
    '/api/webhooks/clerk',
    '/api/health',
  ],
})

export const config = {
  matcher: [
    // Skip Next.js internals and all static files, unless found in search params
    '/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)',
    // Always run for API routes
    '/(api|trpc)(.*)',
  ],
}
```

---

## Step 5: Create Sign-In Page

Create folder and file: `apps/web/app/(auth)/sign-in/[[...sign-in]]/page.tsx`

```tsx
import { SignIn } from '@clerk/nextjs'

export default function SignInPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
      <SignIn 
        appearance={{
          elements: {
            rootBox: 'w-full max-w-md',
            card: 'bg-slate-800 border border-slate-700 shadow-2xl',
            headerTitle: 'text-white text-2xl',
            headerSubtitle: 'text-slate-400',
            formButtonPrimary: 'bg-blue-600 hover:bg-blue-700',
            footerActionLink: 'text-blue-400 hover:text-blue-300',
          },
        }}
      />
    </div>
  )
}
```

---

## Step 6: Create Sign-Up Page

Create folder and file: `apps/web/app/(auth)/sign-up/[[...sign-up]]/page.tsx`

```tsx
import { SignUp } from '@clerk/nextjs'

export default function SignUpPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
      <SignUp 
        appearance={{
          elements: {
            rootBox: 'w-full max-w-md',
            card: 'bg-slate-800 border border-slate-700 shadow-2xl',
            headerTitle: 'text-white text-2xl',
            headerSubtitle: 'text-slate-400',
            formButtonPrimary: 'bg-blue-600 hover:bg-blue-700',
            footerActionLink: 'text-blue-400 hover:text-blue-300',
          },
        }}
      />
    </div>
  )
}
```

---

## Step 7: Create Auth Layout

Create file: `apps/web/app/(auth)/layout.tsx`

```tsx
export default function AuthLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
      {children}
    </div>
  )
}
```

---

## Step 8: Create Protected Dashboard Page

Create folder and file: `apps/web/app/dashboard/page.tsx`

```tsx
import { auth, currentUser } from '@clerk/nextjs'
import { redirect } from 'next/navigation'

export default async function DashboardPage() {
  const { userId } = auth()
  const user = await currentUser()

  // Redirect to sign-in if not authenticated
  if (!userId) {
    redirect('/sign-in')
  }

  return (
    <div className="min-h-screen bg-slate-900 text-white p-8">
      <div className="max-w-6xl mx-auto">
        <h1 className="text-4xl font-bold mb-2">Welcome, {user?.firstName || user?.emailAddresses[0]?.emailAddress}!</h1>
        <p className="text-slate-400 mb-8">C2Pro Dashboard</p>

        {/* Placeholder for dashboard content */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mt-8">
          <div className="bg-slate-800 border border-slate-700 rounded-lg p-6">
            <h2 className="text-slate-400 text-sm font-medium">Projects</h2>
            <p className="text-4xl font-bold text-white mt-2">0</p>
          </div>
          <div className="bg-slate-800 border border-slate-700 rounded-lg p-6">
            <h2 className="text-slate-400 text-sm font-medium">Documents</h2>
            <p className="text-4xl font-bold text-white mt-2">0</p>
          </div>
          <div className="bg-slate-800 border border-slate-700 rounded-lg p-6">
            <h2 className="text-slate-400 text-sm font-medium">Alerts</h2>
            <p className="text-4xl font-bold text-white mt-2">0</p>
          </div>
        </div>

        <div className="mt-8 p-4 bg-yellow-600/10 border border-yellow-600/30 rounded-lg">
          <p className="text-yellow-400 text-sm">
            ✨ Dashboard content will be populated in the next phase
          </p>
        </div>
      </div>
    </div>
  )
}
```

---

## Step 9: Create Navbar Component

Create file: `apps/web/src/components/navbar.tsx`

```tsx
'use client'

import { useAuth } from '@clerk/nextjs'
import { SignOutButton, UserButton, OrganizationSwitcher } from '@clerk/nextjs'
import Link from 'next/link'

export function Navbar() {
  const { isSignedIn } = useAuth()

  return (
    <nav className="bg-slate-800 border-b border-slate-700">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 flex items-center justify-between h-16">
        {/* Logo */}
        <Link href="/" className="text-2xl font-bold text-white">
          C2Pro
        </Link>

        {/* Navigation */}
        {isSignedIn && (
          <div className="flex items-center gap-6">
            <Link href="/dashboard" className="text-slate-300 hover:text-white">
              Dashboard
            </Link>
            <Link href="/projects" className="text-slate-300 hover:text-white">
              Projects
            </Link>
            
            {/* Organization Switcher - For Demo/Production switching */}
            <OrganizationSwitcher
              appearance={{
                elements: {
                  organizationSwitcherPopoverActionButton: 'bg-blue-600 hover:bg-blue-700',
                  organizationPreviewTextContainer: 'text-slate-200',
                },
              }}
            />

            {/* User Menu */}
            <UserButton
              appearance={{
                elements: {
                  userButtonPopupCard: 'bg-slate-800 border-slate-700',
                },
              }}
            />
          </div>
        )}

        {/* Sign In for unauthenticated users */}
        {!isSignedIn && (
          <Link href="/sign-in" className="text-blue-400 hover:text-blue-300">
            Sign In
          </Link>
        )}
      </div>
    </nav>
  )
}
```

---

## Step 10: Test the Setup

```bash
# Start dev server
npm run dev

# Should output:
# ▲ Next.js ready on http://localhost:3000

# Try these URLs:
# 1. http://localhost:3000 → Should load
# 2. http://localhost:3000/sign-in → Should show Clerk SignIn form
# 3. http://localhost:3000/sign-up → Should show Clerk SignUp form
# 4. http://localhost:3000/dashboard → Should redirect to /sign-in
```

---

## ✅ Verification Checklist

- [ ] `npm install @clerk/nextjs` completed
- [ ] `.env.local` updated with Clerk keys
- [ ] Root layout has ClerkProvider
- [ ] `middleware.ts` created
- [ ] Sign-in page created
- [ ] Sign-up page created
- [ ] Dashboard page created
- [ ] Auth layout created
- [ ] Navbar component created
- [ ] Dev server runs without errors
- [ ] Can access `/sign-in`
- [ ] Can see Clerk form

---

## 🐛 Troubleshooting

### "Cannot find module @clerk/nextjs"
```bash
npm install @clerk/nextjs
npm run dev  # Restart dev server
```

### "NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY is not set"
→ Check `.env.local` has `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`  
→ Restart dev server after updating .env

### "Clerk form not showing"
→ Check browser console for errors (F12)  
→ Verify API keys are correct in .env.local

### "Redirect loop on /dashboard"
→ Make sure userId check in page.tsx is correct  
→ Check middleware.ts publicRoutes includes '/sign-in'

---

## 📞 Next Step

Once this is working, proceed to:

**PASO 2: Bridge Layer & Tenant Context** → `02_BRIDGE_LAYER.md`

---

**Status:** ✅ Ready to implement  
**Time to complete:** 10 minutes  
**Next:** PASO 2

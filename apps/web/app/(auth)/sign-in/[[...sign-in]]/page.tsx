/**
 * Sign In Page
 *
 * Uses Clerk's SignIn component with C2Pro dark theme styling.
 * Handles email/password and OAuth (Google) authentication.
 */

import { SignIn } from "@clerk/nextjs";

export default function SignInPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 p-4">
      <div className="w-full max-w-md">
        {/* Logo & Header */}
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-white tracking-tight">
            C2Pro
          </h1>
          <p className="text-slate-400 mt-2 text-sm">
            Contract Intelligence Platform
          </p>
        </div>

        {/* Clerk SignIn Component */}
        <SignIn
          appearance={{
            elements: {
              rootBox: "w-full",
              card: "bg-slate-800 border border-slate-700 shadow-2xl rounded-xl",
              headerTitle: "text-white text-xl font-semibold",
              headerSubtitle: "text-slate-400 text-sm",
              socialButtonsBlockButton:
                "bg-slate-700 border-slate-600 text-white hover:bg-slate-600 transition-colors",
              socialButtonsBlockButtonText: "text-white font-medium",
              dividerLine: "bg-slate-600",
              dividerText: "text-slate-500 text-xs",
              formFieldLabel: "text-slate-300 text-sm font-medium",
              formFieldInput:
                "bg-slate-700 border-slate-600 text-white placeholder:text-slate-500 focus:border-cyan-500 focus:ring-cyan-500",
              formButtonPrimary:
                "bg-cyan-600 hover:bg-cyan-700 text-white font-medium transition-colors",
              footerActionLink:
                "text-cyan-400 hover:text-cyan-300 font-medium transition-colors",
              identityPreviewText: "text-white",
              identityPreviewEditButton: "text-cyan-400 hover:text-cyan-300",
              formFieldInputShowPasswordButton: "text-slate-400",
              otpCodeFieldInput: "bg-slate-700 border-slate-600 text-white",
              formResendCodeLink: "text-cyan-400 hover:text-cyan-300",
              alert: "bg-red-500/10 border-red-500/20 text-red-400",
              alertText: "text-red-400",
            },
            layout: {
              socialButtonsPlacement: "top",
              socialButtonsVariant: "blockButton",
            },
          }}
          routing="path"
          path="/sign-in"
          signUpUrl="/sign-up"
        />

        {/* Footer */}
        <p className="text-center text-xs text-slate-500 mt-6">
          By signing in, you agree to our Terms of Service and Privacy Policy.
        </p>
      </div>
    </div>
  );
}

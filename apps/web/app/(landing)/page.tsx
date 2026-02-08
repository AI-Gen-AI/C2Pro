'use client';

import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-white">
      {/* Navigation */}
      <nav className="flex items-center justify-between border-b px-6 py-4 sticky top-0 bg-white/95 backdrop-blur-sm z-50">
        <Link href="/" className="flex items-center gap-2">
          <div className="text-2xl font-bold bg-gradient-to-r from-primary to-primary/70 bg-clip-text text-transparent">
            C2Pro
          </div>
        </Link>
        <div className="hidden gap-8 md:flex">
          <a href="#features" className="text-sm text-foreground hover:text-primary transition-colors">
            Features
          </a>
          <a href="#stats" className="text-sm text-foreground hover:text-primary transition-colors">
            Why C2Pro
          </a>
          <a href="#" className="text-sm text-foreground hover:text-primary transition-colors">
            Pricing
          </a>
        </div>
        <div className="flex gap-3 items-center">
          <Link href="/login">
            <Button variant="ghost" size="sm">
              Sign In
            </Button>
          </Link>
          <Link href="/signup">
            <Button size="sm" className="bg-primary hover:bg-primary/90">
              Get Started
            </Button>
          </Link>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="space-y-6 px-6 py-20 text-center">
        <h1 className="text-5xl font-bold leading-tight text-foreground md:text-6xl">
          Detect contract conflicts{' '}
          <span className="text-primary">before they cost millions</span>
        </h1>
        <p className="mx-auto max-w-2xl text-lg text-muted-foreground">
          AI-powered cross-document analysis for construction and engineering
          mega-projects. Real-time coherence scoring across Scope, Budget,
          Quality, Technical, Legal, and Time.
        </p>
        <div className="flex justify-center gap-4">
          <Link href="/signup">
            <Button size="lg" className="bg-primary hover:bg-primary/90">
              Start Free Trial
              <span className="ml-2">→</span>
            </Button>
          </Link>
          <Link href="/dashboard">
            <Button size="lg" variant="outline">
              View Live Demo
            </Button>
          </Link>
        </div>
      </section>

      {/* Statistics Section */}
      <section className="border-b bg-background px-6 py-16">
        <div className="mx-auto grid max-w-5xl grid-cols-2 gap-8 md:grid-cols-4">
          <div className="space-y-2 text-center">
            <div className="text-4xl font-bold text-primary">94%</div>
            <div className="text-sm text-muted-foreground">Risk Detection Rate</div>
          </div>
          <div className="space-y-2 text-center">
            <div className="text-4xl font-bold text-primary">6x</div>
            <div className="text-sm text-muted-foreground">Faster Review</div>
          </div>
          <div className="space-y-2 text-center">
            <div className="text-4xl font-bold text-primary">$2.4M</div>
            <div className="text-sm text-muted-foreground">Avg. Savings per Project</div>
          </div>
          <div className="space-y-2 text-center">
            <div className="text-4xl font-bold text-primary">&lt;30s</div>
            <div className="text-sm text-muted-foreground">Analysis Time</div>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section id="features" className="space-y-12 px-6 py-20">
        <div className="mx-auto max-w-3xl text-center">
          <h2 className="text-4xl font-bold text-foreground">
            Everything you need for contract coherence
          </h2>
          <p className="mt-4 text-lg text-muted-foreground">
            Six-dimensional analysis ensures no contradiction goes undetected
            across your entire document corpus.
          </p>
        </div>

        <div className="mx-auto grid max-w-5xl gap-6 md:grid-cols-3">
          {/* Feature 1 */}
          <Card className="space-y-4 border bg-card p-6 shadow-sm">
            <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-primary/10">
              <svg
                className="h-6 w-6 text-primary"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
            </div>
            <h3 className="text-xl font-semibold text-foreground">
              Cross-Document Analysis
            </h3>
            <p className="text-muted-foreground">
              AI scans contracts, specs, and schedules to detect contradictions
              across all project documents.
            </p>
          </Card>

          {/* Feature 2 */}
          <Card className="space-y-4 border bg-card p-6 shadow-sm">
            <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-primary/10">
              <svg
                className="h-6 w-6 text-primary"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
                />
              </svg>
            </div>
            <h3 className="text-xl font-semibold text-foreground">
              Coherence Scoring
            </h3>
            <p className="text-muted-foreground">
              Real-time scoring across 6 categories: Scope, Budget, Quality,
              Technical, Legal, and Time.
            </p>
          </Card>

          {/* Feature 3 */}
          <Card className="space-y-4 border bg-card p-6 shadow-sm">
            <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-primary/10">
              <svg
                className="h-6 w-6 text-primary"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 9v2m0 4v2m0 4v2M7 5h10a2 2 0 012 2v10a2 2 0 01-2 2H7a2 2 0 01-2-2V7a2 2 0 012-2z"
                />
              </svg>
            </div>
            <h3 className="text-xl font-semibold text-foreground">
              Risk Detection
            </h3>
            <p className="text-muted-foreground">
              Automated alerts ranked by severity with actionable remediation
              guidance for every finding.
            </p>
          </Card>
        </div>
      </section>

      {/* CTA Section */}
      <section className="border-t bg-background px-6 py-20">
        <div className="mx-auto max-w-3xl text-center">
          <h2 className="text-3xl font-bold text-foreground">
            Ready to eliminate contract conflicts?
          </h2>
          <p className="mt-4 text-lg text-muted-foreground">
            Join enterprise teams detecting millions in savings with C2Pro.
          </p>
          <Link href="/signup" className="mt-8 inline-block">
            <Button size="lg" className="bg-primary hover:bg-primary/90">
              Start Your Free Trial
            </Button>
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t bg-card px-6 py-8">
        <div className="mx-auto flex max-w-5xl items-center justify-between">
          <div className="text-sm text-muted-foreground">
            © 2026 C2Pro. All rights reserved.
          </div>
          <div className="flex gap-6 text-sm text-muted-foreground">
            <a href="#" className="hover:text-foreground">
              Privacy
            </a>
            <a href="#" className="hover:text-foreground">
              Terms
            </a>
            <a href="#" className="hover:text-foreground">
              Contact
            </a>
          </div>
        </div>
      </footer>
    </div>
  );
}

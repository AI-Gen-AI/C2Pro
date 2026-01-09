import React from 'react';
import Link from 'next/link'; // Import Link for Next.js navigation

interface DashboardLayoutProps {
  children: React.ReactNode;
}

export default function DashboardLayout({ children }: DashboardLayoutProps) {
  return (
    <div className="flex flex-col min-h-screen bg-gray-100">
      <header className="bg-white shadow-sm p-4 border-b border-gray-200">
        <nav className="flex space-x-4">
          <Link href="/dashboard" className="text-blue-600 hover:text-blue-800 font-medium">Dashboard</Link>
          <Link href="/dashboard/projects" className="text-blue-600 hover:text-blue-800 font-medium">Projects</Link>
          <Link href="/dashboard/observability" className="text-blue-600 hover:text-blue-800 font-medium">Observability</Link>
        </nav>
      </header>
      <main className="flex-grow p-4">
        {children}
      </main>
      <footer className="bg-white shadow-sm p-4 border-t border-gray-200 text-center text-gray-500 text-sm">
        <p>&copy; {new Date().getFullYear()} C2Pro</p>
      </footer>
    </div>
  );
}
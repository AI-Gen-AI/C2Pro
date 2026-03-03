'use client';

import { useEffect } from 'react';

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error('[GlobalError]', error);
  }, [error]);

  return (
    <html lang="en">
      <body className="flex min-h-screen items-center justify-center bg-gray-50 font-sans text-gray-900 antialiased">
        <div className="flex flex-col items-center text-center">
          <div className="rounded-full bg-red-100 p-4">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              className="h-8 w-8 text-red-600"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth={2}
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z" />
              <path d="M12 9v4" />
              <path d="M12 17h.01" />
            </svg>
          </div>
          <h2 className="mt-4 text-lg font-semibold">
            Application Error
          </h2>
          <p className="mt-2 max-w-md text-sm text-gray-600">
            A critical error occurred. Please try refreshing the page.
          </p>
          {error.digest ? (
            <p className="mt-1 font-mono text-xs text-gray-500">
              Error ID: {error.digest}
            </p>
          ) : null}
          <button
            onClick={reset}
            className="mt-6 rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 shadow-sm hover:bg-gray-50"
          >
            Try again
          </button>
        </div>
      </body>
    </html>
  );
}

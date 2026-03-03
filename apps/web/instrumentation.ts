export async function register() {
  if (process.env.NEXT_PUBLIC_APP_MODE !== "demo") {
    return;
  }

  // Demo mode: MSW runs client-side only in development.
  // Server-side MSW requires additional bundling config.
  // For now, log that demo mode is active and rely on client-side mocking.
  console.log("[C2Pro] Demo mode active - client-side mocking enabled");
}

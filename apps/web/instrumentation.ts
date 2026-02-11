export async function register() {
  if (process.env.NEXT_PUBLIC_APP_MODE !== "demo") {
    return;
  }

  // Avoid static module resolution in non-demo runs.
  const dynamicImport = new Function("path", "return import(path)") as (
    path: string,
  ) => Promise<{ server: { listen: (opts: { onUnhandledRequest: "bypass" }) => void } }>;

  const { server } = await dynamicImport("./mocks/node");
  server.listen({ onUnhandledRequest: "bypass" });
  console.log("[C2Pro] MSW server-side mocking active (demo mode)");
}

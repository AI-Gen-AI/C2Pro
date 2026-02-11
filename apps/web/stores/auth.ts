import { create } from "zustand";
import { devtools } from "zustand/middleware";

interface AuthState {
  token: string | null;
  tenantId: string | null;
  setAuth: (auth: { token: string | null; tenantId: string | null }) => void;
  clear: () => void;
}

export const useAuthStore = create<AuthState>()(
  devtools(
    (set) => ({
      token: null,
      tenantId: null,
      setAuth: ({ token, tenantId }) => set({ token, tenantId }),
      clear: () => set({ token: null, tenantId: null }),
    }),
    { name: "c2pro-auth" },
  ),
);

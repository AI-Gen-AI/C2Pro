import { QueryClient } from "@tanstack/react-query";

export const queryClientConfig = {
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000,
    },
  },
};

export const createQueryClient = () => new QueryClient(queryClientConfig);

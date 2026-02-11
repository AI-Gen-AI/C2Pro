import { defineConfig } from "orval";

export default defineConfig({
  c2pro: {
    input: {
      target: "./openapi.json",
      validation: true,
    },
    output: {
      target: "./lib/api/generated/endpoints.ts",
      client: "react-query",
      mode: "tags-split",
      httpClient: "axios",
      override: {
        mutator: {
          path: "./lib/api/client.ts",
          name: "apiClient",
        },
        query: {
          useQuery: true,
          useMutation: true,
        },
        mock: {
          type: "msw",
          useExamples: true,
          delay: "real",
          baseUrl: "",
        },
      },
    },
  },
});

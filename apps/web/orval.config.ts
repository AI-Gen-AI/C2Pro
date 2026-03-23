import { defineConfig } from "orval";

export default defineConfig({
  c2pro: {
    input: {
      target: "./schema/api.json",
      validation: true,
    },
    output: {
      target: "./lib/api/generated/endpoints.ts",
      schemas: "./lib/api/generated/models",
      client: "react-query",
      mode: "tags-split",
      httpClient: "axios",
      clean: true,
      override: {
        mutator: {
          path: "./lib/api/client.ts",
          name: "orvalApiClient",
        },
        query: {
          useQuery: true,
          useMutation: true,
          useInfinite: false,
        },
        mock: {
          type: "msw",
          useExamples: true,
          delay: "real",
          baseUrl: "",
          // Isolate mocks to their own folder for production exclusion
          output: "./lib/api/generated/__mocks__",
        },
      },
    },
  },
});

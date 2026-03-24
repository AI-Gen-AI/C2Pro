import js from "@eslint/js";

export default [
  {
    ignores: [
      "everything-claude-code/**",
      "tmp-gh-artifacts/**",
      "apps/api/.pytest-tmp-local/**",
    ],
  },
  {
    ...js.configs.recommended,
    languageOptions: {
      ecmaVersion: "latest",
      sourceType: "module",
      globals: {
        // Using built-in browser and node globals from @eslint/js
        ...js.configs.browser,
        ...js.configs.node,
      },
    },
    rules: {},
  },
];

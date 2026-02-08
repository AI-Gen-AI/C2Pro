import js from '@eslint/js';

export default [
  {
    ...js.configs.recommended,
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'module',
      globals: {
        // Using built-in browser and node globals from @eslint/js
        ...js.configs.browser,
        ...js.configs.node,
      },
    },
    rules: {},
  },
];

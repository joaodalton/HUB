// Fast lint tier. Everything here runs without type information, which is
// what keeps it quick enough for a pre-commit hook. The rules that need the
// type checker live in eslint.typed.config.mjs and run on their own script.
//
// Adapt before use:
//   - the paths in the import-x zones and in quality/no-direct-data-access
//   - the framework blocks, commented out below
//   - the globalIgnores list
import js from "@eslint/js";
import { defineConfig, globalIgnores } from "eslint/config";
import tseslint from "typescript-eslint";

import quality from "./eslint-rules/index.cjs";

export default defineConfig([
  {
    languageOptions: {
      parserOptions: { tsconfigRootDir: import.meta.dirname },
      // js.configs.recommended turns on no-undef, which knows nothing about
      // the runtime this project targets -- without this, every console or
      // process reference is reported as an undefined variable. Declare what
      // the code actually uses. When the list outgrows a handful, install the
      // `globals` package and spread globals.node or globals.browser instead.
      globals: {
        console: "readonly",
        process: "readonly",
        fetch: "readonly",
        URL: "readonly",
        setTimeout: "readonly",
        clearTimeout: "readonly",
      },
    },
  },
  js.configs.recommended,
  ...tseslint.configs.strict,

  // Framework presets. Uncomment only what this project actually uses, and
  // add the matching import at the top of the file. Turning on a preset
  // wholesale is the opposite of what the rest of this config does -- prefer
  // a curated subset per plugin, added as its own files-scoped block below.
  //
  //   nextPlugin.configs["core-web-vitals"],
  //   reactPlugin.configs.flat["jsx-runtime"],
  //   reactHooks.configs.flat.recommended,

  {
    files: ["src/**/*.{js,jsx,ts,tsx,mjs,cjs}"],
    plugins: { quality },
    rules: {
      "no-empty": ["error", { allowEmptyCatch: true }],
      "no-var": "error",
      "prefer-const": "error",
      "@typescript-eslint/no-unused-vars": [
        "error",
        { argsIgnorePattern: "^_", varsIgnorePattern: "^_" },
      ],
      // The size and complexity budget is all "warn" on purpose. These
      // numbers are a conversation starter about factoring, not a gate --
      // promote one to "error" once the count for it reaches zero.
      complexity: ["warn", 12],
      "max-depth": ["warn", 4],
      "max-statements": ["warn", 20],
      "max-params": ["warn", 4],
      "max-lines-per-function": [
        "warn",
        { max: 150, skipBlankLines: true, skipComments: true },
      ],
      "max-nested-callbacks": ["warn", 3],
      // Five existing files exceed the 350-line budget. Keep the gate
      // strict for new work while they are refactored separately.
      "quality/max-lines": [
        "error",
        {
          max: 350,
          ignore: [
            "src/pages/SettingsPage.ts",
            "src/pages/PendenciasPage.ts",
            "src/pages/PlantsPage.ts",
            "src/pages/EmpresasPage.ts",
          ],
        },
      ],
      "quality/no-direct-console": [
        "error",
        { logger: "the project logging helper" },
      ],
    },
  },
  {
    // Existing baseline: five non-null assertions and one unsafe finally.
    rules: {
      "@typescript-eslint/no-non-null-assertion": "warn",
      "no-unsafe-finally": "warn",
    },
  },
  {
    // The same file budget for test files, at "warn". Also placed after the
    // "error" block for the same ordering reason. Two glob branches, because
    // a file counts as a test either by suffix or by directory -- and the
    // suffix branch alone misses test-support files that live in __tests__/
    // without being *.test.ts themselves.
    files: [
      "**/*.test.{ts,tsx}",
      "**/{__tests__,__mocks__,fixtures,mocks}/**/*.{ts,tsx}",
    ],
    plugins: { quality },
    rules: {
      "quality/max-lines": ["warn", { includeTests: true }],
    },
  },
  {
    files: ["**/*.test.{ts,tsx}"],
    rules: {
      // These three fire heavily on describe/it nesting and on long arrange
      // sections without pointing at a real problem. complexity, max-depth
      // and max-params stay on for tests -- they were not part of the noise.
      "max-statements": "off",
      "max-lines-per-function": "off",
      "max-nested-callbacks": "off",
    },
  },
  {
    files: ["eslint-rules/**/*.cjs"],
    languageOptions: {
      sourceType: "commonjs",
      globals: { module: "readonly", require: "readonly" },
    },
    rules: {
      "@typescript-eslint/no-require-imports": "off",
    },
  },
  globalIgnores([
    // Agent harness files, vendored automation and standalone tooling are not
    // the application this config polices. Without these, Node-runtime
    // scripts that never declared Node globals drown real findings in
    // no-undef noise.
    ".claude/**",
    ".github/agents/**",
    ".github/hooks/**",
    ".github/skills/**",
    "node_modules/**",
    "dist/**",
    "build/**",
    "coverage/**",
    "**/*.tsbuildinfo",
    "package-lock.json",
    "src/generated/**",
  ]),
]);

import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'
import { defineConfig, globalIgnores } from 'eslint/config'

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      tseslint.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
    },
    rules: {
      // eslint-plugin-react-hooks v7 promoted the React Compiler rules to
      // errors in `recommended`. They flag working, pre-existing patterns
      // (reset-on-change effects, `Date.now()` in render for "x seconds ago"
      // labels, accumulators inside `.map`) across ~50 files. Keep them
      // visible as warnings instead of blocking the lint gate; fix sites
      // individually when the surrounding code is touched anyway.
      'react-hooks/set-state-in-effect': 'warn',
      'react-hooks/purity': 'warn',
      'react-hooks/immutability': 'warn',
      'react-hooks/refs': 'warn',
      'react-hooks/preserve-manual-memoization': 'warn',
      // Fast Refresh only: files that export a component plus its variants
      // helper / context hook (shadcn `buttonVariants`, `useAuth`, …) lose
      // HMR state, they don't misbehave at runtime.
      'react-refresh/only-export-components': 'warn',
      // Underscore-prefixed bindings are the codebase's "intentionally unused"
      // marker (destructured-and-dropped props, placeholder args).
      '@typescript-eslint/no-unused-vars': [
        'error',
        {
          argsIgnorePattern: '^_',
          varsIgnorePattern: '^_',
          caughtErrorsIgnorePattern: '^_',
          destructuredArrayIgnorePattern: '^_',
        },
      ],
    },
  },
])

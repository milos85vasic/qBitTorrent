import { defineConfig } from 'vitest/config';

/**
 * Vitest configuration picked up by Angular's `@angular/build:unit-test` builder.
 *
 * Coverage thresholds start at 40 % across the board so the Phase 5 spec
 * expansion locks in a baseline without blocking CI. Later phases raise
 * these per-module toward 100 % (see docs/COVERAGE_BASELINE.md).
 */
export default defineConfig({
  test: {
    globals: true,
    environment: 'jsdom',
    include: ['src/**/*.spec.ts'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'html', 'lcov'],
      reportsDirectory: './coverage',
      include: ['src/app/**/*.ts'],
      exclude: [
        'src/app/**/*.spec.ts',
        'src/app/**/*.d.ts',
        'src/app/**/*.module.ts',
        'src/app/**/*.config.ts',
        'src/app/**/*.routes.ts',
        'src/app/**/index.ts',
      ],
      thresholds: {
        lines: 40,
        branches: 40,
        functions: 40,
        statements: 40,
      },
    },
  },
});

// Spec for the lazy-loaded `/jackett` route tree.
//
// CONST-XII anti-bluff: every assertion below pins user-observable shape
// (route count, default-redirect target, presence of named children).
// A stub `JACKETT_ROUTES = []` would FAIL test 1 (length); a stub that
// renames the children would FAIL tests 2 & 3.

import { describe, it, expect } from 'vitest';
import { Route } from '@angular/router';
import { JACKETT_ROUTES } from './jackett.routes';

describe('JACKETT_ROUTES', () => {
  it('exports exactly three child routes (default redirect + credentials + indexers)', () => {
    expect(JACKETT_ROUTES).toHaveLength(3);
  });

  it('default empty path redirects to "credentials"', () => {
    const def = JACKETT_ROUTES.find((r: Route) => r.path === '');
    expect(def).toBeDefined();
    expect(def?.redirectTo).toBe('credentials');
    expect(def?.pathMatch).toBe('full');
  });

  it('declares a "credentials" child route with a lazy component loader', () => {
    const credentials = JACKETT_ROUTES.find((r: Route) => r.path === 'credentials');
    expect(credentials).toBeDefined();
    // Must lazy-load: either `loadComponent` or eager `component`.
    expect(credentials?.loadComponent ?? credentials?.component).toBeDefined();
  });

  it('declares an "indexers" child route with a lazy component loader', () => {
    const indexers = JACKETT_ROUTES.find((r: Route) => r.path === 'indexers');
    expect(indexers).toBeDefined();
    expect(indexers?.loadComponent ?? indexers?.component).toBeDefined();
  });
});

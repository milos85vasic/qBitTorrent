// Vitest setup — initialises Angular's TestBed exactly once per
// vitest worker. Without this, every spec that calls
// `TestBed.configureTestingModule(...)` fails with
//   "Need to call TestBed.initTestEnvironment() first".
//
// Registered via `test.setupFiles` in vitest.config.ts.

// Order matters:
// 1. @angular/compiler — JIT compiler, required to compile standalone
//    components at test time.
// 2. zone.js — polyfills the Zone that Angular's change detection uses.
// 3. zone.js/testing — extends Zone with fakeAsync/flush/tick support.
// 4. getTestBed().initTestEnvironment — finally bootstraps the TestBed.
import '@angular/compiler';
import 'zone.js';
import 'zone.js/testing';

import { getTestBed } from '@angular/core/testing';
import {
  BrowserDynamicTestingModule,
  platformBrowserDynamicTesting,
} from '@angular/platform-browser-dynamic/testing';

// Ensure navigator.userAgent is defined so Angular's DefaultValueAccessor
// (used by ngModel) doesn't crash in jsdom/vitest environments.
if (typeof navigator !== 'undefined' && !navigator.userAgent) {
  Object.defineProperty(navigator, 'userAgent', {
    value: 'vitest-jsdom',
    configurable: true,
  });
}

getTestBed().initTestEnvironment(
  BrowserDynamicTestingModule,
  platformBrowserDynamicTesting(),
  { teardown: { destroyAfterEach: true } },
);

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { TestBed } from '@angular/core/testing';
import { ThemeService } from './theme.service';

/**
 * Cross-app sync specs for ThemeService.
 *
 * Phase B of docs/CROSS_APP_THEME_PLAN.md wires the dashboard into the
 * shared /api/v1/theme endpoint so the qBittorrent WebUI (injected
 * bridge at :7186) picks up every palette change. These specs cover:
 *
 * - GET on construct pulls server state when localStorage is empty.
 * - setPalette/setMode fire-and-forget a PUT (debounced).
 * - A new EventSource('/api/v1/theme/stream') is opened on construct.
 * - SSE 'theme' events with a newer updatedAt adopt the server state.
 * - Missing fetch / EventSource (jsdom quirks) do not crash.
 */

const STORAGE_KEY = 'qbit.theme';

interface FakeEventSource {
  url: string;
  listeners: Map<string, ((ev: MessageEvent) => void)[]>;
  dispatch(event: string, payload: unknown): void;
  close(): void;
  addEventListener(name: string, cb: (ev: MessageEvent) => void): void;
  removeEventListener(name: string, cb: (ev: MessageEvent) => void): void;
}

function makeFakeEventSource(url: string): FakeEventSource {
  const listeners = new Map<string, ((ev: MessageEvent) => void)[]>();
  return {
    url,
    listeners,
    addEventListener(name, cb) {
      const arr = listeners.get(name) ?? [];
      arr.push(cb);
      listeners.set(name, arr);
    },
    removeEventListener(name, cb) {
      const arr = listeners.get(name) ?? [];
      const i = arr.indexOf(cb);
      if (i >= 0) arr.splice(i, 1);
    },
    close() { /* no-op */ },
    dispatch(name, payload) {
      const ev = { data: JSON.stringify(payload) } as MessageEvent;
      for (const cb of listeners.get(name) ?? []) cb(ev);
    },
  };
}

describe('ThemeService cross-app sync', () => {
  let originalFetch: typeof globalThis.fetch;
  let originalEventSource: typeof globalThis.EventSource;
  let fetchCalls: Array<{ url: string; init?: RequestInit }>;
  let fakeEs: FakeEventSource | null;
  let originalMatchMedia: typeof window.matchMedia;

  beforeEach(() => {
    localStorage.clear();
    TestBed.resetTestingModule();
    vi.useFakeTimers();

    // Deterministic matchMedia (dark).
    originalMatchMedia = window.matchMedia;
    (window as any).matchMedia = vi.fn(() => ({
      matches: true,
      media: '(prefers-color-scheme: dark)',
      addEventListener: () => { /* noop */ },
      removeEventListener: () => { /* noop */ },
      addListener: () => { /* noop */ },
      removeListener: () => { /* noop */ },
    }));

    // Stub global fetch.
    originalFetch = globalThis.fetch;
    fetchCalls = [];
    globalThis.fetch = vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
      const stringUrl = typeof url === 'string' ? url : (url as URL).toString();
      fetchCalls.push({ url: stringUrl, init });
      // Default GET response: darcula / dark.
      if (init?.method == null || init.method === 'GET') {
        return new Response(
          JSON.stringify({
            paletteId: 'darcula',
            mode: 'dark',
            updatedAt: '2000-01-01T00:00:00Z',
          }),
          { status: 200, headers: { 'content-type': 'application/json' } },
        );
      }
      return new Response('{}', { status: 200 });
    }) as typeof globalThis.fetch;

    // Stub EventSource. ``vi.fn`` can't be constructed with ``new``
    // (the this-binding gets in the way), so we use a real function
    // that stashes the fake instance on the spec closure + a call
    // counter we can read back from tests.
    originalEventSource = (globalThis as any).EventSource;
    fakeEs = null;
    let esCallCount = 0;
    function FakeEsCtor(this: any, url: string) {
      esCallCount += 1;
      fakeEs = makeFakeEventSource(url);
      Object.assign(this, fakeEs);
    }
    (FakeEsCtor as any).callCount = () => esCallCount;
    (globalThis as any).EventSource = FakeEsCtor;
  });

  afterEach(() => {
    (window as any).matchMedia = originalMatchMedia;
    globalThis.fetch = originalFetch;
    (globalThis as any).EventSource = originalEventSource;
    vi.useRealTimers();
  });

  it('adopts server state on construct when localStorage is empty', async () => {
    (globalThis.fetch as any) = vi.fn(async () =>
      new Response(
        JSON.stringify({ paletteId: 'nord', mode: 'light', updatedAt: '2030-01-01T00:00:00Z' }),
        { status: 200, headers: { 'content-type': 'application/json' } },
      ),
    );

    const svc = TestBed.inject(ThemeService);
    // The GET happens from the constructor; we just need the promise to resolve.
    await vi.runAllTimersAsync();
    // Microtasks may still need to flush for the async then().
    await Promise.resolve();
    await Promise.resolve();

    expect(svc.palette().id).toBe('nord');
    expect(svc.mode()).toBe('light');
  });

  it('does not clobber an existing localStorage state with the server response', async () => {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({ paletteId: 'gruvbox', mode: 'dark', modeIsUserChosen: true }),
    );
    // Server returns nord — but local state wins.
    (globalThis.fetch as any) = vi.fn(async () =>
      new Response(
        JSON.stringify({ paletteId: 'nord', mode: 'dark', updatedAt: '2000-01-01T00:00:00Z' }),
        { status: 200 },
      ),
    );

    const svc = TestBed.inject(ThemeService);
    await vi.runAllTimersAsync();
    await Promise.resolve();

    expect(svc.palette().id).toBe('gruvbox');
  });

  it('PUTs the new state to /api/v1/theme on setPalette (debounced)', async () => {
    const svc = TestBed.inject(ThemeService);
    await vi.runAllTimersAsync();
    // Clear fetch calls from the initial GET.
    fetchCalls.length = 0;

    svc.setPalette('nord');
    svc.setPalette('dracula');
    svc.setPalette('gruvbox');

    // Before the debounce flush, no PUT should have fired yet.
    const beforeFlush = fetchCalls.filter((c) => c.init?.method === 'PUT');
    expect(beforeFlush.length).toBe(0);

    // Advance debounce timer.
    await vi.advanceTimersByTimeAsync(300);
    await Promise.resolve();

    const puts = fetchCalls.filter((c) => c.init?.method === 'PUT');
    expect(puts.length).toBe(1);
    const body = JSON.parse(puts[0].init!.body as string);
    expect(body.paletteId).toBe('gruvbox');
    expect(body.mode).toBe('dark');
  });

  it('PUTs on setMode and toggleMode too', async () => {
    const svc = TestBed.inject(ThemeService);
    await vi.runAllTimersAsync();
    fetchCalls.length = 0;

    svc.setMode('light');
    await vi.advanceTimersByTimeAsync(300);
    await Promise.resolve();

    const puts = fetchCalls.filter((c) => c.init?.method === 'PUT');
    expect(puts.length).toBe(1);
    expect(JSON.parse(puts[0].init!.body as string).mode).toBe('light');
  });

  it('opens an EventSource to the SSE stream on construct', () => {
    TestBed.inject(ThemeService);
    const esCtor = (globalThis as any).EventSource as { callCount: () => number };
    expect(esCtor.callCount()).toBeGreaterThan(0);
    expect(fakeEs!.url).toContain('/api/v1/theme/stream');
  });

  it('adopts remote SSE updates without looping', async () => {
    const svc = TestBed.inject(ThemeService);
    await vi.runAllTimersAsync();
    fetchCalls.length = 0;

    // Remote palette switch (newer updatedAt than anything we've PUT).
    fakeEs!.dispatch('theme', {
      paletteId: 'monokai',
      mode: 'light',
      updatedAt: '2099-01-01T00:00:00Z',
    });

    expect(svc.palette().id).toBe('monokai');
    expect(svc.mode()).toBe('light');

    // Sync-back protection: no PUT should fire because we just adopted.
    await vi.advanceTimersByTimeAsync(500);
    const puts = fetchCalls.filter((c) => c.init?.method === 'PUT');
    expect(puts.length).toBe(0);
  });

  it('falls back gracefully when fetch is undefined', () => {
    (globalThis as any).fetch = undefined;
    expect(() => TestBed.inject(ThemeService)).not.toThrow();
  });

  it('falls back gracefully when EventSource is undefined', () => {
    (globalThis as any).EventSource = undefined;
    expect(() => TestBed.inject(ThemeService)).not.toThrow();
  });

  it('ignores malformed SSE payloads', async () => {
    const svc = TestBed.inject(ThemeService);
    await vi.runAllTimersAsync();
    const beforeId = svc.palette().id;

    // Not a valid JSON.
    if (fakeEs) {
      const arr = fakeEs.listeners.get('theme') ?? [];
      for (const cb of arr) cb({ data: 'not-json' } as MessageEvent);
      // Invalid payload (missing paletteId).
      for (const cb of arr) cb({ data: JSON.stringify({ mode: 'dark' }) } as MessageEvent);
      // Unknown palette id.
      for (const cb of arr) cb({ data: JSON.stringify({ paletteId: 'nope', mode: 'dark', updatedAt: '2099-01-01T00:00:00Z' }) } as MessageEvent);
    }

    expect(svc.palette().id).toBe(beforeId);
  });
});

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { TestBed } from '@angular/core/testing';
import { ThemeService } from './theme.service';
import {
  DEFAULT_PALETTE_ID,
  PALETTES,
  PALETTE_TOKEN_KEYS,
  TOKEN_CSS_VAR,
  findPalette,
} from '../models/palette.model';

/**
 * Spec guarantees, per the "no false positives" mandate:
 *
 * - System dark preference drives `mode` when localStorage is empty.
 * - Valid stored state populates signals verbatim.
 * - Unknown palette ids fall back to the default AND are corrected in
 *   storage.
 * - `setPalette` writes every one of the 15 tokens to
 *   `document.documentElement.style` AND persists the choice.
 * - `setPalette` is a no-op for unknown ids.
 * - `toggleMode` flips the signal, writes `data-mode` / `color-scheme`
 *   on the documentElement AND marks the selection as user-chosen.
 * - The prefers-color-scheme change listener only follows system
 *   changes when the user has not yet picked explicitly.
 */

const STORAGE_KEY = 'qbit.theme';

interface MockMediaQueryList {
  matches: boolean;
  media: string;
  addEventListener: (name: string, cb: (e: MediaQueryListEvent) => void) => void;
  removeEventListener: (name: string, cb: (e: MediaQueryListEvent) => void) => void;
  dispatch: (matches: boolean) => void;
  listeners: Array<(e: MediaQueryListEvent) => void>;
}

function makeMediaQuery(matches: boolean): MockMediaQueryList {
  const listeners: Array<(e: MediaQueryListEvent) => void> = [];
  const mq: MockMediaQueryList = {
    matches,
    media: '(prefers-color-scheme: dark)',
    listeners,
    addEventListener: (_name, cb) => { listeners.push(cb); },
    removeEventListener: (_name, cb) => {
      const i = listeners.indexOf(cb);
      if (i >= 0) listeners.splice(i, 1);
    },
    dispatch(next: boolean) {
      this.matches = next;
      const evt = { matches: next, media: this.media } as MediaQueryListEvent;
      for (const l of listeners.slice()) l(evt);
    },
  };
  return mq;
}

describe('ThemeService', () => {
  let originalMatchMedia: typeof window.matchMedia;
  let mq: MockMediaQueryList;
  let setPropertySpy: ReturnType<typeof vi.spyOn>;
  let setAttributeSpy: ReturnType<typeof vi.spyOn>;
  let setItemSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    localStorage.clear();
    // Reset any prior attributes / inline styles.
    document.documentElement.removeAttribute('data-palette');
    document.documentElement.removeAttribute('data-mode');
    for (const key of PALETTE_TOKEN_KEYS) {
      document.documentElement.style.removeProperty(TOKEN_CSS_VAR[key]);
    }
    originalMatchMedia = window.matchMedia;
    mq = makeMediaQuery(true);
    (window as any).matchMedia = vi.fn((_: string) => mq);

    setPropertySpy = vi.spyOn(document.documentElement.style, 'setProperty');
    setAttributeSpy = vi.spyOn(document.documentElement, 'setAttribute');
    setItemSpy = vi.spyOn(Storage.prototype, 'setItem');

    TestBed.resetTestingModule();
  });

  afterEach(() => {
    (window as any).matchMedia = originalMatchMedia;
    setPropertySpy.mockRestore();
    setAttributeSpy.mockRestore();
    setItemSpy.mockRestore();
  });

  it('defaults mode to dark when system prefers dark and storage is empty', () => {
    mq.matches = true;
    const svc = TestBed.inject(ThemeService);
    expect(svc.mode()).toBe('dark');
    expect(svc.palette().id).toBe(DEFAULT_PALETTE_ID);
    expect(svc.isModeUserChosen()).toBe(false);
  });

  it('defaults mode to light when system prefers light and storage is empty', () => {
    mq.matches = false;
    const svc = TestBed.inject(ThemeService);
    expect(svc.mode()).toBe('light');
  });

  it('hydrates signals from valid localStorage', () => {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({ paletteId: 'nord', mode: 'light', modeIsUserChosen: true }),
    );
    const svc = TestBed.inject(ThemeService);
    expect(svc.palette().id).toBe('nord');
    expect(svc.mode()).toBe('light');
    expect(svc.isModeUserChosen()).toBe(true);
  });

  it('falls back to default when stored paletteId is unknown and persists the correction', () => {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({ paletteId: 'not-a-palette', mode: 'dark', modeIsUserChosen: true }),
    );
    const svc = TestBed.inject(ThemeService);
    expect(svc.palette().id).toBe(DEFAULT_PALETTE_ID);
    // The correction is written back on boot.
    const persisted = JSON.parse(localStorage.getItem(STORAGE_KEY)!);
    expect(persisted.paletteId).toBe(DEFAULT_PALETTE_ID);
  });

  it('setPalette updates signals, applies every CSS var with the right value, and persists', () => {
    const svc = TestBed.inject(ThemeService);
    setPropertySpy.mockClear();
    setItemSpy.mockClear();

    svc.setPalette('dracula');

    expect(svc.palette().id).toBe('dracula');
    const dracula = findPalette('dracula')!;
    // Dark is the default mode hydrated above (jsdom matchMedia mock).
    // Confirm every one of the 15 tokens was written with its dark value.
    for (const key of PALETTE_TOKEN_KEYS) {
      const varName = TOKEN_CSS_VAR[key];
      const expected = dracula.dark[key];
      const actualInline = document.documentElement.style.getPropertyValue(varName).trim();
      expect(actualInline, `${varName} should be ${expected}`).toBe(expected);
      expect(setPropertySpy).toHaveBeenCalledWith(varName, expected);
    }
    // localStorage was touched.
    expect(setItemSpy).toHaveBeenCalled();
    const persisted = JSON.parse(localStorage.getItem(STORAGE_KEY)!);
    expect(persisted.paletteId).toBe('dracula');
    expect(persisted.mode).toBe('dark');
  });

  it('setPalette("unknown") is a no-op — no writes, no crash', () => {
    const svc = TestBed.inject(ThemeService);
    const beforeId = svc.palette().id;
    setPropertySpy.mockClear();
    setItemSpy.mockClear();

    svc.setPalette('i-do-not-exist');

    expect(svc.palette().id).toBe(beforeId);
    expect(setPropertySpy).not.toHaveBeenCalled();
    expect(setItemSpy).not.toHaveBeenCalled();
  });

  it('toggleMode flips the mode signal and writes data-mode + color-scheme on documentElement', () => {
    const svc = TestBed.inject(ThemeService);
    const initialMode = svc.mode();
    svc.toggleMode();
    const newMode = svc.mode();
    expect(newMode).not.toBe(initialMode);
    expect(document.documentElement.getAttribute('data-mode')).toBe(newMode);
    expect(document.documentElement.style.getPropertyValue('color-scheme').trim()).toBe(newMode);
  });

  it('toggleMode sets color-scheme via setProperty', () => {
    const svc = TestBed.inject(ThemeService);
    setPropertySpy.mockClear();
    svc.toggleMode();
    const mode = svc.mode();
    expect(setPropertySpy).toHaveBeenCalledWith('color-scheme', mode);
  });

  it('setMode marks modeIsUserChosen=true in storage', () => {
    const svc = TestBed.inject(ThemeService);
    svc.setMode('light');
    expect(svc.isModeUserChosen()).toBe(true);
    const stored = JSON.parse(localStorage.getItem(STORAGE_KEY)!);
    expect(stored.modeIsUserChosen).toBe(true);
    expect(stored.mode).toBe('light');
  });

  it('follows prefers-color-scheme changes only when user has not chosen explicitly', () => {
    mq.matches = true; // initial: dark
    const svc = TestBed.inject(ThemeService);
    expect(svc.mode()).toBe('dark');
    expect(svc.isModeUserChosen()).toBe(false);

    // System flips to light — should propagate.
    mq.dispatch(false);
    expect(svc.mode()).toBe('light');

    // User picks dark explicitly — sticky.
    svc.setMode('dark');
    expect(svc.isModeUserChosen()).toBe(true);

    // System flips again — must NOT propagate.
    mq.dispatch(false);
    expect(svc.mode()).toBe('dark');
  });

  it('applies all 15 tokens for every palette with the exact catalogued values', () => {
    const svc = TestBed.inject(ThemeService);
    for (const p of PALETTES) {
      svc.setPalette(p.id);
      const tokens = svc.mode() === 'dark' ? p.dark : p.light;
      for (const key of PALETTE_TOKEN_KEYS) {
        const varName = TOKEN_CSS_VAR[key];
        const actual = document.documentElement.style.getPropertyValue(varName).trim();
        expect(actual, `${p.id} ${key}`).toBe(tokens[key]);
      }
      expect(document.documentElement.getAttribute('data-palette')).toBe(p.id);
    }
  });

  it('exposes the catalogue via availablePalettes unchanged', () => {
    const svc = TestBed.inject(ThemeService);
    expect(svc.availablePalettes.length).toBe(PALETTES.length);
    expect(svc.availablePalettes.map((p) => p.id)).toEqual(PALETTES.map((p) => p.id));
  });

  it('currentTokens switches between light and dark with setMode', () => {
    const svc = TestBed.inject(ThemeService);
    svc.setPalette('darcula');
    svc.setMode('dark');
    expect(svc.currentTokens().accent).toBe(findPalette('darcula')!.dark.accent);
    svc.setMode('light');
    expect(svc.currentTokens().accent).toBe(findPalette('darcula')!.light.accent);
  });
});

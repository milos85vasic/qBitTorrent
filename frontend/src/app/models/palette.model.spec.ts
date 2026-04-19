import { describe, it, expect } from 'vitest';
import {
  DEFAULT_PALETTE_ID,
  PALETTES,
  PALETTE_TOKEN_KEYS,
  TOKEN_CSS_VAR,
  findPalette,
} from './palette.model';

/**
 * Pure in-process invariants for the palette catalogue. These mirror the
 * Python parametric test in `tests/unit/test_palette_catalog.py` but
 * live in the frontend suite so regressions flag at `ng test` time too.
 */

const HEX_RE = /^#[0-9a-f]{6}$/i;
const RGBA_RE = /^rgba\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*([0-9]*\.?[0-9]+)\s*\)$/i;

function isValidColour(val: string): boolean {
  if (HEX_RE.test(val)) return true;
  const m = RGBA_RE.exec(val);
  if (!m) return false;
  const [r, g, b, a] = [m[1], m[2], m[3], m[4]].map((n, i) => (i < 3 ? parseInt(n, 10) : parseFloat(n)));
  if ([r, g, b].some((c) => c < 0 || c > 255)) return false;
  if (a < 0 || a > 1) return false;
  return true;
}

describe('palette.model', () => {
  it('has at least one palette', () => {
    expect(PALETTES.length).toBeGreaterThan(0);
  });

  it('has unique palette ids', () => {
    const ids = PALETTES.map((p) => p.id);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it('DEFAULT_PALETTE_ID points at an existing palette', () => {
    expect(findPalette(DEFAULT_PALETTE_ID)).toBeDefined();
  });

  it('every palette has both light and dark variants with all 15 tokens', () => {
    for (const p of PALETTES) {
      for (const variant of ['light', 'dark'] as const) {
        const tokens = p[variant];
        for (const key of PALETTE_TOKEN_KEYS) {
          expect(tokens[key], `${p.id}.${variant}.${String(key)}`).toBeDefined();
          expect(isValidColour(tokens[key]), `${p.id}.${variant}.${String(key)}=${tokens[key]}`).toBe(true);
        }
      }
    }
  });

  it('Darcula accent is the blood-red #9d001e', () => {
    const darcula = findPalette('darcula');
    expect(darcula).toBeDefined();
    expect(darcula!.dark.accent.toLowerCase()).toBe('#9d001e');
  });

  it('TOKEN_CSS_VAR covers every token key', () => {
    for (const key of PALETTE_TOKEN_KEYS) {
      expect(TOKEN_CSS_VAR[key]).toMatch(/^--color-/);
    }
  });

  it('findPalette returns undefined for unknown ids', () => {
    expect(findPalette('not-a-real-palette')).toBeUndefined();
  });
});

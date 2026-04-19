import { Injectable, computed, signal } from '@angular/core';
import {
  DEFAULT_PALETTE_ID,
  Palette,
  PALETTES,
  PALETTE_TOKEN_KEYS,
  PaletteMode,
  PaletteTokens,
  TOKEN_CSS_VAR,
  findPalette,
} from '../models/palette.model';

/**
 * localStorage shape for the persisted theme choice.
 */
export interface StoredTheme {
  paletteId: string;
  mode: PaletteMode;
  /**
   * `true` if the user has explicitly picked `mode` via the UI. When
   * `false`, the service follows `prefers-color-scheme` changes. When
   * `true`, system-preference changes are ignored (the user wins).
   */
  modeIsUserChosen: boolean;
}

const STORAGE_KEY = 'qbit.theme';

@Injectable({ providedIn: 'root' })
export class ThemeService {
  /** Full palette catalogue — exposed for the picker. */
  readonly availablePalettes: readonly Palette[];

  /** Re-exported convenience for consumers that want to read the id list. */
  readonly paletteIds: readonly string[];

  private readonly _palette = signal<Palette>(findPalette(DEFAULT_PALETTE_ID)!);
  private readonly _mode = signal<PaletteMode>('dark');
  private _modeIsUserChosen = false;

  readonly palette = this._palette.asReadonly();
  readonly mode = this._mode.asReadonly();

  /** Active token set (derived from palette + mode). */
  readonly currentTokens = computed<PaletteTokens>(() => {
    const p = this._palette();
    return this._mode() === 'dark' ? p.dark : p.light;
  });

  private readonly documentRef: Document | null;
  private readonly storageRef: Storage | null;
  private readonly mediaQuery: MediaQueryList | null;
  private readonly mediaListener: ((e: MediaQueryListEvent) => void) | null;

  constructor() {
    this.availablePalettes = PALETTES;
    this.paletteIds = PALETTES.map((p) => p.id);
    this.documentRef = typeof document !== 'undefined' ? document : null;
    this.storageRef = this.safeLocalStorage();
    this.mediaQuery = this.resolveMediaQuery();

    const initial = this.resolveInitialState();
    this._palette.set(initial.palette);
    this._mode.set(initial.mode);
    this._modeIsUserChosen = initial.modeIsUserChosen;

    // Persist in case we fell back to defaults (corrects stale ids).
    this.persist();
    this.apply();

    if (this.mediaQuery) {
      this.mediaListener = (event: MediaQueryListEvent) => {
        if (this._modeIsUserChosen) return;
        this._mode.set(event.matches ? 'dark' : 'light');
        this.persist();
        this.apply();
      };
      // Prefer modern API; fall back to deprecated addListener for jsdom.
      if (typeof this.mediaQuery.addEventListener === 'function') {
        this.mediaQuery.addEventListener('change', this.mediaListener);
      } else if (typeof (this.mediaQuery as MediaQueryList).addListener === 'function') {
        (this.mediaQuery as MediaQueryList).addListener(this.mediaListener);
      }
    } else {
      this.mediaListener = null;
    }
  }

  /** Swap to a different palette by id. No-op if id is unknown. */
  setPalette(id: string): void {
    const next = findPalette(id);
    if (!next) return;
    if (next.id === this._palette().id) return;
    this._palette.set(next);
    this.persist();
    this.apply();
  }

  /** Set explicit light/dark mode (marks the user choice as sticky). */
  setMode(mode: PaletteMode): void {
    if (mode !== 'light' && mode !== 'dark') return;
    this._mode.set(mode);
    this._modeIsUserChosen = true;
    this.persist();
    this.apply();
  }

  /** Flip between light and dark. */
  toggleMode(): void {
    this.setMode(this._mode() === 'dark' ? 'light' : 'dark');
  }

  /** Mostly for tests: whether the user has chosen a mode explicitly. */
  isModeUserChosen(): boolean {
    return this._modeIsUserChosen;
  }

  /** For tests and cleanup — remove any listeners we installed. */
  dispose(): void {
    if (this.mediaQuery && this.mediaListener) {
      if (typeof this.mediaQuery.removeEventListener === 'function') {
        this.mediaQuery.removeEventListener('change', this.mediaListener);
      } else if (typeof (this.mediaQuery as MediaQueryList).removeListener === 'function') {
        (this.mediaQuery as MediaQueryList).removeListener(this.mediaListener);
      }
    }
  }

  // ----------------------------------------------------------------- internals

  private safeLocalStorage(): Storage | null {
    try {
      if (typeof localStorage === 'undefined') return null;
      // Touch it once to catch sandboxed throws.
      localStorage.getItem(STORAGE_KEY);
      return localStorage;
    } catch {
      return null;
    }
  }

  private resolveMediaQuery(): MediaQueryList | null {
    try {
      if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') {
        return null;
      }
      return window.matchMedia('(prefers-color-scheme: dark)');
    } catch {
      return null;
    }
  }

  private resolveInitialState(): { palette: Palette; mode: PaletteMode; modeIsUserChosen: boolean } {
    const stored = this.readStored();
    if (stored) {
      const palette = findPalette(stored.paletteId) ?? findPalette(DEFAULT_PALETTE_ID)!;
      const mode: PaletteMode = stored.mode === 'light' || stored.mode === 'dark' ? stored.mode : 'dark';
      return {
        palette,
        mode,
        modeIsUserChosen: !!stored.modeIsUserChosen,
      };
    }
    // No persisted theme — respect system preference.
    const systemDark = this.mediaQuery ? this.mediaQuery.matches : true;
    return {
      palette: findPalette(DEFAULT_PALETTE_ID)!,
      mode: systemDark ? 'dark' : 'light',
      modeIsUserChosen: false,
    };
  }

  private readStored(): StoredTheme | null {
    if (!this.storageRef) return null;
    const raw = this.storageRef.getItem(STORAGE_KEY);
    if (!raw) return null;
    try {
      const parsed = JSON.parse(raw) as Partial<StoredTheme>;
      if (!parsed || typeof parsed !== 'object' || typeof parsed.paletteId !== 'string') {
        return null;
      }
      return {
        paletteId: parsed.paletteId,
        mode: (parsed.mode === 'light' ? 'light' : 'dark'),
        modeIsUserChosen: !!parsed.modeIsUserChosen,
      };
    } catch {
      return null;
    }
  }

  private persist(): void {
    if (!this.storageRef) return;
    const payload: StoredTheme = {
      paletteId: this._palette().id,
      mode: this._mode(),
      modeIsUserChosen: this._modeIsUserChosen,
    };
    try {
      this.storageRef.setItem(STORAGE_KEY, JSON.stringify(payload));
    } catch {
      /* storage full or sandboxed — swallow */
    }
  }

  private apply(): void {
    const doc = this.documentRef;
    if (!doc || !doc.documentElement) return;
    const root = doc.documentElement;
    const tokens = this.currentTokens();
    for (const key of PALETTE_TOKEN_KEYS) {
      const varName = TOKEN_CSS_VAR[key];
      root.style.setProperty(varName, tokens[key]);
    }
    root.style.setProperty('color-scheme', this._mode());
    root.setAttribute('data-palette', this._palette().id);
    root.setAttribute('data-mode', this._mode());
  }
}

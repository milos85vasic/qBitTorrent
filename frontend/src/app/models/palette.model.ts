/**
 * Palette catalogue for the runtime-switchable theme system.
 *
 * Every palette ships a `light` and `dark` token set. Tokens are applied
 * to `document.documentElement` as CSS custom properties by
 * `ThemeService` so every app / dashboard / embedded surface picks them
 * up without hardcoded colours.
 *
 * Darcula's accent is the blood-red extracted from
 * `assets/Logo.jpeg` (`#9d001e`). The palette is based on the JetBrains
 * Darcula greys catalogued at https://colorshexa.com/palette/darcula-palette.
 *
 * When adding a palette:
 *   1. Keep every token a valid CSS colour (hex `#RRGGBB` or rgba(...)).
 *   2. Run `tests/unit/test_palette_catalog.py`.
 *   3. Run `tests/unit/test_theme_wiring.py`.
 *   4. Run `npx --prefix frontend ng test --watch=false`.
 */

export interface PaletteTokens {
  /** App background (main surface) */
  bgPrimary: string;
  /** Card / panel background */
  bgSecondary: string;
  /** Input / chip background (one step lighter than secondary in dark, darker in light) */
  bgTertiary: string;
  /** Borders + dividers */
  border: string;
  /** Primary readable text */
  textPrimary: string;
  /** Muted secondary text */
  textSecondary: string;
  /** Primary brand accent (used for CTAs, focus ring) */
  accent: string;
  /** Darker accent for hover */
  accentHover: string;
  /** Secondary brand accent (e.g. Darcula uses a warm gold next to the blood-red) */
  contrast: string;
  success: string;
  danger: string;
  warning: string;
  info: string;
  purple: string;
  /** Shadow rgba */
  shadow: string;
}

export type PaletteMode = 'light' | 'dark';

export interface Palette {
  id: string;
  name: string;
  description: string;
  /** Reference URL for the colour extraction source. */
  source: string;
  light: PaletteTokens;
  dark: PaletteTokens;
}

export const PALETTE_TOKEN_KEYS: readonly (keyof PaletteTokens)[] = [
  'bgPrimary',
  'bgSecondary',
  'bgTertiary',
  'border',
  'textPrimary',
  'textSecondary',
  'accent',
  'accentHover',
  'contrast',
  'success',
  'danger',
  'warning',
  'info',
  'purple',
  'shadow',
] as const;

/** Mapping from the camelCase palette token to the CSS custom property. */
export const TOKEN_CSS_VAR: Record<keyof PaletteTokens, string> = {
  bgPrimary: '--color-bg-primary',
  bgSecondary: '--color-bg-secondary',
  bgTertiary: '--color-bg-tertiary',
  border: '--color-border',
  textPrimary: '--color-text-primary',
  textSecondary: '--color-text-secondary',
  accent: '--color-accent',
  accentHover: '--color-accent-hover',
  contrast: '--color-contrast',
  success: '--color-success',
  danger: '--color-danger',
  warning: '--color-warning',
  info: '--color-info',
  purple: '--color-purple',
  shadow: '--color-shadow',
};

export const PALETTES: Palette[] = [
  {
    id: 'darcula',
    name: 'Darcula',
    description: 'JetBrains Darcula greys — paired with the blood-red from the qBittorrent logo.',
    source: 'https://colorshexa.com/palette/darcula-palette',
    dark: {
      bgPrimary:     '#2b2b2b',
      bgSecondary:   '#3c3f41',
      bgTertiary:    '#4e5254',
      border:        '#555555',
      textPrimary:   '#a9b7c6',
      textSecondary: '#808080',
      accent:        '#9d001e',   // logo blood-red
      accentHover:   '#c4002a',
      contrast:      '#d9a441',   // warm gold for secondary accent / badges
      success:       '#6a8759',
      danger:        '#cc7832',
      warning:       '#d9a441',
      info:          '#6897bb',
      purple:        '#9876aa',
      shadow:        'rgba(0,0,0,0.55)',
    },
    light: {
      bgPrimary:     '#ffffff',
      bgSecondary:   '#f2f2f2',
      bgTertiary:    '#e4e4e4',
      border:        '#c9c9c9',
      textPrimary:   '#1c1c1c',
      textSecondary: '#555555',
      accent:        '#9d001e',
      accentHover:   '#7d0017',
      contrast:      '#b07d1f',
      success:       '#0a7b28',
      danger:        '#c9302c',
      warning:       '#b07d1f',
      info:          '#1e6fa8',
      purple:        '#6f42c1',
      shadow:        'rgba(0,0,0,0.12)',
    },
  },
  {
    id: 'dracula',
    name: 'Dracula',
    description: 'Popular Dracula community palette.',
    source: 'https://draculatheme.com/contribute',
    dark: {
      bgPrimary:     '#282a36',
      bgSecondary:   '#343746',
      bgTertiary:    '#44475a',
      border:        '#6272a4',
      textPrimary:   '#f8f8f2',
      textSecondary: '#bfbfbf',
      accent:        '#ff79c6',
      accentHover:   '#ff92d0',
      contrast:      '#bd93f9',
      success:       '#50fa7b',
      danger:        '#ff5555',
      warning:       '#f1fa8c',
      info:          '#8be9fd',
      purple:        '#bd93f9',
      shadow:        'rgba(0,0,0,0.55)',
    },
    light: {
      bgPrimary:     '#f8f8f2',
      bgSecondary:   '#eeeeec',
      bgTertiary:    '#e0e0da',
      border:        '#c9c9c0',
      textPrimary:   '#282a36',
      textSecondary: '#6272a4',
      accent:        '#d6336c',
      accentHover:   '#bd255a',
      contrast:      '#7048e8',
      success:       '#2b8a3e',
      danger:        '#c92a2a',
      warning:       '#b08900',
      info:          '#1c7ed6',
      purple:        '#6741d9',
      shadow:        'rgba(0,0,0,0.12)',
    },
  },
  {
    id: 'solarized',
    name: 'Solarized',
    description: "Ethan Schoonover's Solarized — precision colours for machines and people.",
    source: 'https://colorshexa.com/palette/solarized-palette',
    dark: {
      bgPrimary:     '#002b36',
      bgSecondary:   '#073642',
      bgTertiary:    '#0a4453',
      border:        '#586e75',
      textPrimary:   '#93a1a1',
      textSecondary: '#657b83',
      accent:        '#268bd2',
      accentHover:   '#2aa198',
      contrast:      '#b58900',
      success:       '#859900',
      danger:        '#dc322f',
      warning:       '#b58900',
      info:          '#268bd2',
      purple:        '#6c71c4',
      shadow:        'rgba(0,0,0,0.55)',
    },
    light: {
      bgPrimary:     '#fdf6e3',
      bgSecondary:   '#eee8d5',
      bgTertiary:    '#d9d2bf',
      border:        '#93a1a1',
      textPrimary:   '#073642',
      textSecondary: '#657b83',
      accent:        '#268bd2',
      accentHover:   '#1d70ad',
      contrast:      '#b58900',
      success:       '#859900',
      danger:        '#dc322f',
      warning:       '#b58900',
      info:          '#268bd2',
      purple:        '#6c71c4',
      shadow:        'rgba(0,0,0,0.12)',
    },
  },
  {
    id: 'nord',
    name: 'Nord',
    description: 'Arctic, north-bluish clean and elegant colour palette.',
    source: 'https://colorshexa.com/palette/nord-palette',
    dark: {
      bgPrimary:     '#2e3440',
      bgSecondary:   '#3b4252',
      bgTertiary:    '#434c5e',
      border:        '#4c566a',
      textPrimary:   '#eceff4',
      textSecondary: '#d8dee9',
      accent:        '#88c0d0',
      accentHover:   '#8fbcbb',
      contrast:      '#ebcb8b',
      success:       '#a3be8c',
      danger:        '#bf616a',
      warning:       '#ebcb8b',
      info:          '#81a1c1',
      purple:        '#b48ead',
      shadow:        'rgba(0,0,0,0.55)',
    },
    light: {
      bgPrimary:     '#eceff4',
      bgSecondary:   '#e5e9f0',
      bgTertiary:    '#d8dee9',
      border:        '#b8c0ce',
      textPrimary:   '#2e3440',
      textSecondary: '#4c566a',
      accent:        '#5e81ac',
      accentHover:   '#4c6e95',
      contrast:      '#d08770',
      success:       '#5b8c3a',
      danger:        '#bf616a',
      warning:       '#b08900',
      info:          '#81a1c1',
      purple:        '#b48ead',
      shadow:        'rgba(0,0,0,0.12)',
    },
  },
  {
    id: 'monokai',
    name: 'Monokai',
    description: "Wimer Hazenberg's Monokai — the iconic Sublime Text palette.",
    source: 'https://colorshexa.com/palette/monokai-palette',
    dark: {
      bgPrimary:     '#272822',
      bgSecondary:   '#383830',
      bgTertiary:    '#49483e',
      border:        '#75715e',
      textPrimary:   '#f8f8f2',
      textSecondary: '#cfcfc2',
      accent:        '#f92672',
      accentHover:   '#ff4890',
      contrast:      '#a6e22e',
      success:       '#a6e22e',
      danger:        '#f92672',
      warning:       '#fd971f',
      info:          '#66d9ef',
      purple:        '#ae81ff',
      shadow:        'rgba(0,0,0,0.55)',
    },
    light: {
      bgPrimary:     '#fafaf5',
      bgSecondary:   '#ededeb',
      bgTertiary:    '#dddbcf',
      border:        '#b0ad9e',
      textPrimary:   '#272822',
      textSecondary: '#75715e',
      accent:        '#d63384',
      accentHover:   '#b5256e',
      contrast:      '#689822',
      success:       '#689822',
      danger:        '#c02450',
      warning:       '#c6660a',
      info:          '#2a9ab4',
      purple:        '#7a4ddb',
      shadow:        'rgba(0,0,0,0.12)',
    },
  },
  {
    id: 'gruvbox',
    name: 'Gruvbox',
    description: 'Retro groove colour scheme — warm, earthy, high-contrast.',
    source: 'https://colorshexa.com/palette/gruvbox-palette',
    dark: {
      bgPrimary:     '#282828',
      bgSecondary:   '#3c3836',
      bgTertiary:    '#504945',
      border:        '#665c54',
      textPrimary:   '#ebdbb2',
      textSecondary: '#a89984',
      accent:        '#fb4934',
      accentHover:   '#cc241d',
      contrast:      '#fabd2f',
      success:       '#b8bb26',
      danger:        '#fb4934',
      warning:       '#fabd2f',
      info:          '#83a598',
      purple:        '#d3869b',
      shadow:        'rgba(0,0,0,0.55)',
    },
    light: {
      bgPrimary:     '#fbf1c7',
      bgSecondary:   '#ebdbb2',
      bgTertiary:    '#d5c4a1',
      border:        '#bdae93',
      textPrimary:   '#3c3836',
      textSecondary: '#665c54',
      accent:        '#9d0006',
      accentHover:   '#79111e',
      contrast:      '#b57614',
      success:       '#79740e',
      danger:        '#9d0006',
      warning:       '#b57614',
      info:          '#076678',
      purple:        '#8f3f71',
      shadow:        'rgba(0,0,0,0.12)',
    },
  },
  {
    id: 'one-dark',
    name: 'One Dark',
    description: 'Atom One Dark — balanced, signature editor palette.',
    source: 'https://colorshexa.com/palette/one-dark-palette',
    dark: {
      bgPrimary:     '#282c34',
      bgSecondary:   '#353b45',
      bgTertiary:    '#3e4451',
      border:        '#4b5263',
      textPrimary:   '#abb2bf',
      textSecondary: '#7f848e',
      accent:        '#61afef',
      accentHover:   '#4e96d6',
      contrast:      '#e5c07b',
      success:       '#98c379',
      danger:        '#e06c75',
      warning:       '#e5c07b',
      info:          '#56b6c2',
      purple:        '#c678dd',
      shadow:        'rgba(0,0,0,0.55)',
    },
    light: {
      bgPrimary:     '#fafafa',
      bgSecondary:   '#eaeaeb',
      bgTertiary:    '#d3d3d5',
      border:        '#a0a1a7',
      textPrimary:   '#383a42',
      textSecondary: '#696c77',
      accent:        '#4078f2',
      accentHover:   '#2e62cc',
      contrast:      '#986801',
      success:       '#50a14f',
      danger:        '#e45649',
      warning:       '#c18401',
      info:          '#0184bc',
      purple:        '#a626a4',
      shadow:        'rgba(0,0,0,0.12)',
    },
  },
  {
    id: 'tokyo-night',
    name: 'Tokyo Night',
    description: "Clean, dark urban palette inspired by Tokyo's lights.",
    source: 'https://colorshexa.com/palette/tokyo-night-palette',
    dark: {
      bgPrimary:     '#1a1b26',
      bgSecondary:   '#24283b',
      bgTertiary:    '#2f344d',
      border:        '#414868',
      textPrimary:   '#c0caf5',
      textSecondary: '#a9b1d6',
      accent:        '#7aa2f7',
      accentHover:   '#6a91e6',
      contrast:      '#e0af68',
      success:       '#9ece6a',
      danger:        '#f7768e',
      warning:       '#e0af68',
      info:          '#7dcfff',
      purple:        '#bb9af7',
      shadow:        'rgba(0,0,0,0.55)',
    },
    light: {
      bgPrimary:     '#e6e7ed',
      bgSecondary:   '#d5d6db',
      bgTertiary:    '#c4c7d0',
      border:        '#989caf',
      textPrimary:   '#343b58',
      textSecondary: '#565a6e',
      accent:        '#34548a',
      accentHover:   '#2a4471',
      contrast:      '#8f5e15',
      success:       '#485e30',
      danger:        '#8c4351',
      warning:       '#8f5e15',
      info:          '#2a6194',
      purple:        '#5a3e8e',
      shadow:        'rgba(0,0,0,0.12)',
    },
  },
];

export const DEFAULT_PALETTE_ID = 'darcula';

/** Lookup by id, returning `undefined` if not found. */
export function findPalette(id: string): Palette | undefined {
  return PALETTES.find((p) => p.id === id);
}

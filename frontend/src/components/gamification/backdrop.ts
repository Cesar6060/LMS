/**
 * Per-backdrop UI palettes for the dashboard hero (Phase 34): every container
 * and button in the hero restyles itself from the equipped scene so the whole
 * hero reads as one composition. Calm scenes (plain/none/grid) use theme
 * tokens with no container chrome (per the 1a design); busy scenes get
 * scene-tinted glass surfaces with matching accents.
 */
export interface SceneTheme {
  /** Scene ends in a dark scrim → loose text goes light. */
  dark: boolean;
  /** Gradient display numerals (Lv / streak count) in the hero corners. */
  numeral: string;
  /** Accent text (View all link, etc.). */
  accent: string;
  /** Secondary text (XP subtext, trophy label, mascot name). */
  label: string;
  /** XP track override ('' keeps `progress-gaming`'s default). */
  track: string;
  /** Speech bubble + thought-dot surface. */
  bubble: string;
  /** Customize button override. */
  button: string;
}

const GOLD_NUMERAL =
  'bg-gradient-to-b from-amber-200 via-yellow-400 to-amber-600 bg-clip-text text-transparent drop-shadow-[0_1px_2px_rgba(0,0,0,0.45)]';

const DEFAULT_THEME: SceneTheme = {
  dark: false,
  numeral: 'text-gradient-gaming',
  accent: 'text-primary',
  label: 'text-muted-foreground',
  track: '',
  bubble:
    'border-primary/30 bg-gradient-to-br from-white to-emerald-50 text-zinc-900 shadow-[0_4px_20px_rgba(34,197,94,0.18)]',
  button: 'bg-background/75 backdrop-blur-sm',
};

const SCENE_THEMES: Record<string, SceneTheme> = {
  plain: DEFAULT_THEME,
  none: DEFAULT_THEME,
  grid: DEFAULT_THEME,
  stars: {
    dark: true,
    numeral: GOLD_NUMERAL,
    accent: 'text-amber-300',
    label: 'text-slate-300',
    track: 'bg-white/15',
    bubble:
      'border-sky-300/40 bg-gradient-to-br from-white to-sky-100 text-zinc-900 shadow-[0_4px_20px_rgba(125,211,252,0.25)]',
    button:
      'border-sky-300/30 bg-slate-900/65 text-slate-100 backdrop-blur-md hover:bg-slate-900/85 hover:text-slate-100',
  },
  sunset: {
    dark: true,
    numeral: GOLD_NUMERAL,
    accent: 'text-amber-300',
    label: 'text-rose-100/90',
    track: 'bg-white/20',
    bubble:
      'border-amber-300/60 bg-gradient-to-br from-white to-amber-100 text-zinc-900 shadow-[0_4px_20px_rgba(251,191,36,0.3)]',
    button:
      'border-amber-300/40 bg-rose-950/65 text-amber-50 backdrop-blur-md hover:bg-rose-950/85 hover:text-amber-50',
  },
  galaxy: {
    dark: true,
    numeral:
      'bg-gradient-to-b from-violet-200 via-violet-400 to-indigo-400 bg-clip-text text-transparent drop-shadow-[0_1px_2px_rgba(0,0,0,0.45)]',
    accent: 'text-violet-300',
    label: 'text-indigo-200',
    track: 'bg-white/15',
    bubble:
      'border-violet-400/50 bg-gradient-to-br from-white to-violet-100 text-zinc-900 shadow-[0_4px_20px_rgba(167,139,250,0.3)]',
    button:
      'border-violet-400/40 bg-indigo-950/65 text-indigo-50 backdrop-blur-md hover:bg-indigo-950/85 hover:text-indigo-50',
  },
};

export function getSceneTheme(key: string | null | undefined): SceneTheme {
  return SCENE_THEMES[key ?? 'plain'] ?? DEFAULT_THEME;
}

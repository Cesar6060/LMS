import { render } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { Mascot } from './Mascot';
import { Held } from './mascot/Held';
import { getSceneTheme } from './backdrop';
import type { AvatarEquipped, AvatarSlot } from '@/types';

vi.mock('@/contexts/AvatarContext', () => ({
  useAvatarContext: () => ({ avatar: null, refresh: vi.fn(), update: vi.fn() }),
}));

/**
 * The catalog keys, mirrored from `backend/gamification/avatar_catalog.py`.
 * Kept as a literal rather than fetched: these tests guard that every key the
 * backend can send has art, so a copy that drifts is exactly the failure we
 * want surfaced when someone adds a catalog entry and forgets the SVG.
 */
const CATALOG_KEYS: Record<AvatarSlot, string[]> = {
  color: ['classic', 'ember', 'ocean', 'mint', 'bubblegum', 'gold', 'violet', 'crimson', 'chrome', 'aurora'],
  headgear: ['none', 'cap', 'headphones', 'beanie', 'wizard_hat', 'crown', 'halo', 'hard_hat', 'space_helmet', 'laurel', 'flame_crest'],
  eyes: ['none', 'visor', 'sleepy', 'glasses', 'starry', 'shades', 'heart', 'scanner', 'laser', 'focus'],
  accessory: ['none', 'bowtie', 'scarf', 'medal', 'backpack', 'cape', 'jetpack', 'sash', 'wings', 'marksman_pin'],
  backdrop: ['plain', 'none', 'grid', 'stars', 'sunset', 'forest', 'galaxy', 'arcade', 'aurora_sky'],
  companion: ['none', 'drone', 'chip', 'robo_cat', 'owl', 'dragon', 'phoenix'],
  aura: ['none', 'sparkle', 'pulse', 'electric', 'rainbow', 'flame_ring', 'golden'],
  held: ['none', 'wrench', 'controller', 'codex', 'debug_blade', 'torch', 'trophy'],
};

const DEFAULTS: AvatarEquipped = {
  color: 'classic', headgear: 'none', eyes: 'none', accessory: 'none',
  backdrop: 'plain', companion: 'none', aura: 'none', held: 'none',
};

const POSES = ['idle', 'cheer', 'encourage', 'celebrate'] as const;

describe('Mascot cosmetic layers', () => {
  const slots = Object.keys(CATALOG_KEYS) as AvatarSlot[];

  it.each(slots)('renders every %s key without throwing', (slot) => {
    for (const key of CATALOG_KEYS[slot]) {
      for (const pose of POSES) {
        expect(() =>
          render(<Mascot pose={pose} customization={{ ...DEFAULTS, [slot]: key }} />)
        ).not.toThrow();
      }
    }
  });

  it.each(slots)('draws something different for every non-default %s key', (slot) => {
    // "Doesn't throw" is too weak on its own: every layer module returns null
    // for an unknown key, so a catalog entry with no SVG branch would render
    // an invisible cosmetic and still pass. Comparing against the default
    // render is what actually catches missing art.
    const base = render(
      <Mascot customization={DEFAULTS} />
    ).container.innerHTML;

    for (const key of CATALOG_KEYS[slot]) {
      if (key === DEFAULTS[slot]) continue;
      const html = render(
        <Mascot customization={{ ...DEFAULTS, [slot]: key }} />
      ).container.innerHTML;
      // useId makes ids differ per instance, so normalize them away before
      // comparing — otherwise every render looks "different" and the test
      // passes vacuously, which is the exact failure mode being fixed.
      const norm = (s: string) => s.replace(/:r[0-9a-z]+:/g, 'ID').replace(/«r\w+»/g, 'ID');
      expect(norm(html), `${slot}/${key} renders identically to the default`)
        .not.toEqual(norm(base));
    }
  });

  it('renders an unknown key as the plain robot rather than crashing', () => {
    const { container } = render(
      <Mascot customization={{ ...DEFAULTS, headgear: 'not_a_real_hat' }} />
    );
    expect(container.querySelector('svg')).not.toBeNull();
  });

  it('gives each instance distinct gradient ids', () => {
    // The customizer grid mounts dozens of mascots at once; a shared id makes
    // one instance's gradient bleed into another's fill.
    const { container } = render(
      <>
        <Mascot customization={{ ...DEFAULTS, backdrop: 'sunset' }} />
        <Mascot customization={{ ...DEFAULTS, backdrop: 'sunset' }} />
      </>
    );
    const ids = Array.from(container.querySelectorAll('linearGradient')).map(
      (node) => node.getAttribute('id')
    );
    expect(ids).toHaveLength(2);
    expect(ids[0]).not.toBeNull();
    expect(ids[0]).not.toEqual(ids[1]);
  });
});

describe('Held item hand tracking', () => {
  const props = {
    itemKey: 'torch',
    primary: '#22c55e',
    surface: '#eee',
    outline: '#111',
    gold: '#facc15',
    gradientId: 'test',
  };

  function translateOf(container: HTMLElement): string | null {
    const g = container.querySelector('g[transform]');
    return g?.getAttribute('transform') ?? null;
  }

  it('anchors to the raised hand on celebrate, not the idle hand', () => {
    // Mascot's right arm ends at (98, 94) idle and (102, 62) on celebrate.
    const { container: idle } = render(
      <svg><Held {...props} pose="idle" hand={{ x: 98, y: 94 }} /></svg>
    );
    const { container: celebrating } = render(
      <svg><Held {...props} pose="celebrate" hand={{ x: 102, y: 62 }} /></svg>
    );

    expect(translateOf(idle)).toContain('98');
    expect(translateOf(idle)).toContain('94');
    expect(translateOf(celebrating)).toContain('102');
    expect(translateOf(celebrating)).toContain('62');
    expect(translateOf(idle)).not.toEqual(translateOf(celebrating));
  });

  it('renders nothing for the empty-hands key', () => {
    const { container } = render(
      <svg><Held {...props} itemKey="none" pose="idle" hand={{ x: 98, y: 94 }} /></svg>
    );
    expect(container.querySelector('g')).toBeNull();
  });
});

describe('backdrop scene themes', () => {
  it('has a fully populated theme for every backdrop key', () => {
    // A dark scene that falls through to DEFAULT_THEME puts theme-token text
    // on a near-black background — unreadable, and silent.
    for (const key of CATALOG_KEYS.backdrop) {
      const theme = getSceneTheme(key);
      expect(theme, key).toBeDefined();
      for (const field of ['numeral', 'accent', 'label', 'bubble', 'button'] as const) {
        expect(theme[field], `${key}.${field}`).toBeTruthy();
      }
      // `track` is the one field where '' is meaningful — it means "keep
      // progress-gaming's own styling". That's fine on a light scene, but a
      // dark one needs an explicit override or the XP bar vanishes into it.
      expect(typeof theme.track, `${key}.track`).toBe('string');
      if (theme.dark) {
        expect(theme.track, `dark scene ${key} must override the XP track`).toBeTruthy();
      }
    }
  });

  it('marks the new phase-64 scenes as dark', () => {
    for (const key of ['forest', 'arcade', 'aurora_sky']) {
      expect(getSceneTheme(key).dark, key).toBe(true);
    }
  });

  it('does not silently reuse the default theme for a real scene', () => {
    const fallback = getSceneTheme('definitely-not-a-scene');
    for (const key of ['forest', 'arcade', 'aurora_sky', 'stars', 'galaxy', 'sunset']) {
      expect(getSceneTheme(key), key).not.toEqual(fallback);
    }
  });
});

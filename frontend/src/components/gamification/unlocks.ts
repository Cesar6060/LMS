import type { AvatarItem } from '@/types';

/**
 * Which cosmetics a celebration just made available (Phase 64).
 *
 * Both read the STATIC catalog rather than the `unlocked` flags, so they are
 * correct even before AvatarContext refreshes — which is the normal case,
 * since a celebration fires the moment the award lands.
 *
 * Separate from `UnlockedItems.tsx` so that file only exports a component
 * (react-refresh/only-export-components).
 */

/** Items a given level unlocks. */
export function itemsUnlockedAtLevel(catalog: AvatarItem[], level: number): AvatarItem[] {
  return catalog.filter(
    (item) => item.unlock_type === 'level' && item.required_level === level
  );
}

/** Items a given badge unlocks. Empty for most badges — that's expected. */
export function itemsUnlockedByBadge(catalog: AvatarItem[], badgeKey: string): AvatarItem[] {
  return catalog.filter(
    (item) => item.unlock_type === 'badge' && item.required_badge === badgeKey
  );
}

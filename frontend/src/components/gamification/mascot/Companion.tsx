import { starPath } from '@/components/gamification/starPath';
import type { LayerProps } from './types';

/**
 * Companion layer (Phase 64). Drawn LAST, in front of every other layer.
 *
 * Circuit's body rect is x 38–82 / y 70–102 and the right arm swings out to
 * x≈98–102 on cheer/celebrate, so every companion is boxed into the lower-right
 * corner — roughly x 84–116, y 74–110 — and nothing crosses x < 84. Creatures
 * are ~22–30 units tall and carry no detail finer than ~1.5 units, because the
 * course map renders Circuit at size={72}.
 */
export function Companion({ itemKey, primary, surface, outline, gold, pose, gradientId }: LayerProps) {
  // The companion perks up alongside Circuit; only one element per creature
  // animates, and only in the excited poses.
  const excited = pose === 'cheer' || pose === 'celebrate';
  const perk = excited ? 'animate-pulse motion-reduce:animate-none' : undefined;

  if (itemKey === 'drone') {
    return (
      <>
        {/* Rotor bar and discs, sized so the whole rig reads as hovering */}
        <line x1="90" y1="84" x2="110" y2="84" stroke={outline} strokeWidth="2" strokeLinecap="round" />
        <g className={perk}>
          <ellipse cx="90" cy="84" rx="5.5" ry="2.5" fill={primary} opacity="0.75" />
          <ellipse cx="110" cy="84" rx="5.5" ry="2.5" fill={primary} opacity="0.75" />
        </g>
        <line x1="100" y1="84" x2="100" y2="88" stroke={outline} strokeWidth="2" />
        {/* Chassis */}
        <rect x="93" y="86" width="14" height="15" rx="7" fill={surface} stroke={primary} strokeWidth="2.5" />
        {/* Single camera eye */}
        <circle cx="100" cy="93" r="4" fill={outline} opacity="0.85" />
        <circle cx="100" cy="93" r="1.8" fill={primary} />
        {/* Landing skid */}
        <line x1="96" y1="101" x2="96" y2="104" stroke={outline} strokeWidth="2" />
        <line x1="104" y1="101" x2="104" y2="104" stroke={outline} strokeWidth="2" />
        <line x1="93" y1="104" x2="107" y2="104" stroke={outline} strokeWidth="2" strokeLinecap="round" />
      </>
    );
  }

  if (itemKey === 'chip') {
    return (
      <>
        {/* Pin rows first, so the package body caps them */}
        <g stroke={outline} strokeWidth="2" strokeLinecap="round">
          <line x1="86" y1="87" x2="90" y2="87" />
          <line x1="86" y1="92" x2="90" y2="92" />
          <line x1="86" y1="97" x2="90" y2="97" />
          <line x1="110" y1="87" x2="114" y2="87" />
          <line x1="110" y1="92" x2="114" y2="92" />
          <line x1="110" y1="97" x2="114" y2="97" />
        </g>
        <rect x="90" y="82" width="20" height="20" rx="3" fill={surface} stroke={primary} strokeWidth="2.5" />
        {/* Die window behind the face */}
        <rect x="94" y="86" width="12" height="12" rx="2" fill={primary} opacity="0.18" />
        <circle cx="96" cy="90" r="2" fill={outline} />
        <circle cx="104" cy="90" r="2" fill={outline} />
        <path d="M95 95 q5 5 10 0" fill="none" stroke={outline} strokeWidth="2" strokeLinecap="round" />
        <path d={starPath(112, 78, 3)} fill={gold} className={perk} />
      </>
    );
  }

  if (itemKey === 'robo_cat') {
    return (
      <>
        {/* Antenna tail with an LED tip */}
        <path d="M107 104 Q114 101 112 93" fill="none" stroke={outline} strokeWidth="2.5" strokeLinecap="round" />
        <circle cx="112" cy="92" r="2" fill="#22d3ee" className={perk} />
        {/* Sitting haunches */}
        <path d="M93 106 Q91 93 100 93 Q109 93 107 106 Z" fill="#94a3b8" stroke={outline} strokeWidth="2" />
        {/* Collar tag */}
        <circle cx="100" cy="95" r="2" fill={gold} stroke={outline} strokeWidth="1" />
        {/* Ears, then head over them */}
        <path d="M94 82 L95 76 L99.5 80 Z" fill="#cbd5e1" stroke={outline} strokeWidth="1.5" />
        <path d="M106 82 L105 76 L100.5 80 Z" fill="#cbd5e1" stroke={outline} strokeWidth="1.5" />
        <circle cx="100" cy="86" r="7.5" fill="#cbd5e1" stroke={outline} strokeWidth="2" />
        <circle cx="97" cy="86" r="1.8" fill="#22d3ee" />
        <circle cx="103" cy="86" r="1.8" fill="#22d3ee" />
        <line x1="97.5" y1="90" x2="102.5" y2="90" stroke={outline} strokeWidth="1.5" strokeLinecap="round" />
      </>
    );
  }

  if (itemKey === 'owl') {
    return (
      <>
        {/* Ear tufts under the body silhouette */}
        <path d="M92 84 L91 77 L97 82 Z" fill="#92400e" stroke={outline} strokeWidth="1.5" />
        <path d="M108 84 L109 77 L103 82 Z" fill="#92400e" stroke={outline} strokeWidth="1.5" />
        <ellipse cx="100" cy="93" rx="10" ry="12" fill="#92400e" stroke={outline} strokeWidth="2" />
        {/* Folded wings hugging the body */}
        <path d="M90 88 Q86 98 92 104 Q94 96 93 88 Z" fill="#78350f" />
        <path d="M110 88 Q114 98 108 104 Q106 96 107 88 Z" fill="#78350f" />
        <ellipse cx="100" cy="96" rx="6.5" ry="8" fill="#fcd34d" opacity="0.9" />
        <circle cx="95.5" cy="86" r="4.2" fill="#fef3c7" stroke={outline} strokeWidth="1.5" />
        <circle cx="104.5" cy="86" r="4.2" fill="#fef3c7" stroke={outline} strokeWidth="1.5" />
        <circle cx="95.5" cy="86" r="2" fill={outline} className={perk} />
        <circle cx="104.5" cy="86" r="2" fill={outline} />
        <path d="M100 89 L97 92.5 L103 92.5 Z" fill={gold} stroke={outline} strokeWidth="1" />
        {/* Talons */}
        <line x1="96" y1="104" x2="96" y2="107" stroke={gold} strokeWidth="2" strokeLinecap="round" />
        <line x1="104" y1="104" x2="104" y2="107" stroke={gold} strokeWidth="2" strokeLinecap="round" />
      </>
    );
  }

  if (itemKey === 'dragon') {
    return (
      <>
        {/* Far wing and tail behind the body */}
        <path d="M100 90 Q106 76 115 79 Q109 87 107 95 Z" fill="#15803d" stroke={outline} strokeWidth="1.5" />
        <path d="M106 100 Q116 103 112 92" fill="none" stroke="#22c55e" strokeWidth="3.5" strokeLinecap="round" />
        {/* Dorsal spikes */}
        <path d="M96 89 l2.5 -4.5 l2.5 4.5 z" fill="#15803d" />
        <path d="M102 89 l2.5 -4.5 l2.5 4.5 z" fill="#15803d" />
        <ellipse cx="95" cy="103" rx="3" ry="2" fill="#15803d" />
        <ellipse cx="104" cy="103" rx="3" ry="2" fill="#15803d" />
        <ellipse cx="100" cy="96" rx="9" ry="8" fill="#22c55e" stroke={outline} strokeWidth="2" />
        <ellipse cx="100" cy="99" rx="5.5" ry="4.5" fill="#bbf7d0" opacity="0.85" />
        {/* Head turned back toward Circuit */}
        <path d="M94 81 L96 75 L97.5 81 Z" fill={gold} stroke={outline} strokeWidth="1" />
        <ellipse cx="92" cy="86" rx="6.5" ry="5.5" fill="#22c55e" stroke={outline} strokeWidth="2" />
        <circle cx="89.5" cy="85" r="1.7" fill={outline} />
        <path d={starPath(111, 76, 2.8)} fill={gold} className={perk} />
      </>
    );
  }

  if (itemKey === 'phoenix') {
    return (
      <>
        <defs>
          <linearGradient id={`${gradientId}-companion-phoenix`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#fde68a" />
            <stop offset="55%" stopColor="#fb923c" />
            <stop offset="100%" stopColor="#dc2626" />
          </linearGradient>
        </defs>
        {/* Flame tail sweeping down-right, hottest at the core */}
        <path d="M100 96 Q112 96 111 86 Q117 96 112 105 Q106 109 98 104 Z" fill="#f97316" opacity="0.9" />
        <path
          d="M102 98 Q110 98 109 91 Q113 98 110 104 Q105 107 100 103 Z"
          fill="#fde047"
          opacity="0.9"
          className={perk}
        />
        {/* Raised wing */}
        <path d="M97 88 Q104 76 114 78 Q106 84 104 92 Z" fill="#fb923c" stroke={outline} strokeWidth="1.5" />
        <ellipse cx="97" cy="93" rx="8" ry="9" fill={`url(#${gradientId}-companion-phoenix)`} stroke={outline} strokeWidth="2" />
        {/* Crest, then head over it */}
        <path d="M90 79 Q89 74 95 75 Q91 77 93 80 Z" fill="#f97316" stroke={outline} strokeWidth="1" />
        <circle cx="92" cy="84" r="5" fill="#fbbf24" stroke={outline} strokeWidth="2" />
        <path d="M88 84 L84.5 85.5 L88 87 Z" fill={gold} stroke={outline} strokeWidth="1" />
        <circle cx="91" cy="83" r="1.6" fill={outline} />
        <path d={starPath(110, 74, 3)} fill={gold} />
      </>
    );
  }

  // 'none' and any unknown key: Circuit goes solo.
  return null;
}

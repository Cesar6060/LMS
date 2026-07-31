import { useId } from 'react';
import { cn } from '@/lib/utils';
import { useAvatarContext } from '@/contexts/AvatarContext';
import { Backdrop } from '@/components/gamification/mascot/Backdrops';
import { BehindBodyAccessory, ChestAccessory } from '@/components/gamification/mascot/Accessories';
import { Aura } from '@/components/gamification/mascot/Aura';
import { Companion } from '@/components/gamification/mascot/Companion';
import { Eyes } from '@/components/gamification/mascot/Eyes';
import { Headgear } from '@/components/gamification/mascot/Headgear';
import { Held } from '@/components/gamification/mascot/Held';
import { colorFor, GOLD } from '@/components/gamification/mascot/colors';
import type { HandPoint, MascotPose } from '@/components/gamification/mascot/types';
import type { AvatarEquipped } from '@/types';

export type { MascotPose };

interface MascotProps {
  pose?: MascotPose;
  /** Rendered width/height in px. */
  size?: number;
  className?: string;
  /**
   * Explicit cosmetic overrides (Phase 33). Defaults to the logged-in
   * student's equipped items from AvatarContext, so existing call sites
   * pick up the custom look automatically. Pass values (e.g. a pending
   * selection) to preview a different look.
   */
  customization?: Partial<AvatarEquipped> | null;
  /**
   * Skip the backdrop panel layer (Phase 34): the dashboard hero renders the
   * equipped backdrop at container scale, so the SVG's own panel would
   * double-render the scene.
   */
  hideBackdrop?: boolean;
}

/**
 * "Circuit" — the STEM Quest robot mascot. A single inline SVG with a few
 * poses, used in the quiz mastery flow's feedback moments, the course map and
 * the dashboard avatar card. Theme-aware via CSS variables; CSS-only animation.
 *
 * This component owns the base body, the pose math, the palette and the
 * composition ORDER. Each cosmetic slot lives in its own module under
 * `mascot/` (Phase 64) — with eight slots and 70-odd items, keeping every
 * layer here made the file unworkable. Unknown keys fall back to drawing
 * nothing, so a catalog entry with no art degrades instead of crashing.
 *
 * Draw order is load-bearing: backdrop → behind-body accessory → aura →
 * antenna → head → eyes → eye cosmetics → mouth → headgear → arms → body →
 * chest accessory → held → feet → companion.
 */
export function Mascot({ pose = 'idle', size = 96, className, customization, hideBackdrop = false }: MascotProps) {
  const { avatar } = useAvatarContext();
  const equipped = customization ?? avatar?.equipped ?? null;

  const primary = colorFor(equipped?.color);
  const surface = 'hsl(var(--muted))';
  const outline = 'hsl(var(--foreground))';

  const headgear = equipped?.headgear ?? 'none';
  const eyes = equipped?.eyes ?? 'none';
  const accessory = equipped?.accessory ?? 'none';
  const backdrop = hideBackdrop ? 'none' : equipped?.backdrop ?? 'plain';
  const companion = equipped?.companion ?? 'none';
  const aura = equipped?.aura ?? 'none';
  const held = equipped?.held ?? 'none';
  const name = avatar?.mascot_name ?? 'Circuit';
  // Gradient ids must be unique per mascot instance — the customizer grid
  // renders many at once. Every layer namespaces its ids with this.
  const gradientId = useId();

  const armsUp = pose === 'celebrate';
  const oneArmUp = pose === 'cheer';
  const happyEyes = pose === 'cheer' || pose === 'celebrate';

  // Arm endpoints. These same values feed both the arm <line>s below and the
  // held item's anchor, so a held item can never drift away from the hand.
  const leftHand: HandPoint = {
    x: armsUp || oneArmUp ? 18 : 22,
    y: armsUp || oneArmUp ? 62 : 94,
  };
  const rightHand: HandPoint = {
    x: armsUp ? 102 : 98,
    y: armsUp ? 62 : 94,
  };

  const layer = { primary, surface, outline, gold: GOLD, pose, gradientId };

  return (
    <div
      className={cn(
        'inline-block select-none',
        (pose === 'cheer' || pose === 'celebrate') && 'animate-bounce motion-reduce:animate-none',
        className
      )}
      style={{ width: size, height: size }}
      role="img"
      aria-label={`${name} the robot (${pose})`}
    >
      {/*
        The body is authored in a 0..120 box, but satellite layers (aura rings,
        the companion) need somewhere to go that isn't on top of it. Extending
        the viewBox to -20..140 reserves a 20-unit margin on every side without
        moving a single body coordinate — the robot simply renders ~14% smaller
        with room around it. Layers may draw out to r=80 from the (60,60) centre.
      */}
      <svg viewBox="-20 -20 160 160" width={size} height={size}>
        {/* Backdrop container (drawn first, behind everything) */}
        <Backdrop {...layer} itemKey={backdrop} />

        {/* Behind-the-body accessories */}
        <BehindBodyAccessory {...layer} itemKey={accessory} />

        {/* Aura — behind Circuit, in front of the backdrop */}
        <Aura {...layer} itemKey={aura} />

        {/* Antenna */}
        <line x1="60" y1="22" x2="60" y2="10" stroke={outline} strokeWidth="3" strokeLinecap="round" />
        <circle
          cx="60"
          cy="8"
          r="4.5"
          fill={primary}
          className={pose === 'celebrate' ? 'animate-pulse motion-reduce:animate-none' : undefined}
        />

        {/* Head */}
        <rect x="32" y="22" width="56" height="42" rx="12" fill={surface} stroke={primary} strokeWidth="3.5" />

        {/* Eyes */}
        {happyEyes ? (
          <>
            {/* Happy closed-arc eyes */}
            <path d="M42 44 q 5 -7 10 0" fill="none" stroke={outline} strokeWidth="3.5" strokeLinecap="round" />
            <path d="M68 44 q 5 -7 10 0" fill="none" stroke={outline} strokeWidth="3.5" strokeLinecap="round" />
          </>
        ) : (
          <>
            <circle cx="47" cy="42" r="4.5" fill={outline} />
            <circle cx="73" cy="42" r="4.5" fill={outline} />
            {pose === 'encourage' && (
              /* Raised, determined brows */
              <>
                <line x1="41" y1="33" x2="52" y2="35.5" stroke={outline} strokeWidth="3" strokeLinecap="round" />
                <line x1="79" y1="33" x2="68" y2="35.5" stroke={outline} strokeWidth="3" strokeLinecap="round" />
              </>
            )}
          </>
        )}

        {/* Eye-slot cosmetics (drawn over the base eyes) */}
        <Eyes {...layer} itemKey={eyes} happyEyes={happyEyes} />

        {/* Mouth */}
        {pose === 'celebrate' ? (
          <path d="M48 52 q 12 12 24 0 z" fill={primary} opacity="0.85" />
        ) : pose === 'cheer' ? (
          <path d="M48 52 q 12 9 24 0" fill="none" stroke={outline} strokeWidth="3.5" strokeLinecap="round" />
        ) : pose === 'encourage' ? (
          <path d="M50 55 q 10 4 20 0" fill="none" stroke={outline} strokeWidth="3" strokeLinecap="round" />
        ) : (
          <line x1="51" y1="54" x2="69" y2="54" stroke={outline} strokeWidth="3.5" strokeLinecap="round" />
        )}

        {/* Headgear (drawn over the head/antenna) */}
        <Headgear {...layer} itemKey={headgear} />

        {/* Arms */}
        <line
          x1="34" y1="82"
          x2={leftHand.x}
          y2={leftHand.y}
          stroke={primary} strokeWidth="4" strokeLinecap="round"
        />
        <line
          x1="86" y1="82"
          x2={rightHand.x}
          y2={rightHand.y}
          stroke={primary} strokeWidth="4" strokeLinecap="round"
        />

        {/* Body with a circuit bolt */}
        <rect x="38" y="70" width="44" height="32" rx="9" fill={surface} stroke={primary} strokeWidth="3.5" />
        <path d="M62 75 L53 88 h6 l-2 10 9 -13 h-6 z" fill={primary} />

        {/* Neck / chest accessories (drawn over the body) */}
        <ChestAccessory {...layer} itemKey={accessory} />

        {/* Held item — anchored to the right hand, so it tracks every pose */}
        <Held {...layer} itemKey={held} hand={rightHand} />

        {/* Feet */}
        <circle cx="48" cy="108" r="5" fill={outline} opacity="0.7" />
        <circle cx="72" cy="108" r="5" fill={outline} opacity="0.7" />

        {/*
          Companion (front-most, lower right). Its art is authored against the
          old 0..120 box, where it unavoidably overlapped the jetpack's right
          thruster (x 85–96). Offsetting the whole group into the margin the
          viewBox now reserves clears that collision without touching a single
          creature's coordinates — they keep their own local frame.
        */}
        <g transform="translate(24 14)">
          <Companion {...layer} itemKey={companion} />
        </g>
      </svg>
    </div>
  );
}

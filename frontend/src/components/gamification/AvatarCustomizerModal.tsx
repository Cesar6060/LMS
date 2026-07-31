import { useEffect, useMemo, useState } from 'react';
import { isAxiosError } from 'axios';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/Dialog';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/Tabs';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Mascot } from '@/components/gamification/Mascot';
import { useAvatarContext } from '@/contexts/AvatarContext';
import { useAuth } from '@/contexts/useAuth';
import { useToast } from '@/contexts/useToast';
import { cn } from '@/lib/utils';
import { AVATAR_SLOTS } from '@/types';
import type { AvatarEquipped, AvatarItem, AvatarSlot, AvatarUpdatePatch } from '@/types';
import { Loader2, Lock, RotateCcw } from 'lucide-react';

/**
 * Eight slots is too many for a flat tab strip (Phase 64), so they're grouped
 * into three tabs and each tab lists its slots as labelled sections. Radix
 * unmounts inactive TabsContent, which matters here: every item tile renders a
 * live Mascot, and mounting all 70-odd at once would be wasteful.
 */
const TAB_GROUPS: { id: string; label: string; slots: AvatarSlot[] }[] = [
  { id: 'look', label: 'Look', slots: ['color', 'eyes'] },
  { id: 'gear', label: 'Gear', slots: ['headgear', 'accessory', 'held'] },
  { id: 'extras', label: 'Extras', slots: ['companion', 'aura', 'backdrop'] },
];

const SLOT_LABELS: Record<AvatarSlot, string> = {
  color: 'Color',
  eyes: 'Eyes',
  headgear: 'Headgear',
  accessory: 'Accessory',
  held: 'Held item',
  companion: 'Companion',
  aura: 'Aura',
  backdrop: 'Backdrop',
};

const DEFAULT_NAME = 'Circuit';

/**
 * Slots loud enough to drown out whatever an item tile is trying to show.
 * A tile previews the pending look with one item swapped in — but with an
 * aura ringing the figure and a companion beside it, every tile in the Eyes
 * section looks identical and you can't tell what you're picking. So a tile
 * mutes these three unless they ARE the slot being chosen. The big preview
 * on the left always shows the full, unmuted look.
 */
const DOMINANT_SLOTS: AvatarSlot[] = ['aura', 'companion', 'backdrop'];

/** Neutral value for each muted slot — 'none' is a valid key in all three. */
const MUTED = Object.fromEntries(
  DOMINANT_SLOTS.map((slot) => [slot, 'none'])
) as Partial<AvatarEquipped>;

function tilePreview(
  pending: AvatarEquipped,
  slot: AvatarSlot,
  key: string
): Partial<AvatarEquipped> {
  const muted = { ...MUTED };
  // Keep the slot being previewed — muting it would hide the very thing the
  // tile exists to show.
  delete muted[slot];
  return { ...pending, ...muted, [slot]: key };
}

/** Level gates sort ahead of the achievement gates in the "next unlock" hint —
 *  a level is the one a student can always make progress toward today. */
const GATE_ORDER: Record<AvatarItem['unlock_type'], number> = {
  level: 0,
  streak: 1,
  badge: 2,
};

interface AvatarCustomizerModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

/**
 * Customizer for the student's Circuit (Phase 33, regrouped Phase 64): three
 * grouped tabs over eight slots, each item tile a live preview of the pending
 * selection, locked items chipped with their own gate label. Nothing persists
 * until Save.
 */
export function AvatarCustomizerModal({ open, onOpenChange }: AvatarCustomizerModalProps) {
  const { avatar, update } = useAvatarContext();
  const { user } = useAuth();
  const toast = useToast();

  const isDemo = !!user?.is_demo;

  const [pending, setPending] = useState<AvatarEquipped | null>(null);
  const [pendingName, setPendingName] = useState(DEFAULT_NAME);
  const [isSaving, setIsSaving] = useState(false);

  // Re-seed the working copy from the saved state each time the modal opens.
  useEffect(() => {
    if (open && avatar) {
      setPending({ ...avatar.equipped });
      setPendingName(avatar.mascot_name);
    }
  }, [open, avatar]);

  const itemsBySlot = useMemo(() => {
    // Built from AVATAR_SLOTS rather than an object literal: a hard-coded map
    // silently drops every item of a slot someone forgot to add.
    const map = Object.fromEntries(
      AVATAR_SLOTS.map((slot) => [slot, [] as AvatarItem[]])
    ) as Record<AvatarSlot, AvatarItem[]>;
    for (const item of avatar?.catalog ?? []) {
      map[item.slot]?.push(item);
    }
    return map;
  }, [avatar]);

  const nextUnlock = useMemo(() => {
    const locked = (avatar?.catalog ?? []).filter((item) => !item.unlocked);
    if (locked.length === 0) return null;
    return locked.reduce((best, item) => {
      const byGate = GATE_ORDER[item.unlock_type] - GATE_ORDER[best.unlock_type];
      if (byGate !== 0) return byGate < 0 ? item : best;
      if (item.unlock_type === 'level') {
        return item.required_level < best.required_level ? item : best;
      }
      if (item.unlock_type === 'streak') {
        return (item.required_streak ?? 0) < (best.required_streak ?? 0) ? item : best;
      }
      return best;
    });
  }, [avatar]);

  const trimmedName = pendingName.trim();
  const nameError =
    trimmedName.length < 1
      ? 'Give your robot a name (1-20 characters).'
      : trimmedName.length > 20
        ? 'Names can be at most 20 characters.'
        : null;

  if (!avatar || !pending) return null;

  const nameChanged = trimmedName !== avatar.mascot_name;

  const handleSave = async () => {
    if (nameError) return;
    setIsSaving(true);
    try {
      // Only send the name when it actually changed. The shared demo account
      // is allowed to equip cosmetics but 403s on any rename, so sending an
      // unchanged name would block an otherwise-legal cosmetics-only save.
      const patch: AvatarUpdatePatch = { ...pending };
      if (nameChanged) patch.mascot_name = trimmedName;

      await update(patch);
      toast.show({ message: `${trimmedName} is looking sharp!`, icon: '🤖', variant: 'success' });
      onOpenChange(false);
    } catch (err) {
      const detail = isAxiosError(err) ? err.response?.data?.detail : undefined;
      toast.show({
        message: typeof detail === 'string' ? detail : 'Failed to save your avatar.',
        icon: '⚠️',
      });
    } finally {
      setIsSaving(false);
    }
  };

  const renderSlotSection = (slot: AvatarSlot) => (
    <section key={slot} className="mb-6 last:mb-0">
      <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
        {SLOT_LABELS[slot]}
      </h3>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        {itemsBySlot[slot].map((item) => {
          const selected = pending[slot] === item.key;
          return (
            <button
              key={`${slot}-${item.key}`}
              type="button"
              disabled={!item.unlocked}
              onClick={() =>
                setPending((prev) => (prev ? { ...prev, [slot]: item.key } : prev))
              }
              title={item.description}
              className={cn(
                'flex flex-col items-center gap-1.5 rounded-lg border p-3 text-sm font-medium transition-colors',
                selected
                  ? 'border-primary bg-primary/10'
                  : 'border-border hover:border-primary/50',
                !item.unlocked && 'opacity-50 cursor-not-allowed hover:border-border'
              )}
            >
              <Mascot
                pose="idle"
                size={75}
                customization={tilePreview(pending, slot, item.key)}
              />
              <span className="text-center leading-tight">{item.name}</span>
              {!item.unlocked && (
                <span className="inline-flex items-center gap-1 rounded-full bg-muted px-2 py-0.5 text-xs font-semibold text-muted-foreground">
                  <Lock className="h-3 w-3" />
                  {item.unlock_label}
                </span>
              )}
            </button>
          );
        })}
      </div>
    </section>
  );

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Customize your {avatar.mascot_name}</DialogTitle>
          <DialogDescription className="text-base">
            Level up by finishing lessons and quizzes to unlock more gear.
            {nextUnlock && (
              <span className="block mt-1 font-medium text-primary">
                Next unlock: {nextUnlock.unlock_label} — {nextUnlock.name}
              </span>
            )}
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col sm:flex-row gap-6">
          {/* Live preview + rename — pinned so it stays visible while the
              item lists scroll. */}
          <div className="flex flex-col items-center gap-4 sm:w-52 flex-shrink-0 sm:sticky sm:top-0 sm:self-start">
            <div className="rounded-xl border border-border bg-muted/30 p-4">
              <Mascot pose="idle" size={186} customization={pending} />
            </div>
            <div className="w-full">
              <label htmlFor="mascot-name" className="block text-sm font-medium mb-1.5">
                Robot name
              </label>
              <Input
                id="mascot-name"
                value={pendingName}
                maxLength={20}
                disabled={isDemo}
                onChange={(e) => setPendingName(e.target.value)}
                aria-invalid={nameError !== null}
              />
              {isDemo ? (
                <p className="mt-1.5 text-sm text-muted-foreground">
                  Renaming isn't available in the shared demo — everything else is.
                </p>
              ) : (
                <>
                  {nameError && (
                    <p className="text-sm text-destructive mt-1.5">{nameError}</p>
                  )}
                  <Button
                    variant="ghost"
                    size="sm"
                    className="mt-1.5 px-2 text-muted-foreground"
                    onClick={() => setPendingName(DEFAULT_NAME)}
                    disabled={pendingName === DEFAULT_NAME}
                  >
                    <RotateCcw className="h-3.5 w-3.5 mr-1.5" />
                    Reset to {DEFAULT_NAME}
                  </Button>
                </>
              )}
            </div>
          </div>

          {/* Grouped slot tabs + item grids */}
          <Tabs defaultValue={TAB_GROUPS[0].id} className="flex-1 min-w-0">
            <TabsList className="w-full">
              {TAB_GROUPS.map(({ id, label }) => (
                <TabsTrigger key={id} value={id} className="flex-1 px-2">
                  {label}
                </TabsTrigger>
              ))}
            </TabsList>
            {TAB_GROUPS.map(({ id, slots }) => (
              <TabsContent key={id} value={id}>
                {slots.map(renderSlotSection)}
              </TabsContent>
            ))}
          </Tabs>
        </div>

        <div className="flex justify-end gap-3 pt-2">
          <Button variant="outline" size="lg" onClick={() => onOpenChange(false)} disabled={isSaving}>
            Cancel
          </Button>
          <Button variant="neon" size="lg" onClick={handleSave} disabled={isSaving || nameError !== null}>
            {isSaving && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
            Save
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

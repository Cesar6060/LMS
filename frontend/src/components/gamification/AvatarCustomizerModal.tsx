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
import { useToast } from '@/contexts/ToastContext';
import { cn } from '@/lib/utils';
import type { AvatarEquipped, AvatarItem, AvatarSlot } from '@/types';
import { Loader2, Lock, RotateCcw } from 'lucide-react';

const SLOT_TABS: { slot: AvatarSlot; label: string }[] = [
  { slot: 'color', label: 'Colors' },
  { slot: 'headgear', label: 'Headgear' },
  { slot: 'eyes', label: 'Eyes' },
  { slot: 'accessory', label: 'Extras' },
  { slot: 'backdrop', label: 'Backdrop' },
];

const DEFAULT_NAME = 'Circuit';

interface AvatarCustomizerModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

/**
 * Customizer for the student's Circuit (Phase 33): slot tabs with an item
 * grid (locked items greyed with a "Lv N" chip), a live preview of the
 * pending selection, and a rename input. Nothing persists until Save.
 */
export function AvatarCustomizerModal({ open, onOpenChange }: AvatarCustomizerModalProps) {
  const { avatar, update } = useAvatarContext();
  const toast = useToast();

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
    const map: Record<AvatarSlot, AvatarItem[]> = {
      color: [], headgear: [], eyes: [], accessory: [], backdrop: [],
    };
    for (const item of avatar?.catalog ?? []) {
      map[item.slot].push(item);
    }
    return map;
  }, [avatar]);

  const nextUnlockLevel = useMemo(() => {
    const lockedLevels = (avatar?.catalog ?? [])
      .filter((item) => !item.unlocked)
      .map((item) => item.required_level);
    return lockedLevels.length > 0 ? Math.min(...lockedLevels) : null;
  }, [avatar]);

  const trimmedName = pendingName.trim();
  const nameError =
    trimmedName.length < 1
      ? 'Give your robot a name (1-20 characters).'
      : trimmedName.length > 20
        ? 'Names can be at most 20 characters.'
        : null;

  if (!avatar || !pending) return null;

  const handleSave = async () => {
    if (nameError) return;
    setIsSaving(true);
    try {
      await update({ ...pending, mascot_name: trimmedName });
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

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Customize your Circuit</DialogTitle>
          <DialogDescription className="text-base">
            Level up by finishing lessons and quizzes to unlock more gear.
            {nextUnlockLevel !== null && (
              <span className="block mt-1 font-medium text-primary">
                Next unlock at Lv {nextUnlockLevel}
              </span>
            )}
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col sm:flex-row gap-6">
          {/* Live preview + rename */}
          <div className="flex flex-col items-center gap-4 sm:w-52 flex-shrink-0">
            <div className="rounded-xl border border-border bg-muted/30 p-4">
              <Mascot pose="idle" size={140} customization={pending} />
            </div>
            <div className="w-full">
              <label htmlFor="mascot-name" className="block text-sm font-medium mb-1.5">
                Robot name
              </label>
              <Input
                id="mascot-name"
                value={pendingName}
                maxLength={20}
                onChange={(e) => setPendingName(e.target.value)}
                aria-invalid={nameError !== null}
              />
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
            </div>
          </div>

          {/* Slot tabs + item grid */}
          <Tabs defaultValue="color" className="flex-1 min-w-0">
            <TabsList className="w-full">
              {SLOT_TABS.map(({ slot, label }) => (
                <TabsTrigger key={slot} value={slot} className="flex-1 px-2">
                  {label}
                </TabsTrigger>
              ))}
            </TabsList>
            {SLOT_TABS.map(({ slot }) => (
              <TabsContent key={slot} value={slot}>
                <div className="grid grid-cols-2 gap-3">
                  {itemsBySlot[slot].map((item) => {
                    const selected = pending[slot] === item.key;
                    return (
                      <button
                        key={`${slot}-${item.key}`}
                        type="button"
                        disabled={!item.unlocked}
                        onClick={() =>
                          setPending((prev) =>
                            prev ? { ...prev, [slot]: item.key } : prev
                          )
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
                          size={56}
                          customization={{ ...pending, [slot]: item.key }}
                        />
                        <span className="text-center leading-tight">{item.name}</span>
                        {!item.unlocked && (
                          <span className="inline-flex items-center gap-1 rounded-full bg-muted px-2 py-0.5 text-xs font-semibold text-muted-foreground">
                            <Lock className="h-3 w-3" />
                            Lv {item.required_level}
                          </span>
                        )}
                      </button>
                    );
                  })}
                </div>
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

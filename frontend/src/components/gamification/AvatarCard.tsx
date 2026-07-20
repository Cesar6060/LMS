import { Button } from '@/components/ui/Button';
import { Mascot } from '@/components/gamification/Mascot';
import { useAvatarContext } from '@/contexts/AvatarContext';
import { Paintbrush } from 'lucide-react';

interface AvatarCardProps {
  level: number;
  firstName?: string;
  onCustomize: () => void;
}

/**
 * Dashboard home for the student's Circuit avatar (Phase 33). Replaces the
 * Phase 32 greeting line: big customized mascot, name + greeting, level
 * chip, and a real Customize button. Render only for gamified students.
 */
export function AvatarCard({ level, firstName, onCustomize }: AvatarCardProps) {
  const { avatar } = useAvatarContext();
  const name = avatar?.mascot_name ?? 'Circuit';

  return (
    <div className="card-gaming rounded-xl p-6 mb-6 flex flex-col sm:flex-row items-center gap-6">
      <Mascot pose="idle" size={110} className="flex-shrink-0" />
      <div className="flex-1 text-center sm:text-left">
        <div className="flex items-center justify-center sm:justify-start gap-3 mb-1.5">
          <h2 className="text-2xl font-semibold">{name}</h2>
          <span className="inline-flex items-center rounded-full bg-primary/15 text-primary border border-primary/30 px-3 py-0.5 text-sm font-semibold">
            Lv {level}
          </span>
        </div>
        <p className="text-lg text-muted-foreground">
          {name} says: Welcome back{firstName ? `, ${firstName}` : ''}! Ready for today's quest?
        </p>
      </div>
      <Button size="lg" variant="outline" onClick={onCustomize} className="flex-shrink-0">
        <Paintbrush className="h-4 w-4 mr-2" />
        Customize
      </Button>
    </div>
  );
}

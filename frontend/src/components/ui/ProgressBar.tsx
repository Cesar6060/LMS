import { cn } from '@/lib/utils';

interface ProgressBarProps {
  /** Fill percentage, 0–100. */
  value: number;
  className?: string;
}

/** A thin neon progress bar reusing the `.progress-gaming` gaming utility. */
export function ProgressBar({ value, className }: ProgressBarProps) {
  const pct = Math.max(0, Math.min(100, value));
  return (
    <div className={cn('progress-gaming', className)}>
      <div className="progress-gaming-bar" style={{ width: `${pct}%` }} />
    </div>
  );
}

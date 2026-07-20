import { X } from 'lucide-react';
import { cn } from '@/lib/utils';

export type ToastVariant = 'default' | 'xp' | 'success';

export interface ToastOptions {
  message: string;
  icon?: string;
  variant?: ToastVariant;
  /** Auto-dismiss delay in ms (default 3000). */
  duration?: number;
}

export interface ToastItem extends ToastOptions {
  id: number;
}

const variantClasses: Record<ToastVariant, string> = {
  default: 'border-border text-foreground',
  xp: 'border-[rgba(34,197,94,0.4)] text-[hsl(142_71%_55%)] shadow-[0_0_18px_rgba(34,197,94,0.25)]',
  success: 'border-[rgba(34,197,94,0.4)] text-[hsl(142_71%_55%)]',
};

function Toast({ toast, onDismiss }: { toast: ToastItem; onDismiss: (id: number) => void }) {
  const variant = toast.variant ?? 'default';
  return (
    <div
      role="status"
      className={cn(
        'card-gaming pointer-events-auto flex items-center gap-3 rounded-lg border px-5 py-3 shadow-lg',
        'animate-in slide-in-from-bottom-4 fade-in duration-300',
        variantClasses[variant]
      )}
    >
      {toast.icon && <span className="text-2xl leading-none">{toast.icon}</span>}
      <span className="text-base font-bold tracking-wide">{toast.message}</span>
      <button
        onClick={() => onDismiss(toast.id)}
        className="ml-1 opacity-60 transition-opacity hover:opacity-100"
        aria-label="Dismiss"
      >
        <X className="h-4 w-4" />
      </button>
    </div>
  );
}

export function ToastViewport({
  toasts,
  onDismiss,
}: {
  toasts: ToastItem[];
  onDismiss: (id: number) => void;
}) {
  if (toasts.length === 0) return null;
  return (
    <div className="fixed bottom-4 right-4 z-[100] flex flex-col items-end gap-2 pointer-events-none">
      {toasts.map((t) => (
        <Toast key={t.id} toast={t} onDismiss={onDismiss} />
      ))}
    </div>
  );
}

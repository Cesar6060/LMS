import { Eye } from 'lucide-react';
import { useAuth } from '@/contexts/useAuth';

/**
 * Phase 56: slim persistent bar shown on every authenticated page while the
 * shared demo account is signed in. Rendered from Layout so individual pages
 * don't need to opt in; returns null for normal users.
 */
export function DemoBanner() {
  const { user } = useAuth();

  if (!user?.is_demo) {
    return null;
  }

  return (
    <div
      role="status"
      className="relative z-20 flex items-center justify-center gap-2.5 border-b
        border-amber-500/50 bg-amber-500/15 px-4 py-2.5 text-center text-base
        font-semibold text-amber-200"
    >
      <Eye className="h-5 w-5 flex-shrink-0" aria-hidden="true" />
      <span>
        You&apos;re in the shared demo &mdash; progress is visible to other
        visitors and resets nightly.
      </span>
    </div>
  );
}

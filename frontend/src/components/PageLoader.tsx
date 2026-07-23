import { Loader2 } from 'lucide-react';

// Full-page centered spinner — Suspense fallback for lazy-loaded routes and
// the auth-loading states in App.tsx.
export function PageLoader() {
  return (
    <div className="min-h-screen flex items-center justify-center">
      <Loader2 className="h-8 w-8 animate-spin text-primary" />
    </div>
  );
}

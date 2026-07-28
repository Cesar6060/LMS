import { useCallback, useEffect, useState, ReactNode } from 'react';
import { ToastViewport, type ToastItem, type ToastOptions } from '@/components/ui/Toast';
import { setDemoBlockedListener } from '@/services/api';
import { ToastContext } from './useToast';

let nextId = 1;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const dismiss = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const show = useCallback(
    (opts: ToastOptions) => {
      const id = nextId++;
      setToasts((prev) => [...prev, { id, ...opts }]);
      window.setTimeout(() => dismiss(id), opts.duration ?? 3000);
    },
    [dismiss]
  );

  // Phase 56: the api interceptor announces blocked demo writes through this
  // bridge so every 403 demo_blocked surfaces as one consistent toast.
  useEffect(() => {
    setDemoBlockedListener((message) => show({ message, duration: 4000 }));
    return () => setDemoBlockedListener(null);
  }, [show]);

  return (
    <ToastContext.Provider value={{ show }}>
      {children}
      <ToastViewport toasts={toasts} onDismiss={dismiss} />
    </ToastContext.Provider>
  );
}

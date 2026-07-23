import { useCallback, useState, ReactNode } from 'react';
import { ToastViewport, type ToastItem, type ToastOptions } from '@/components/ui/Toast';
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

  return (
    <ToastContext.Provider value={{ show }}>
      {children}
      <ToastViewport toasts={toasts} onDismiss={dismiss} />
    </ToastContext.Provider>
  );
}

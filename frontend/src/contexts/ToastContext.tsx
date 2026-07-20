import { createContext, useContext, useCallback, useState, ReactNode } from 'react';
import { ToastViewport, type ToastItem, type ToastOptions } from '@/components/ui/Toast';

interface ToastContextType {
  show: (opts: ToastOptions) => void;
}

const ToastContext = createContext<ToastContextType | undefined>(undefined);

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

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    throw new Error('useToast must be used within a ToastProvider');
  }
  return ctx;
}

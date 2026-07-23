import { createContext, useContext } from 'react';
import type { ToastOptions } from '@/components/ui/Toast';

export interface ToastContextType {
  show: (opts: ToastOptions) => void;
}

// Context + hook live apart from ToastProvider so ToastContext.tsx only
// exports a component (react-refresh/only-export-components).
export const ToastContext = createContext<ToastContextType | undefined>(undefined);

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    throw new Error('useToast must be used within a ToastProvider');
  }
  return ctx;
}

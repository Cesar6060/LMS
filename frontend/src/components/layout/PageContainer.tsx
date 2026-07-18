import { type ReactNode } from 'react';
import { cn } from '@/lib/utils';

interface PageContainerProps {
  children: ReactNode;
  /** Tailwind max-width class; defaults to the standard page width. */
  maxWidth?: string;
  className?: string;
}

export function PageContainer({
  children,
  maxWidth = 'max-w-7xl',
  className,
}: PageContainerProps) {
  return (
    <div className={cn('container mx-auto px-6 py-8', maxWidth, className)}>
      {children}
    </div>
  );
}

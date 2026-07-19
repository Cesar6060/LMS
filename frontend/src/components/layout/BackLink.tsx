import { Link } from 'react-router';
import { ChevronLeft } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { cn } from '@/lib/utils';

interface BackLinkProps {
  to: string;
  /** Names the destination: renders "Back to {label}". */
  label: string;
  className?: string;
}

export function BackLink({ to, label, className }: BackLinkProps) {
  return (
    <Button
      asChild
      variant="ghost"
      size="sm"
      className={cn('-ml-3 text-muted-foreground hover:text-foreground', className)}
    >
      <Link to={to}>
        <ChevronLeft className="h-4 w-4 mr-1" />
        Back to {label}
      </Link>
    </Button>
  );
}

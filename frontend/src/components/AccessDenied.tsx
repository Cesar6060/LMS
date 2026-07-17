import { Link } from 'react-router';
import { Button } from '@/components/ui/Button';
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '@/components/ui/Card';
import { Home, ShieldAlert } from 'lucide-react';

interface AccessDeniedProps {
  message?: string;
}

export function AccessDenied({ message }: AccessDeniedProps) {
  return (
    <div className="min-h-[calc(100vh-4rem)] flex items-center justify-center px-4">
      <Card className="w-full max-w-md text-center">
        <CardHeader className="pb-4">
          <div className="flex justify-center mb-4">
            <ShieldAlert className="h-16 w-16 text-muted-foreground/40" />
          </div>
          <CardTitle className="text-2xl">Access Denied</CardTitle>
          <CardDescription>
            {message || "You don't have permission to view this page."}
          </CardDescription>
        </CardHeader>
        <CardContent className="pb-2">
          <span className="text-sm text-muted-foreground">
            If you think this is a mistake, check that you're signed in with the right account.
          </span>
        </CardContent>
        <CardFooter className="flex justify-center pt-4">
          <Link to="/dashboard" className="w-full sm:w-auto">
            <Button className="w-full">
              <Home className="h-4 w-4 mr-2" />
              Go to Dashboard
            </Button>
          </Link>
        </CardFooter>
      </Card>
    </div>
  );
}

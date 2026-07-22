import { useState, type FormEvent } from 'react';
import { Link, useLocation, useNavigate, useSearchParams } from 'react-router';
import { useAuth } from '@/contexts/AuthContext';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '@/components/ui/Card';
import { AnimatedBackground } from '@/components/ui/AnimatedBackground';
import { Rocket, Loader2 } from 'lucide-react';

export function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isDemoLoading, setIsDemoLoading] = useState(false);

  const { login, loginAsDemo } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();

  // Where to land after login: router state from a guard redirect, then the
  // ?next= param set by the 401 interceptor's full-page redirect. Only accept
  // relative paths ('/...' but not '//...') to avoid open redirects.
  const isSafePath = (path: string | null | undefined): path is string =>
    !!path && path.startsWith('/') && !path.startsWith('//');
  const from = (location.state as { from?: { pathname: string; search?: string } } | null)?.from;
  const fromPath = from ? `${from.pathname}${from.search ?? ''}` : null;
  const nextParam = searchParams.get('next');
  const redirectTo = [fromPath, nextParam].find(isSafePath) ?? '/dashboard';

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    try {
      await login({ email, password });
      navigate(redirectTo, { replace: true });
    } catch (err: unknown) {
      const error = err as { response?: { data?: { non_field_errors?: string[]; detail?: string } } };
      if (error.response?.data?.non_field_errors) {
        setError(error.response.data.non_field_errors[0]);
      } else if (error.response?.data?.detail) {
        setError(error.response.data.detail);
      } else {
        setError('Login failed. Please check your credentials.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleDemoLogin = async () => {
    setError('');
    setIsDemoLoading(true);

    try {
      await loginAsDemo();
      navigate(redirectTo, { replace: true });
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } };
      setError(
        error.response?.data?.detail ??
          'The demo is unavailable right now. Please try again in a moment.'
      );
    } finally {
      setIsDemoLoading(false);
    }
  };

  return (
    <AnimatedBackground className="min-h-screen flex items-center justify-center bg-background px-4" showMouseGlow={true}>
      <Card className="w-full max-w-md backdrop-blur-sm bg-card/95">
        <CardHeader className="space-y-1 text-center">
          <div className="flex justify-center mb-4">
            <Rocket className="h-12 w-12 animate-pulse text-primary" style={{ filter: 'drop-shadow(0 0 8px rgba(34,197,94,0.35))' }} />
          </div>
          <CardTitle className="text-2xl text-gradient-gaming" style={{ fontFamily: 'Orbitron, sans-serif' }}>Welcome back</CardTitle>
          <CardDescription>
            Enter your credentials to access your account
          </CardDescription>
        </CardHeader>
        <form onSubmit={handleSubmit}>
          <CardContent className="space-y-4">
            {error && (
              <div className="rounded-md bg-destructive/15 p-3 text-sm text-destructive">
                {error}
              </div>
            )}
            <div className="space-y-2">
              <label htmlFor="email" className="text-sm font-medium">
                Email
              </label>
              <Input
                id="email"
                type="email"
                placeholder="you@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete="email"
              />
            </div>
            <div className="space-y-2">
              <label htmlFor="password" className="text-sm font-medium">
                Password
              </label>
              <Input
                id="password"
                type="password"
                placeholder="Enter your password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                autoComplete="current-password"
              />
            </div>
            <div className="text-right">
              <Link
                to="/forgot-password"
                className="text-sm text-muted-foreground hover:text-primary"
              >
                Forgot password?
              </Link>
            </div>
          </CardContent>
          <CardFooter className="flex flex-col space-y-4">
            <Button type="submit" className="w-full" variant="neon" disabled={isLoading || isDemoLoading}>
              {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Sign in
            </Button>
            <p className="text-center text-sm text-muted-foreground">Just exploring?</p>
            <Button
              type="button"
              variant="secondary"
              className="w-full"
              onClick={handleDemoLogin}
              disabled={isLoading || isDemoLoading}
            >
              {isDemoLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Try the demo
            </Button>
          </CardFooter>
        </form>
      </Card>
    </AnimatedBackground>
  );
}

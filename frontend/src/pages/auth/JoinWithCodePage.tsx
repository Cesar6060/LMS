import { useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router';
import { inviteService } from '@/services/invites';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import {
  Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter,
} from '@/components/ui/Card';
import { AnimatedBackground } from '@/components/ui/AnimatedBackground';
import { KeyRound, Loader2 } from 'lucide-react';

const GENERIC_ERROR = "That code and email don't match an open invitation.";

/**
 * Phase 67 — fallback entry point for a student whose invite email was
 * filtered. The code is only a delivery channel: redeeming it still requires a
 * pending invite for that exact address, so this page never creates anything.
 * On success it hands off to the existing /invite/<token> accept flow.
 */
export function JoinWithCodePage() {
  const navigate = useNavigate();

  const [joinCode, setJoinCode] = useState('');
  const [email, setEmail] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    setSubmitting(true);

    try {
      // The backend normalizes the code (case, spaces, dashes) — send it raw.
      const result = await inviteService.joinWithCode(joinCode, email.trim());
      navigate(`/invite/${result.token}`);
    } catch (err: unknown) {
      const e = err as { response?: { status?: number; data?: { detail?: string } } };
      if (e.response?.status === 429) {
        setError('Too many attempts — please wait a while and try again.');
      } else {
        setError(e.response?.data?.detail ?? GENERIC_ERROR);
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AnimatedBackground
      className="min-h-screen flex items-center justify-center bg-background px-4"
      showMouseGlow={true}
    >
      <Card className="w-full max-w-md backdrop-blur-sm bg-card/95">
        <CardHeader className="space-y-1 text-center">
          <div className="flex justify-center mb-4">
            <KeyRound className="h-12 w-12 text-primary" />
          </div>
          <CardTitle className="text-2xl">Join with a class code</CardTitle>
          <CardDescription className="text-base">
            Didn't get the invitation email? Enter the class code from your
            teacher to get in.
          </CardDescription>
        </CardHeader>
        <form onSubmit={handleSubmit}>
          <CardContent className="space-y-5">
            {error && (
              <div
                role="alert"
                className="rounded-md bg-destructive/15 p-3 text-base text-destructive"
              >
                {error}
              </div>
            )}
            <div className="space-y-2">
              <label htmlFor="join-code" className="text-base font-medium">
                Class code
              </label>
              <Input
                id="join-code"
                value={joinCode}
                onChange={(e) => setJoinCode(e.target.value)}
                required
                autoFocus
                autoComplete="off"
                autoCapitalize="characters"
                spellCheck={false}
                placeholder="ABCD2345"
                className="uppercase tracking-widest text-2xl h-14 text-center font-mono"
              />
            </div>
            <div className="space-y-2">
              <label htmlFor="join-email" className="text-base font-medium">
                Your email
              </label>
              <Input
                id="join-email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete="email"
                placeholder="you@example.com"
                className="text-lg h-12"
              />
              <p className="text-sm text-muted-foreground">
                Use the same email address your teacher invited — the code only
                works for an invited address.
              </p>
            </div>
          </CardContent>
          <CardFooter className="flex flex-col space-y-4">
            <Button
              type="submit"
              className="w-full"
              size="lg"
              variant="neon"
              disabled={submitting}
            >
              {submitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Continue
            </Button>
            <p className="text-center text-sm text-muted-foreground">
              Already have an account?{' '}
              <Link to="/login" className="underline hover:text-primary">
                Log in
              </Link>
            </p>
          </CardFooter>
        </form>
      </Card>
    </AnimatedBackground>
  );
}

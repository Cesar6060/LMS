import { useState, useEffect, useRef, type FormEvent } from 'react';
import { Link, useNavigate, useParams } from 'react-router';
import { useAuth } from '@/contexts/useAuth';
import { inviteService } from '@/services/invites';
import type { InviteTokenInfo } from '@/types';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import {
  Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter,
} from '@/components/ui/Card';
import { AnimatedBackground } from '@/components/ui/AnimatedBackground';
import { GraduationCap, Loader2, MailX } from 'lucide-react';

interface FieldErrors {
  first_name?: string[];
  last_name?: string[];
  password?: string[];
  agree_terms?: string[];
}

const DEAD_STATUS_MESSAGES: Record<string, { title: string; body: string }> = {
  invalid: {
    title: 'Invitation not found',
    body: 'This invitation link is not valid. Check that you copied the full link from the email, or ask your instructor for a new one.',
  },
  expired: {
    title: 'Invitation expired',
    body: 'This invitation has expired. Ask your instructor to send you a new one.',
  },
  revoked: {
    title: 'Invitation revoked',
    body: 'This invitation was revoked by the instructor. If you think this is a mistake, contact your instructor.',
  },
  accepted: {
    title: 'Invitation already used',
    body: 'This invitation has already been used. If that was you, just log in to get to your course.',
  },
};

export function AcceptInvitePage() {
  const { token } = useParams<{ token: string }>();
  const navigate = useNavigate();
  const { user, isAuthenticated, isLoading: authLoading, refreshUser, logout } = useAuth();

  const [info, setInfo] = useState<InviteTokenInfo | null>(null);
  const [infoLoading, setInfoLoading] = useState(true);

  // New-account form
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [agreeTerms, setAgreeTerms] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [formError, setFormError] = useState('');

  // Existing-account auto-accept
  const [wrongAccountError, setWrongAccountError] = useState('');
  const autoAcceptStarted = useRef(false);

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    inviteService
      .getInvite(token)
      .then((data) => {
        if (!cancelled) setInfo(data);
      })
      .catch(() => {
        // Unknown token comes back as 404 — treat anything else the same way.
        if (!cancelled) {
          setInfo({
            course_title: null,
            course_code: null,
            email_masked: null,
            status: 'invalid',
            account_exists: false,
          });
        }
      })
      .finally(() => {
        if (!cancelled) setInfoLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [token]);

  // Existing-account path: once the invitee is logged in, accept silently and
  // land them in the course.
  useEffect(() => {
    if (
      !token || !info || autoAcceptStarted.current ||
      info.status !== 'pending' || !info.account_exists ||
      authLoading || !isAuthenticated
    ) {
      return;
    }
    autoAcceptStarted.current = true;
    inviteService
      .acceptInviteExistingAccount(token)
      .then(() => {
        navigate(`/courses/${info.course_code}`, { replace: true });
      })
      .catch((err: unknown) => {
        const e = err as { response?: { data?: { detail?: string } } };
        setWrongAccountError(
          e.response?.data?.detail ??
            'Could not accept the invitation with this account.'
        );
      });
  }, [token, info, authLoading, isAuthenticated, navigate]);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!token || !info) return;

    setFieldErrors({});
    setFormError('');
    if (password !== confirmPassword) {
      setFieldErrors({ password: ['Passwords do not match.'] });
      return;
    }

    setSubmitting(true);
    try {
      await inviteService.acceptInviteNewAccount(token, {
        first_name: firstName.trim(),
        last_name: lastName.trim(),
        password,
        agree_terms: agreeTerms,
      });
      await refreshUser();
      navigate(`/courses/${info.course_code}`, { replace: true });
    } catch (err: unknown) {
      const e = err as {
        response?: { status?: number; data?: FieldErrors & { detail?: string } };
      };
      if (e.response?.status === 429) {
        setFormError('Too many attempts — please wait a while and try again.');
      } else if (e.response?.data?.detail) {
        setFormError(e.response.data.detail);
      } else if (e.response?.data) {
        setFieldErrors(e.response.data);
      } else {
        setFormError('Something went wrong. Please try again.');
      }
    } finally {
      setSubmitting(false);
    }
  };

  const goToLogin = async () => {
    // Signed in as someone else? Sign out first, or /login's PublicRoute
    // guard would bounce straight back to the dashboard.
    if (isAuthenticated) {
      await logout();
    }
    navigate('/login', {
      state: { from: { pathname: `/invite/${token}` } },
    });
  };

  const renderFieldError = (errors?: string[]) =>
    errors && errors.length > 0 ? (
      <p className="text-sm text-destructive">{errors[0]}</p>
    ) : null;

  const legalFooter = (
    <p className="text-center text-sm text-muted-foreground">
      <Link to="/terms" target="_blank" className="underline hover:text-primary">
        Terms of Service
      </Link>{' '}
      ·{' '}
      <Link to="/privacy" target="_blank" className="underline hover:text-primary">
        Privacy Policy
      </Link>
    </p>
  );

  let content: React.ReactNode;

  if (infoLoading || authLoading || !info) {
    content = (
      <Card className="w-full max-w-md backdrop-blur-sm bg-card/95">
        <CardContent className="py-16 flex justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
        </CardContent>
      </Card>
    );
  } else if (info.status !== 'pending') {
    const message = DEAD_STATUS_MESSAGES[info.status] ?? DEAD_STATUS_MESSAGES.invalid;
    content = (
      <Card className="w-full max-w-md backdrop-blur-sm bg-card/95">
        <CardHeader className="space-y-1 text-center">
          <div className="flex justify-center mb-4">
            <MailX className="h-12 w-12 text-muted-foreground" />
          </div>
          <CardTitle className="text-2xl">{message.title}</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-base text-center text-muted-foreground">{message.body}</p>
        </CardContent>
        <CardFooter className="flex flex-col space-y-4">
          <Button className="w-full" size="lg" onClick={() => navigate('/login')}>
            Go to login
          </Button>
          {legalFooter}
        </CardFooter>
      </Card>
    );
  } else if (info.account_exists) {
    content = (
      <Card className="w-full max-w-md backdrop-blur-sm bg-card/95">
        <CardHeader className="space-y-1 text-center">
          <div className="flex justify-center mb-4">
            <GraduationCap className="h-12 w-12 text-primary" />
          </div>
          <CardTitle className="text-2xl">Join {info.course_title}</CardTitle>
          <CardDescription className="text-base">
            This invitation is for <strong>{info.email_masked}</strong>, which
            already has an account.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {wrongAccountError ? (
            <div className="rounded-md bg-destructive/15 p-3 text-base text-destructive">
              {wrongAccountError}
              {user && (
                <span className="block mt-1 text-sm">
                  You are currently signed in as {user.email}.
                </span>
              )}
            </div>
          ) : isAuthenticated ? (
            <div className="flex items-center justify-center gap-2 py-4 text-muted-foreground">
              <Loader2 className="h-5 w-5 animate-spin" />
              Joining the course…
            </div>
          ) : (
            <p className="text-base text-center text-muted-foreground">
              Log in with that account to join the course.
            </p>
          )}
        </CardContent>
        <CardFooter className="flex flex-col space-y-4">
          {(!isAuthenticated || wrongAccountError) && (
            <Button className="w-full" size="lg" variant="neon" onClick={goToLogin}>
              Log in to join
            </Button>
          )}
          {legalFooter}
        </CardFooter>
      </Card>
    );
  } else {
    content = (
      <Card className="w-full max-w-md backdrop-blur-sm bg-card/95">
        <CardHeader className="space-y-1 text-center">
          <div className="flex justify-center mb-4">
            <GraduationCap className="h-12 w-12 text-primary" />
          </div>
          <CardTitle className="text-2xl">Join {info.course_title}</CardTitle>
          <CardDescription className="text-base">
            You were invited as <strong>{info.email_masked}</strong>. Create
            your account to get started.
          </CardDescription>
        </CardHeader>
        <form onSubmit={handleSubmit}>
          <CardContent className="space-y-4">
            {formError && (
              <div className="rounded-md bg-destructive/15 p-3 text-base text-destructive">
                {formError}
              </div>
            )}
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <label htmlFor="first-name" className="text-sm font-medium">
                  First name
                </label>
                <Input
                  id="first-name"
                  value={firstName}
                  onChange={(e) => setFirstName(e.target.value)}
                  required
                  autoComplete="given-name"
                />
                {renderFieldError(fieldErrors.first_name)}
              </div>
              <div className="space-y-2">
                <label htmlFor="last-name" className="text-sm font-medium">
                  Last name
                </label>
                <Input
                  id="last-name"
                  value={lastName}
                  onChange={(e) => setLastName(e.target.value)}
                  required
                  autoComplete="family-name"
                />
                {renderFieldError(fieldErrors.last_name)}
              </div>
            </div>
            <div className="space-y-2">
              <label htmlFor="password" className="text-sm font-medium">
                Password
              </label>
              <Input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                autoComplete="new-password"
              />
              {renderFieldError(fieldErrors.password)}
            </div>
            <div className="space-y-2">
              <label htmlFor="confirm-password" className="text-sm font-medium">
                Confirm password
              </label>
              <Input
                id="confirm-password"
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
                autoComplete="new-password"
              />
            </div>
            <div className="space-y-2">
              <label className="flex items-start gap-3 text-base">
                <input
                  type="checkbox"
                  checked={agreeTerms}
                  onChange={(e) => setAgreeTerms(e.target.checked)}
                  className="mt-1 h-4 w-4"
                  required
                />
                <span>
                  I agree to the{' '}
                  <Link to="/terms" target="_blank" className="underline hover:text-primary">
                    Terms of Service
                  </Link>{' '}
                  and{' '}
                  <Link to="/privacy" target="_blank" className="underline hover:text-primary">
                    Privacy Policy
                  </Link>
                  .
                </span>
              </label>
              {renderFieldError(fieldErrors.agree_terms)}
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
              Create account & join course
            </Button>
            <p className="text-center text-sm text-muted-foreground">
              Already have an account?{' '}
              <button
                type="button"
                onClick={goToLogin}
                className="underline hover:text-primary"
              >
                Log in
              </button>
            </p>
          </CardFooter>
        </form>
      </Card>
    );
  }

  return (
    <AnimatedBackground
      className="min-h-screen flex items-center justify-center bg-background px-4"
      showMouseGlow={true}
    >
      {content}
    </AnimatedBackground>
  );
}

import { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { courseService } from '@/services/courses';
import { isForbidden } from '@/services/api';
import { copyToClipboard } from '@/lib/clipboard';
import {
  AlertCircle, CheckCircle, Copy, KeyRound, Power, RefreshCw,
} from 'lucide-react';

interface ClassCodeCardProps {
  courseCode: string;
  className?: string;
}

/**
 * The class code, with its full lifecycle: generate / rotate / turn off.
 *
 * Phase 68 extracted this out of StudentRosterPage so ManageCoursePage can
 * render the SAME component. That page's most prominent code used to be the
 * ENROLLMENT code — which under invite-only fails for every student without
 * an account, i.e. all of them on day one. The class code is the one that
 * works, so it takes the prominent slot; one component means the two pages
 * cannot drift into showing different states for the same course.
 *
 * The card hides itself entirely on a 403: the demo course refuses the
 * join-code endpoint outright (`demo_blocked`), and offering an action that
 * can never work is worse than offering nothing.
 */
export function ClassCodeCard({ courseCode, className }: ClassCodeCardProps) {
  const [joinCode, setJoinCode] = useState<string | null>(null);
  const [available, setAvailable] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [copied, setCopied] = useState(false);
  const [confirmRotate, setConfirmRotate] = useState(false);

  const loadJoinCode = useCallback(async () => {
    try {
      setJoinCode(await courseService.getJoinCode(courseCode));
    } catch (err) {
      if (isForbidden(err)) {
        // The demo course refuses this endpoint outright (403 demo_blocked).
        // Hide the card rather than offer an action that can never work.
        setAvailable(false);
      } else {
        // A blip, a 500, a 429 — keep the card and say so, rather than
        // silently removing a feature the instructor may be looking for.
        setError('Could not load the class code. Reload to try again.');
      }
      console.error('Failed to load the join code:', err);
    }
  }, [courseCode]);

  useEffect(() => {
    loadJoinCode();
  }, [loadJoinCode]);

  const handleCopy = async () => {
    if (!joinCode) return;
    setError('');
    if (await copyToClipboard(joinCode)) {
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2500);
    } else {
      // Never let a copy that did nothing look like one that worked. The code
      // is on screen at 4xl and selectable, so pointing at it is enough.
      setError('Your browser blocked the copy — select the code above instead.');
    }
  };

  const handleGenerate = async () => {
    try {
      setBusy(true);
      setError('');
      setJoinCode(await courseService.rotateJoinCode(courseCode));
    } catch (err) {
      setError('Could not update the class code');
      console.error(err);
    } finally {
      setBusy(false);
      setConfirmRotate(false);
    }
  };

  const handleDisable = async () => {
    try {
      setBusy(true);
      setError('');
      await courseService.disableJoinCode(courseCode);
      setJoinCode(null);
    } catch (err) {
      setError('Could not turn off the class code');
      console.error(err);
    } finally {
      setBusy(false);
    }
  };

  if (!available) return null;

  return (
    <>
      <Card className={className}>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-xl">
            <KeyRound className="h-5 w-5" />
            Class code
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-base text-muted-foreground">
            The code to read out to your class. It only works together with an
            email address you have already invited, so it is safe to say out
            loud — on its own it enrols nobody. It is also the way in for a
            student whose invitation email was blocked or never arrived.
          </p>

          {error && (
            <div className="bg-destructive/10 border border-destructive/20 rounded-lg p-3 flex items-center gap-2">
              <AlertCircle className="h-4 w-4 text-destructive shrink-0" />
              <p className="text-sm text-destructive">{error}</p>
            </div>
          )}

          {joinCode ? (
            <>
              <div className="flex flex-wrap items-center gap-4">
                <span className="font-mono text-4xl font-bold tracking-[0.2em] select-all">
                  {joinCode}
                </span>
                <Button size="lg" variant="outline" onClick={handleCopy}>
                  {copied ? (
                    <>
                      <CheckCircle className="h-4 w-4 mr-2" />
                      Copied
                    </>
                  ) : (
                    <>
                      <Copy className="h-4 w-4 mr-2" />
                      Copy code
                    </>
                  )}
                </Button>
              </div>

              <div className="rounded-lg border bg-muted/30 p-4">
                <p className="text-sm font-semibold mb-1">Read this to your class:</p>
                <p className="text-base select-all">
                  Go to {window.location.origin}/join, enter the class code{' '}
                  <strong>{joinCode}</strong>, and the email address I invited you
                  with.
                </p>
              </div>

              <div className="flex flex-wrap gap-3">
                <Button
                  size="lg"
                  variant="outline"
                  onClick={() => setConfirmRotate(true)}
                  disabled={busy}
                >
                  <RefreshCw className="h-4 w-4 mr-2" />
                  Rotate code
                </Button>
                <Button
                  size="lg"
                  variant="outline"
                  onClick={handleDisable}
                  disabled={busy}
                  className="text-destructive hover:text-destructive"
                >
                  <Power className="h-4 w-4 mr-2" />
                  Turn off
                </Button>
              </div>
            </>
          ) : (
            <Button size="lg" onClick={handleGenerate} disabled={busy}>
              <KeyRound className="h-4 w-4 mr-2" />
              {busy ? 'Generating...' : 'Generate a class code'}
            </Button>
          )}
        </CardContent>
      </Card>

      <ConfirmDialog
        open={confirmRotate}
        onOpenChange={setConfirmRotate}
        title="Rotate the class code?"
        confirmLabel="Rotate code"
        loadingLabel="Rotating..."
        onConfirm={handleGenerate}
        isLoading={busy}
      >
        The current code <span className="font-mono font-medium text-foreground">{joinCode}</span>{' '}
        stops working immediately. Any student who has it but has not joined yet
        will need the new one.
      </ConfirmDialog>
    </>
  );
}

export default ClassCodeCard;

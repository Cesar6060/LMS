import { Link } from 'react-router';
import { AlertTriangle } from 'lucide-react';

// Plain-language draft, written for a course platform used by students who
// may be minors (parental consent is collected offline by the instructor).
// The DRAFT banner stays until the site owner signs off on the wording.

export function TermsPage() {
  return (
    <div className="min-h-screen bg-background">
      <div className="mx-auto max-w-3xl px-4 py-12">
        <div className="mb-8 flex items-start gap-3 rounded-lg border border-amber-300 bg-amber-50 p-4 text-amber-800 dark:border-amber-700 dark:bg-amber-900/30 dark:text-amber-300">
          <AlertTriangle className="h-5 w-5 mt-0.5 shrink-0" />
          <p className="text-base font-medium">
            DRAFT — pending review. This document has not yet been finalized
            and is not legal advice.
          </p>
        </div>

        <h1 className="text-4xl font-bold mb-2">Terms of Service</h1>
        <p className="text-muted-foreground mb-10">Last updated: July 2026</p>

        <div className="space-y-8 text-lg leading-relaxed">
          <section>
            <h2 className="text-2xl font-semibold mb-3">What STEM Quest is</h2>
            <p>
              STEM Quest is an online learning platform for Computer Science
              and Robotics courses. Your instructor invites you to a course;
              you use the site to read lessons, take quizzes, join
              discussions, and track your progress.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-3">Your account</h2>
            <ul className="list-disc pl-6 space-y-2">
              <li>
                You get an account through an instructor&apos;s invitation.
                There is no open sign-up.
              </li>
              <li>
                Keep your password private. You are responsible for what
                happens under your account.
              </li>
              <li>
                If you are under 18, a parent or guardian must have given
                your instructor permission for you to use the site. That
                consent is collected by the instructor outside the platform.
              </li>
            </ul>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-3">Rules of behavior</h2>
            <ul className="list-disc pl-6 space-y-2">
              <li>Be respectful in discussions and replies.</li>
              <li>
                Don&apos;t post anything harmful, hateful, or unrelated spam.
              </li>
              <li>Don&apos;t try to access other people&apos;s accounts or data.</li>
              <li>
                Don&apos;t attempt to break, overload, or reverse-engineer the
                platform.
              </li>
            </ul>
            <p className="mt-3">
              Instructors can remove students from a course, and accounts
              that break these rules can be suspended.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-3">Your work and grades</h2>
            <p>
              Content you submit (discussion posts, quiz answers) stays yours.
              You give us permission to store and display it so the platform
              can work — for example, showing your posts to classmates and
              your grades to your instructor.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-3">The demo course</h2>
            <p>
              The public &quot;Try the demo&quot; account is shared by all
              visitors and is reset regularly. Anything you do there can be
              seen by other visitors and will be wiped.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-3">No warranty</h2>
            <p>
              The platform is provided as-is. We work to keep it reliable and
              secure, but we can&apos;t promise it will always be available or
              error-free.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-3">Changes</h2>
            <p>
              If these terms change in a meaningful way, we&apos;ll note the
              new date at the top of this page.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-3">Privacy</h2>
            <p>
              How we handle your data is described in the{' '}
              <Link to="/privacy" className="underline hover:text-primary">
                Privacy Policy
              </Link>
              .
            </p>
          </section>
        </div>

        <div className="mt-12 border-t pt-6">
          <Link to="/login" className="text-base underline hover:text-primary">
            Back to login
          </Link>
        </div>
      </div>
    </div>
  );
}

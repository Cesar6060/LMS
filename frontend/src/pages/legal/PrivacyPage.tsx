import { Link } from 'react-router';
import { AlertTriangle } from 'lucide-react';

// Plain-language draft tailored to what the platform actually collects:
// name, email, course progress, and grades. Students may be minors whose
// parental consent is collected offline. Sentry error reporting runs with
// PII scrubbed; there are no ads and no third-party tracking.
// The DRAFT banner stays until the site owner signs off on the wording.

export function PrivacyPage() {
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

        <h1 className="text-4xl font-bold mb-2">Privacy Policy</h1>
        <p className="text-muted-foreground mb-10">Last updated: July 2026</p>

        <div className="space-y-8 text-lg leading-relaxed">
          <section>
            <h2 className="text-2xl font-semibold mb-3">What we collect</h2>
            <p>We only collect what the platform needs to run a course:</p>
            <ul className="list-disc pl-6 space-y-2 mt-3">
              <li>
                <strong>Your name and email address</strong> — from your
                instructor&apos;s invitation and the account you create.
              </li>
              <li>
                <strong>Your course activity</strong> — which lessons
                you&apos;ve completed, quiz answers and scores, grades, and
                posts you write in course discussions.
              </li>
              <li>
                <strong>Basic technical logs</strong> — the kind every web
                server records to stay secure and diagnose problems.
              </li>
            </ul>
            <p className="mt-3">
              That&apos;s it. No advertising profiles, no selling data, no
              third-party tracking cookies, no analytics beyond error
              monitoring.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-3">Who can see your data</h2>
            <ul className="list-disc pl-6 space-y-2">
              <li>
                <strong>Your instructor</strong> sees your name, email,
                progress, and grades for their course.
              </li>
              <li>
                <strong>Your classmates</strong> see your name and what you
                post in course discussions — never your grades or email.
              </li>
              <li>
                <strong>The site operator</strong> can access the database to
                run and maintain the service.
              </li>
            </ul>
            <p className="mt-3">We never sell or rent your information.</p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-3">Students under 18</h2>
            <p>
              Many of our students are minors. Accounts are created only
              through instructor invitations, and instructors collect a
              parent or guardian&apos;s written consent before inviting a
              minor. If you are a parent and want to review or delete your
              child&apos;s data, contact the instructor who runs the course.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-3">Error monitoring</h2>
            <p>
              We use Sentry to learn about crashes and bugs. Error reports
              are scrubbed of personal information before they are sent —
              they describe what broke, not who you are.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-3">Where data lives</h2>
            <p>
              Your data is stored in managed cloud databases with encrypted
              connections, and backups are kept so coursework isn&apos;t
              lost. Emails (invitations, password resets, announcements) are
              sent through a transactional email provider.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-3">Your choices</h2>
            <ul className="list-disc pl-6 space-y-2">
              <li>
                You can update your name and preferences in Settings.
              </li>
              <li>
                You can turn off announcement emails in Settings.
              </li>
              <li>
                You can ask your instructor to remove you from a course, or
                to have your account and data deleted.
              </li>
            </ul>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-3">Changes</h2>
            <p>
              If this policy changes in a meaningful way, we&apos;ll note the
              new date at the top of this page.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-3">Terms</h2>
            <p>
              The rules for using the platform are in the{' '}
              <Link to="/terms" className="underline hover:text-primary">
                Terms of Service
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

/**
 * Whether an API-supplied string is safe to hand to `navigate()`.
 *
 * `Notification.related_url` is the one string the app follows straight from
 * the API, so the router only accepts a relative in-app path from it. Rejected:
 * protocol-relative (`//example.com/x`), backslash-separated (`/\example.com`),
 * and anything not anchored at the root (`dashboard`, which resolves against
 * whatever route happens to be open). A leading `/` also rules out a scheme —
 * `http:`, `javascript:` — since a scheme can only appear at the start.
 */
export function isInAppPath(url: string): boolean {
  // Browsers strip ASCII whitespace and C0 controls while parsing a URL, so
  // "/<tab>/example.com" resolves as protocol-relative. Normalize the same way
  // before deciding.
  const path = Array.from(url)
    .filter(char => {
      const code = char.charCodeAt(0);
      return code > 0x20 && code !== 0x7f;
    })
    .join('');

  if (!path.startsWith('/')) return false;
  return !path.startsWith('//') && !path.startsWith('/\\');
}

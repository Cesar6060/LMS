/**
 * Write to the clipboard, reporting whether it actually landed.
 *
 * `navigator.clipboard` is absent on insecure origins and rejects when the
 * browser withholds permission. Both must surface the text instead of failing
 * silently — a copy button that quietly does nothing is worse than no button
 * at all.
 *
 * The timeout is not belt-and-braces: writeText does not always settle. When
 * the browser wants a permission decision it can leave the promise pending
 * indefinitely (reproduced under Chrome automation in phase 67), which would
 * strand the caller on "busy" with no copy and no explanation. Treat silence
 * as failure and reveal the text.
 */
export async function copyToClipboard(text: string): Promise<boolean> {
  const timeout = new Promise<false>((resolve) =>
    window.setTimeout(() => resolve(false), 2000)
  );
  try {
    return await Promise.race([
      navigator.clipboard.writeText(text).then(() => true),
      timeout,
    ]);
  } catch {
    return false;
  }
}

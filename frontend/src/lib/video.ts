/**
 * Extract YouTube video ID from various URL formats or return the ID if already extracted.
 * Supports:
 * - https://www.youtube.com/watch?v=VIDEO_ID
 * - https://youtu.be/VIDEO_ID
 * - https://www.youtube.com/embed/VIDEO_ID
 * - VIDEO_ID (already extracted)
 */
export function extractYouTubeVideoId(input: string): string {
  if (!input) return '';

  const trimmed = input.trim();

  const patterns = [
    /(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([a-zA-Z0-9_-]{11})/,
    /^([a-zA-Z0-9_-]{11})$/, // Just the ID itself
  ];

  for (const pattern of patterns) {
    const match = trimmed.match(pattern);
    if (match && match[1]) {
      return match[1];
    }
  }

  // Return as-is if no pattern matched (let backend validate)
  return trimmed;
}

/**
 * Extract Vimeo video ID from various URL formats or return the ID if already extracted.
 * Supports:
 * - https://vimeo.com/VIDEO_ID
 * - https://vimeo.com/channels/name/VIDEO_ID
 * - https://player.vimeo.com/video/VIDEO_ID
 * - VIDEO_ID (already extracted, numeric)
 */
export function extractVimeoVideoId(input: string): string {
  if (!input) return '';

  const trimmed = input.trim();

  const patterns = [
    /player\.vimeo\.com\/video\/(\d+)/,
    /vimeo\.com\/(?:[a-zA-Z]+\/[^/]+\/)?(\d+)/,
    /^(\d+)$/, // Just the ID itself
  ];

  for (const pattern of patterns) {
    const match = trimmed.match(pattern);
    if (match && match[1]) {
      return match[1];
    }
  }

  // Return as-is if no pattern matched (let backend validate)
  return trimmed;
}

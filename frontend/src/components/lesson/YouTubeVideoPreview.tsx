import { extractYouTubeVideoId } from '@/lib/video';
import { AlertCircle, CheckCircle2 } from 'lucide-react';

interface YouTubeVideoPreviewProps {
  /** Raw instructor input — URL or bare video ID. */
  input: string;
}

/**
 * Inline feedback under the video URL field: thumbnail + parsed ID when the
 * input parses, a prominent error when it doesn't. Renders nothing while the
 * field is empty.
 */
export function YouTubeVideoPreview({ input }: YouTubeVideoPreviewProps) {
  const trimmed = input.trim();
  if (!trimmed) return null;

  const videoId = extractYouTubeVideoId(trimmed);

  if (!videoId) {
    return (
      <div
        role="alert"
        className="flex items-start gap-3 bg-destructive/10 border-2 border-destructive/40 text-destructive rounded-md px-4 py-3"
      >
        <AlertCircle className="h-5 w-5 mt-0.5 shrink-0" />
        <div>
          <p className="font-semibold">Not a valid YouTube link</p>
          <p className="text-sm mt-1">
            Paste a YouTube URL (watch, youtu.be, Shorts, live, or embed) or an
            11-character video ID. This value cannot be saved.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-4 border-2 border-green-600/40 bg-green-600/5 rounded-md p-3">
      <img
        src={`https://i.ytimg.com/vi/${videoId}/hqdefault.jpg`}
        alt="YouTube video thumbnail"
        className="h-20 w-auto rounded max-w-full"
      />
      <div className="min-w-0">
        <p className="flex items-center gap-2 font-semibold text-green-700 dark:text-green-500">
          <CheckCircle2 className="h-5 w-5 shrink-0" />
          Video found
        </p>
        <p className="text-sm text-muted-foreground mt-1">
          Video ID: <code className="font-mono">{videoId}</code>
        </p>
      </div>
    </div>
  );
}

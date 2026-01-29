import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Card, CardContent } from '@/components/ui/Card';
import { VideoPlayer } from '@/components/video/VideoPlayer';
import type { LessonSection } from '@/types';

interface SectionContentProps {
  section: LessonSection;
  onVideoProgress?: (position: number, duration: number) => void;
  onVideoEnded?: () => void;
  initialVideoPosition?: number;
}

export function SectionContent({
  section,
  onVideoProgress,
  onVideoEnded,
  initialVideoPosition = 0,
}: SectionContentProps) {
  const hasVideo = section.video_type !== 'none' && section.video_id;
  const hasContent = section.content && section.content.trim().length > 0;

  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-right-4 duration-300">
      {/* Section title */}
      {section.title && (
        <h3 className="text-xl font-semibold">{section.title}</h3>
      )}

      {/* Video player */}
      {hasVideo && section.video_type === 'youtube' && (
        <div className="mb-6">
          <VideoPlayer
            videoType="youtube"
            videoId={section.video_id}
            initialPosition={initialVideoPosition}
            onProgress={onVideoProgress}
            onEnded={onVideoEnded}
          />
        </div>
      )}

      {/* Markdown content */}
      {hasContent && (
        <Card>
          <CardContent className="prose prose-neutral dark:prose-invert max-w-none py-6">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {section.content}
            </ReactMarkdown>
          </CardContent>
        </Card>
      )}

      {/* Empty state */}
      {!hasVideo && !hasContent && (
        <Card>
          <CardContent className="py-12 text-center text-muted-foreground">
            No content available for this section.
          </CardContent>
        </Card>
      )}
    </div>
  );
}

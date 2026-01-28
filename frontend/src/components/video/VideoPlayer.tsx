import { YouTubePlayer } from './YouTubePlayer';

interface VideoPlayerProps {
  videoType: 'youtube' | 'none';
  videoId: string;
  initialPosition?: number;
  onProgress?: (position: number, duration: number) => void;
  onEnded?: () => void;
}

export function VideoPlayer({
  videoType,
  videoId,
  initialPosition = 0,
  onProgress,
  onEnded,
}: VideoPlayerProps) {
  if (videoType === 'youtube') {
    return (
      <YouTubePlayer
        videoId={videoId}
        initialPosition={initialPosition}
        onProgress={onProgress}
        onEnded={onEnded}
      />
    );
  }

  return null;
}

export { YouTubePlayer } from './YouTubePlayer';

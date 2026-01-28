import { useEffect, useRef, useCallback } from 'react';

// YouTube IFrame API types
declare global {
  interface Window {
    YT: {
      Player: new (
        elementId: string,
        config: {
          videoId: string;
          width?: string | number;
          height?: string | number;
          playerVars?: Record<string, number | string>;
          events?: {
            onReady?: (event: { target: YTPlayer }) => void;
            onStateChange?: (event: { data: number; target: YTPlayer }) => void;
          };
        }
      ) => YTPlayer;
      PlayerState: {
        ENDED: number;
        PLAYING: number;
        PAUSED: number;
        BUFFERING: number;
        CUED: number;
      };
    };
    onYouTubeIframeAPIReady?: () => void;
  }
}

interface YTPlayer {
  getCurrentTime: () => number;
  getDuration: () => number;
  seekTo: (seconds: number, allowSeekAhead?: boolean) => void;
  playVideo: () => void;
  pauseVideo: () => void;
  destroy: () => void;
}

interface YouTubePlayerProps {
  videoId: string;
  initialPosition?: number;
  onProgress?: (position: number, duration: number) => void;
  onEnded?: () => void;
}

let isAPILoaded = false;
let isAPILoading = false;
const apiLoadCallbacks: (() => void)[] = [];

function loadYouTubeAPI(): Promise<void> {
  return new Promise((resolve) => {
    if (isAPILoaded) {
      resolve();
      return;
    }

    apiLoadCallbacks.push(resolve);

    if (isAPILoading) {
      return;
    }

    isAPILoading = true;

    const tag = document.createElement('script');
    tag.src = 'https://www.youtube.com/iframe_api';
    const firstScriptTag = document.getElementsByTagName('script')[0];
    firstScriptTag.parentNode?.insertBefore(tag, firstScriptTag);

    window.onYouTubeIframeAPIReady = () => {
      isAPILoaded = true;
      isAPILoading = false;
      apiLoadCallbacks.forEach((cb) => cb());
      apiLoadCallbacks.length = 0;
    };
  });
}

export function YouTubePlayer({
  videoId,
  initialPosition = 0,
  onProgress,
  onEnded,
}: YouTubePlayerProps) {
  const playerRef = useRef<YTPlayer | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const progressIntervalRef = useRef<number | null>(null);
  const playerIdRef = useRef(`youtube-player-${Date.now()}`);

  const startProgressTracking = useCallback(() => {
    if (progressIntervalRef.current) {
      clearInterval(progressIntervalRef.current);
    }

    progressIntervalRef.current = window.setInterval(() => {
      if (playerRef.current && onProgress) {
        try {
          const currentTime = playerRef.current.getCurrentTime();
          const duration = playerRef.current.getDuration();
          if (duration > 0) {
            onProgress(currentTime, duration);
          }
        } catch {
          // Player might be destroyed
        }
      }
    }, 10000); // Every 10 seconds as per plan
  }, [onProgress]);

  const stopProgressTracking = useCallback(() => {
    if (progressIntervalRef.current) {
      clearInterval(progressIntervalRef.current);
      progressIntervalRef.current = null;
    }
  }, []);

  useEffect(() => {
    let mounted = true;

    async function initPlayer() {
      await loadYouTubeAPI();

      if (!mounted || !containerRef.current) return;

      // Create a div for the player
      const playerDiv = document.createElement('div');
      playerDiv.id = playerIdRef.current;
      containerRef.current.innerHTML = '';
      containerRef.current.appendChild(playerDiv);

      playerRef.current = new window.YT.Player(playerIdRef.current, {
        videoId,
        width: '100%',
        height: '100%',
        playerVars: {
          autoplay: 0,
          modestbranding: 1,
          rel: 0,
          start: Math.floor(initialPosition),
        },
        events: {
          onReady: (event) => {
            // Seek to initial position if provided
            if (initialPosition > 0) {
              event.target.seekTo(initialPosition, true);
            }
          },
          onStateChange: (event) => {
            if (event.data === window.YT.PlayerState.PLAYING) {
              startProgressTracking();
            } else if (
              event.data === window.YT.PlayerState.PAUSED ||
              event.data === window.YT.PlayerState.ENDED
            ) {
              stopProgressTracking();

              // Save progress on pause/end
              if (onProgress && playerRef.current) {
                try {
                  const currentTime = playerRef.current.getCurrentTime();
                  const duration = playerRef.current.getDuration();
                  if (duration > 0) {
                    onProgress(currentTime, duration);
                  }
                } catch {
                  // Ignore
                }
              }

              if (event.data === window.YT.PlayerState.ENDED && onEnded) {
                onEnded();
              }
            }
          },
        },
      });
    }

    initPlayer();

    return () => {
      mounted = false;
      stopProgressTracking();
      if (playerRef.current) {
        try {
          playerRef.current.destroy();
        } catch {
          // Ignore destruction errors
        }
        playerRef.current = null;
      }
    };
  }, [videoId, initialPosition, onProgress, onEnded, startProgressTracking, stopProgressTracking]);

  return (
    <div
      ref={containerRef}
      className="aspect-video bg-black rounded-lg overflow-hidden [&>div]:w-full [&>div]:h-full [&_iframe]:w-full [&_iframe]:h-full"
    />
  );
}

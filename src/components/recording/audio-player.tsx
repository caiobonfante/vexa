"use client";

import { useRef, useState, useEffect, useCallback, forwardRef, useImperativeHandle } from "react";
import { Play, Pause, Volume2, VolumeX, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export interface AudioPlayerHandle {
  seekTo: (time: number) => void;
}

interface AudioPlayerProps {
  src: string;
  onTimeUpdate?: (currentTime: number) => void;
  className?: string;
  compact?: boolean;
}

function formatTime(seconds: number): string {
  if (!isFinite(seconds) || seconds < 0) return "0:00";
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, "0")}`;
}

export const AudioPlayer = forwardRef<AudioPlayerHandle, AudioPlayerProps>(
  function AudioPlayer({ src, onTimeUpdate, className, compact = false }, ref) {
    const audioRef = useRef<HTMLAudioElement>(null);
    const retryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const [isPlaying, setIsPlaying] = useState(false);
    const [isLoading, setIsLoading] = useState(true);
    const [currentTime, setCurrentTime] = useState(0);
    const [duration, setDuration] = useState(0);
    const [isMuted, setIsMuted] = useState(false);
    const [errorCount, setErrorCount] = useState(0);

    // Expose seekTo to parent via ref
    useImperativeHandle(ref, () => ({
      seekTo(time: number) {
        const audio = audioRef.current;
        if (!audio) return;
        audio.currentTime = time;
        setCurrentTime(time);
        // Auto-play when seeking from transcript click
        if (audio.paused) {
          audio.play().catch(() => {});
        }
      },
    }), []);

    useEffect(() => {
      const audio = audioRef.current;
      if (!audio) return;

      const handleTimeUpdate = () => {
        const time = audio.currentTime;
        setCurrentTime(time);
        onTimeUpdate?.(time);
      };

      const handleLoadedMetadata = () => {
        setDuration(audio.duration);
        setIsLoading(false);
      };

      const handleCanPlay = () => {
        setIsLoading(false);
        setErrorCount(0);
      };
      const handleWaiting = () => setIsLoading(true);
      const handlePlaying = () => { setIsLoading(false); setIsPlaying(true); };
      const handlePause = () => setIsPlaying(false);
      const handleEnded = () => setIsPlaying(false);
      const handleError = () => {
        setIsPlaying(false);
        setIsLoading(true);
        setErrorCount((count) => count + 1);
        if (retryTimerRef.current) {
          clearTimeout(retryTimerRef.current);
        }
        // Recording can take a moment to become streamable after stop. Retry automatically.
        retryTimerRef.current = setTimeout(() => {
          audio.load();
        }, 1500);
      };

      audio.addEventListener("timeupdate", handleTimeUpdate);
      audio.addEventListener("loadedmetadata", handleLoadedMetadata);
      audio.addEventListener("canplay", handleCanPlay);
      audio.addEventListener("waiting", handleWaiting);
      audio.addEventListener("playing", handlePlaying);
      audio.addEventListener("pause", handlePause);
      audio.addEventListener("ended", handleEnded);
      audio.addEventListener("error", handleError);

      return () => {
        if (retryTimerRef.current) {
          clearTimeout(retryTimerRef.current);
          retryTimerRef.current = null;
        }
        audio.removeEventListener("timeupdate", handleTimeUpdate);
        audio.removeEventListener("loadedmetadata", handleLoadedMetadata);
        audio.removeEventListener("canplay", handleCanPlay);
        audio.removeEventListener("waiting", handleWaiting);
        audio.removeEventListener("playing", handlePlaying);
        audio.removeEventListener("pause", handlePause);
        audio.removeEventListener("ended", handleEnded);
        audio.removeEventListener("error", handleError);
      };
    }, [onTimeUpdate]);

    const togglePlay = useCallback(() => {
      const audio = audioRef.current;
      if (!audio) return;
      if (isPlaying) {
        audio.pause();
      } else {
        audio.play().catch(() => {
          setErrorCount((count) => count + 1);
        });
      }
    }, [isPlaying]);

    const toggleMute = useCallback(() => {
      const audio = audioRef.current;
      if (!audio) return;
      audio.muted = !audio.muted;
      setIsMuted(!isMuted);
    }, [isMuted]);

    const handleSeekBarChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
      const time = parseFloat(e.target.value);
      const audio = audioRef.current;
      if (audio) {
        audio.currentTime = time;
        setCurrentTime(time);
      }
    }, []);

    const progress = duration > 0 ? (currentTime / duration) * 100 : 0;

    return (
      <div
        className={cn(
          "flex items-center bg-muted/50 rounded-lg border",
          compact ? "gap-1.5 px-2 py-1" : "gap-3 px-4 py-2",
          className
        )}
      >
        <audio ref={audioRef} src={src} preload="metadata" />

        {/* Play/Pause */}
        <Button
          variant="ghost"
          size="icon"
          className={cn("shrink-0", compact ? "h-6 w-6" : "h-8 w-8")}
          onClick={togglePlay}
          disabled={isLoading && !isPlaying}
        >
          {isLoading && !isPlaying ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : isPlaying ? (
            <Pause className="h-4 w-4" />
          ) : (
            <Play className="h-4 w-4" />
          )}
        </Button>

        {/* Current time */}
        <span className={cn("text-xs text-muted-foreground tabular-nums text-right shrink-0", compact ? "w-8" : "w-10")}>
          {formatTime(currentTime)}
        </span>

        {/* Seek bar */}
        <div className={cn("relative flex-1 flex items-center", compact ? "h-6" : "h-8")}>
          <div className="absolute inset-x-0 h-1.5 bg-muted rounded-full overflow-hidden">
            <div
              className="h-full bg-primary rounded-full transition-[width] duration-75"
              style={{ width: `${progress}%` }}
            />
          </div>
          <input
            type="range"
            min={0}
            max={duration || 0}
            step={0.1}
            value={currentTime}
            onChange={handleSeekBarChange}
            className={cn("absolute inset-x-0 w-full opacity-0 cursor-pointer", compact ? "h-6" : "h-8")}
          />
        </div>

        {/* Duration */}
        <span className={cn("text-xs text-muted-foreground tabular-nums shrink-0", compact ? "w-8" : "w-10")}>
          {formatTime(duration)}
        </span>

        {/* Mute */}
        <Button
          variant="ghost"
          size="icon"
          className={cn("shrink-0", compact ? "h-6 w-6" : "h-8 w-8")}
          onClick={toggleMute}
        >
          {isMuted ? (
            <VolumeX className="h-4 w-4" />
          ) : (
            <Volume2 className="h-4 w-4" />
          )}
        </Button>

        {isLoading && errorCount > 0 && (
          <span className="text-xs text-muted-foreground whitespace-nowrap">
            Preparing audio...
          </span>
        )}
      </div>
    );
  }
);

"use client";

import { useEffect, useRef, useCallback, useState } from "react";
import type {
  Platform,
  WebSocketIncomingMessage,
  MeetingStatus,
  TranscriptSegment,
  WebSocketSegment,
} from "@/types/vexa";
import { useMeetingsStore } from "@/stores/meetings-store";
import { vexaAPI } from "@/lib/api";

interface UseLiveTranscriptsOptions {
  platform: Platform;
  nativeId: string;
  meetingId: string;
  isActive: boolean;
  onStatusChange?: (status: MeetingStatus) => void;
}

interface UseLiveTranscriptsReturn {
  isConnecting: boolean;
  isConnected: boolean;
  connectionError: string | null;
  reconnectAttempts: number;
}

// Configuration
const PING_INTERVAL = 25000; // 25 seconds
const INITIAL_RECONNECT_DELAY = 1000; // 1 second
const MAX_RECONNECT_DELAY = 30000; // 30 seconds
const MAX_RECONNECT_ATTEMPTS = 10;

/**
 * Hook for managing live transcript updates via WebSocket.
 * Implements the algorithm from ws_realtime_transcription.py:
 * 1. Bootstrap from REST API (seed in-memory map by absolute_start_time)
 * 2. Connect to WebSocket and subscribe to meeting
 * 3. Process transcript.mutable and transcript.finalized events
 * 4. Deduplicate by absolute_start_time (keep newer updated_at)
 */
export function useLiveTranscripts(
  options: UseLiveTranscriptsOptions
): UseLiveTranscriptsReturn {
  const { platform, nativeId, meetingId, isActive, onStatusChange } = options;

  // Connection state
  const [isConnecting, setIsConnecting] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const [reconnectAttempts, setReconnectAttempts] = useState(0);

  // Refs for cleanup and internal state
  const wsRef = useRef<WebSocket | null>(null);
  const pingIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const shouldReconnectRef = useRef(true);
  const mountedRef = useRef(true);
  const reconnectAttemptsRef = useRef(0);
  const bootstrappedRef = useRef(false);

  // Store refs for stable callbacks
  const onStatusChangeRef = useRef(onStatusChange);
  onStatusChangeRef.current = onStatusChange;

  // Store actions (stable references from Zustand)
  const bootstrapTranscripts = useMeetingsStore((state) => state.bootstrapTranscripts);
  const upsertTranscriptSegments = useMeetingsStore((state) => state.upsertTranscriptSegments);
  const updateMeetingStatus = useMeetingsStore((state) => state.updateMeetingStatus);

  // Convert WebSocket segment to TranscriptSegment format
  const convertWebSocketSegment = useCallback(
    (seg: WebSocketSegment): TranscriptSegment => ({
      id: seg.absolute_start_time, // Use timestamp as unique ID
      meeting_id: nativeId,
      start_time: seg.start || 0,
      end_time: seg.end_time || 0,
      absolute_start_time: seg.absolute_start_time,
      absolute_end_time: seg.absolute_end_time,
      text: seg.text,
      speaker: seg.speaker || "Unknown",
      language: seg.language || "en",
      session_uid: seg.session_uid || "",
      created_at: seg.absolute_start_time,
      updated_at: seg.updated_at,
    }),
    [nativeId]
  );

  // Step 1: Bootstrap from REST API
  const bootstrapFromRest = useCallback(async () => {
    if (bootstrappedRef.current) return;

    try {
      console.log(`[LiveTranscripts] Bootstrapping from REST API: ${platform}/${nativeId}`);
      const segments = await vexaAPI.getTranscripts(platform, nativeId);
      console.log(`[LiveTranscripts] Bootstrapped ${segments.length} segments from REST API`);
      
      // Bootstrap the transcript map (algorithm step 1)
      bootstrapTranscripts(segments);
      bootstrappedRef.current = true;
    } catch (error) {
      console.error("[LiveTranscripts] Bootstrap from REST API failed:", error);
      // Continue anyway - WebSocket will provide segments
      bootstrappedRef.current = true;
    }
  }, [platform, nativeId, bootstrapTranscripts]);

  // Calculate reconnect delay with exponential backoff
  const getReconnectDelay = useCallback((attempt: number) => {
    const delay = Math.min(
      INITIAL_RECONNECT_DELAY * Math.pow(2, attempt),
      MAX_RECONNECT_DELAY
    );
    // Add jitter (±20%)
    const jitter = delay * 0.2 * (Math.random() - 0.5);
    return Math.round(delay + jitter);
  }, []);

  // Cleanup all intervals and connections
  const cleanup = useCallback(() => {
    if (pingIntervalRef.current) {
      clearInterval(pingIntervalRef.current);
      pingIntervalRef.current = null;
    }
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    if (wsRef.current) {
      wsRef.current.close(1000, "Cleanup");
      wsRef.current = null;
    }
  }, []);

  // WebSocket connection function
  const connect = useCallback(async () => {
    if (!mountedRef.current || !shouldReconnectRef.current) return;
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    // Clean up any existing connection
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    if (pingIntervalRef.current) {
      clearInterval(pingIntervalRef.current);
      pingIntervalRef.current = null;
    }

    setIsConnecting(true);
    setConnectionError(null);

    // Fetch WebSocket URL and auth token from runtime config API
    let wsUrl: string;
    let authToken: string | null = null;
    try {
      const configResponse = await fetch("/api/config");
      const config = await configResponse.json();
      wsUrl = config.wsUrl;
      authToken = config.authToken;
    } catch {
      // Fallback to default (runtime config should always be available)
      wsUrl = "ws://localhost:18056/ws";
    }

    // Append auth token as query parameter if available
    // Vexa uses X-API-Key header for REST, but browsers can't set WS headers
    // So we pass it as api_key query parameter
    if (authToken) {
      const separator = wsUrl.includes("?") ? "&" : "?";
      wsUrl = `${wsUrl}${separator}api_key=${encodeURIComponent(authToken)}`;
    }
    console.log("[LiveTranscripts] Connecting to:", wsUrl.replace(/api_key=([^&]+)/, "api_key=***"));

    try {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        if (!mountedRef.current) return;

        console.log("[LiveTranscripts] Connected");
        setIsConnecting(false);
        setIsConnected(true);
        setReconnectAttempts(0);
        reconnectAttemptsRef.current = 0;
        setConnectionError(null);

        // Step 3: Subscribe to meeting for live transcript updates
        ws.send(
          JSON.stringify({
            action: "subscribe",
            meetings: [{ platform, native_id: nativeId }],
          })
        );

        // Start ping interval for keepalive
        pingIntervalRef.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ action: "ping" }));
          }
        }, PING_INTERVAL);
      };

      ws.onmessage = (event) => {
        if (!mountedRef.current) return;

        try {
          const message: WebSocketIncomingMessage = JSON.parse(event.data);

          switch (message.type) {
            case "transcript.mutable":
            case "transcript.finalized":
              // Step 4: Process transcript events (mutable and finalized)
              // Deduplication by absolute_start_time is handled in upsertTranscriptSegments
              if (message.payload?.segments) {
                const segments: TranscriptSegment[] = [];
                for (const seg of message.payload.segments) {
                  // Skip empty segments or those missing required fields
                  if (!seg.text?.trim() || !seg.absolute_start_time) continue;

                  // Convert WebSocket segment to TranscriptSegment format
                  segments.push(convertWebSocketSegment(seg));
                }

                if (segments.length > 0) {
                  upsertTranscriptSegments(segments);
                  console.log(
                    `[LiveTranscripts] ${message.type}: ${segments.length} segments processed`
                  );
                }
              }
              break;

            case "meeting.status":
              // Update meeting status in the store (status is in payload)
              const status = message.payload?.status;
              if (status) {
                updateMeetingStatus(meetingId, status);
                onStatusChangeRef.current?.(status);

                // If meeting ended, disconnect WebSocket
                if (status === "completed" || status === "failed") {
                  console.log("[LiveTranscripts] Meeting ended, disconnecting");
                  shouldReconnectRef.current = false;
                  ws.close(1000, "Meeting ended");
                }
              }
              break;

            case "subscribed":
              console.log("[LiveTranscripts] Successfully subscribed to meeting", message.meetings);
              break;

            case "pong":
              // Keepalive acknowledged - connection is healthy
              break;

            case "error":
              console.error("[LiveTranscripts] Server error:", message.message);
              setConnectionError(message.message);
              break;
          }
        } catch (error) {
          console.error("[LiveTranscripts] Failed to parse message:", error);
        }
      };

      ws.onerror = (event) => {
        if (!mountedRef.current) return;
        
        // WebSocket error events don't provide much detail, but we can check the readyState
        const readyState = ws.readyState;
        const readyStateText = 
          readyState === WebSocket.CONNECTING ? "CONNECTING" :
          readyState === WebSocket.OPEN ? "OPEN" :
          readyState === WebSocket.CLOSING ? "CLOSING" :
          readyState === WebSocket.CLOSED ? "CLOSED" : "UNKNOWN";
        
        const errorDetails = {
          readyState: readyStateText,
          url: wsUrl.replace(/api_key=([^&]+)/, "api_key=***"),
          timestamp: new Date().toISOString(),
        };
        
        console.error("[LiveTranscripts] WebSocket error:", errorDetails, event);
        setConnectionError(`Connection error (${readyStateText})`);
      };

      ws.onclose = (event) => {
        if (!mountedRef.current) return;

        console.log("[LiveTranscripts] Disconnected:", event.code, event.reason);
        setIsConnecting(false);
        setIsConnected(false);

        // Cleanup ping interval
        if (pingIntervalRef.current) {
          clearInterval(pingIntervalRef.current);
          pingIntervalRef.current = null;
        }

        // Auto-reconnect if not intentionally closed
        if (shouldReconnectRef.current && event.code !== 1000) {
          reconnectAttemptsRef.current += 1;
          const attempts = reconnectAttemptsRef.current;
          setReconnectAttempts(attempts);

          if (attempts <= MAX_RECONNECT_ATTEMPTS) {
            const delay = getReconnectDelay(attempts);
            console.log(`[LiveTranscripts] Reconnecting in ${delay}ms (attempt ${attempts}/${MAX_RECONNECT_ATTEMPTS})`);

            reconnectTimeoutRef.current = setTimeout(() => {
              if (mountedRef.current && shouldReconnectRef.current) {
                connect();
              }
            }, delay);
          } else {
            console.log("[LiveTranscripts] Max reconnect attempts reached");
            setConnectionError("Connection lost. Max reconnect attempts reached.");
          }
        }
      };
    } catch (error) {
      console.error("[LiveTranscripts] Failed to create WebSocket:", error);
      if (!mountedRef.current) return;

      setIsConnecting(false);
      setConnectionError((error as Error).message);
    }
  }, [
    platform,
    nativeId,
    meetingId,
    convertWebSocketSegment,
    upsertTranscriptSegments,
    updateMeetingStatus,
    getReconnectDelay,
    cleanup,
  ]);

  // Main connection effect
  useEffect(() => {
    if (!isActive || !platform || !nativeId) {
      // Clean up and reset when not active
      shouldReconnectRef.current = false;
      cleanup();
      setIsConnecting(false);
      setIsConnected(false);
      setReconnectAttempts(0);
      reconnectAttemptsRef.current = 0;
      bootstrappedRef.current = false;
      return;
    }

    mountedRef.current = true;
    shouldReconnectRef.current = true;
    reconnectAttemptsRef.current = 0;
    setReconnectAttempts(0);

    // Step 1: Bootstrap from REST API first
    bootstrapFromRest().then(() => {
      // Step 2: Connect to WebSocket after bootstrap
      connect();
    });

    // Cleanup on unmount or when dependencies change
    return () => {
      mountedRef.current = false;
      shouldReconnectRef.current = false;
      cleanup();
      setIsConnecting(false);
      setIsConnected(false);
    };
  }, [isActive, platform, nativeId, bootstrapFromRest, connect, cleanup]);

  return {
    isConnecting,
    isConnected,
    connectionError,
    reconnectAttempts,
  };
}

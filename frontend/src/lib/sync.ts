import { useEffect, useCallback, useRef } from "react";

export const SyncEvent = {
  NOVELS_CHANGED: "NOVELS_CHANGED",
  DOWNLOAD_STARTED: "DOWNLOAD_STARTED",
  DOWNLOAD_PROGRESS: "DOWNLOAD_PROGRESS",
  DOWNLOAD_COMPLETED: "DOWNLOAD_COMPLETED",
  DOWNLOAD_FAILED: "DOWNLOAD_FAILED",
} as const;

export type SyncEventType = (typeof SyncEvent)[keyof typeof SyncEvent];

export type SyncPayload = Record<string, unknown>;

interface Message { type: SyncEventType; payload: SyncPayload; timestamp: number; }

const CHANNEL = "novelreader-sync";
let _channel: BroadcastChannel | null = null;

function channel(): BroadcastChannel {
  if (!_channel) _channel = new BroadcastChannel(CHANNEL);
  return _channel;
}

type Listener = (type: SyncEventType, payload: SyncPayload) => void;

export function useCrossTab(listener: Listener) {
  const listenerRef = useRef(listener);
  listenerRef.current = listener;

  const broadcast = useCallback((type: SyncEventType, payload: SyncPayload = {}) => {
    channel().postMessage({ type, payload, timestamp: Date.now() } satisfies Message);
  }, []);

  useEffect(() => {
    const ch = channel();
    const handler = (e: MessageEvent<Message>) => listenerRef.current(e.data.type, e.data.payload);
    ch.addEventListener("message", handler);
    return () => ch.removeEventListener("message", handler);
  }, []);

  return broadcast;
}

import { useCallback, useEffect, useRef, useState } from 'react';
import { ApiError } from '../api/client';
import { timingApi } from '../api/timing';
import type { RecordIn } from '../api/types';
import { readStorage, writeStorage } from './useLocalStorage';

export interface QueuedCapture extends RecordIn {
  event_id: string;
  status: 'pending' | 'synced';
  synced_at?: string;
}

const MAX_KEPT = 300;
const BATCH = 100;
const SYNC_INTERVAL_MS = 5000;

function storageKey(slug: string) {
  return `bibby_timing_queue_${slug}`;
}

function makeDedupKey(label: string): string {
  const safe = label.replace(/[^A-Za-z0-9_-]+/g, '-').slice(0, 40) || 'web';
  const uuid =
    typeof crypto.randomUUID === 'function'
      ? crypto.randomUUID()
      : `${Date.now().toString(16)}-${Math.random().toString(16).slice(2)}`;
  return `${safe}-${uuid}`;
}

interface Options {
  slug: string;
  deviceToken: string | null;
  /** Label used as dedup-key prefix (device label or 'web'). */
  label: string;
  online: boolean;
}

/**
 * Persistent (localStorage) capture queue with a background sync loop.
 * Re-sending records is idempotent on the server (dedup_key), so retries are safe.
 */
export function useTimingQueue({ slug, deviceToken, label, online }: Options) {
  const [items, setItems] = useState<QueuedCapture[]>(() => readStorage<QueuedCapture[]>(storageKey(slug), []));
  const [syncing, setSyncing] = useState(false);
  const [lastError, setLastError] = useState<string | null>(null);
  const [lastSyncAt, setLastSyncAt] = useState<string | null>(null);
  const itemsRef = useRef(items);
  itemsRef.current = items;
  const syncingRef = useRef(false);

  const persist = useCallback(
    (updater: (prev: QueuedCapture[]) => QueuedCapture[]) => {
      setItems((prev) => {
        const next = updater(prev);
        // keep all pending + the most recent synced ones
        const pending = next.filter((i) => i.status === 'pending');
        const synced = next.filter((i) => i.status === 'synced').slice(-MAX_KEPT);
        const merged = [...pending, ...synced].sort((a, b) => a.absolute_time.localeCompare(b.absolute_time));
        writeStorage(storageKey(slug), merged);
        return merged;
      });
    },
    [slug],
  );

  const capture = useCallback(
    (eventId: string, bib: number) => {
      const rec: QueuedCapture = {
        event_id: eventId,
        bib_number: bib,
        absolute_time: new Date().toISOString(),
        dedup_key: makeDedupKey(label),
        status: 'pending',
      };
      persist((prev) => [...prev, rec]);
      return rec;
    },
    [label, persist],
  );

  const sync = useCallback(async () => {
    if (syncingRef.current) return;
    const pending = itemsRef.current.filter((i) => i.status === 'pending');
    if (pending.length === 0) return;
    syncingRef.current = true;
    setSyncing(true);
    setLastError(null);
    try {
      const byEvent = new Map<string, QueuedCapture[]>();
      for (const p of pending) {
        const list = byEvent.get(p.event_id) ?? [];
        list.push(p);
        byEvent.set(p.event_id, list);
      }
      for (const [eventId, list] of byEvent) {
        for (let i = 0; i < list.length; i += BATCH) {
          const chunk = list.slice(i, i + BATCH);
          await timingApi.upload(
            slug,
            eventId,
            chunk.map(({ bib_number, absolute_time, dedup_key }) => ({ bib_number, absolute_time, dedup_key })),
            deviceToken,
          );
          const keys = new Set(chunk.map((c) => c.dedup_key));
          const now = new Date().toISOString();
          persist((prev) =>
            prev.map((p) => (keys.has(p.dedup_key) ? { ...p, status: 'synced', synced_at: now } : p)),
          );
        }
      }
      setLastSyncAt(new Date().toISOString());
    } catch (err) {
      if (err instanceof ApiError) {
        setLastError(err.detail);
      } else {
        setLastError('Übertragung fehlgeschlagen.');
      }
    } finally {
      syncingRef.current = false;
      setSyncing(false);
    }
  }, [slug, deviceToken, persist]);

  // Background loop: try every few seconds while online and something is pending.
  useEffect(() => {
    if (!online) return;
    const id = window.setInterval(() => {
      if (itemsRef.current.some((i) => i.status === 'pending')) void sync();
    }, SYNC_INTERVAL_MS);
    void sync();
    return () => window.clearInterval(id);
  }, [online, sync]);

  const pendingCount = items.filter((i) => i.status === 'pending').length;
  const recent = [...items].sort((a, b) => b.absolute_time.localeCompare(a.absolute_time)).slice(0, 10);

  return { items, recent, pendingCount, capture, sync, syncing, lastError, lastSyncAt };
}

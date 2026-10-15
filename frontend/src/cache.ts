import type { ChatSession } from "./api";

// Local copy of server data, so revisits can skip requests that were already answered.
// Every key is scoped to a user id, and sign-out removes them all. Storage can be blocked or full,
// so each access is wrapped: a failure only means the next load asks the server again.
const PREFIX = "ai-chat.cache.";
const ENTRY_VERSION = 1;
// Sessions hold their full message history, so only the most recently saved ones are kept
const MAX_CACHED_SESSIONS = 30;

const HOUR_MS = 60 * 60 * 1000;
const DAY_MS = 24 * HOUR_MS;

// How long a cached value is used without asking the server again
export const FRESH_FOR_MS = {
  models: HOUR_MS,
  tools: DAY_MS,
  limits: DAY_MS,
} as const;

type Entry<T> = { v: number; savedAt: number; data: T };

export type CachedValue<T> = { data: T; ageMs: number };

function keyFor(userId: string, name: string): string {
  return `${PREFIX}${userId}.${name}`;
}

export function readCache<T>(userId: string, name: string): CachedValue<T> | null {
  try {
    const entry = JSON.parse(window.localStorage.getItem(keyFor(userId, name)) ?? "null") as Entry<T> | null;
    if (entry?.v !== ENTRY_VERSION) {
      return null;
    }
    return { data: entry.data, ageMs: Date.now() - entry.savedAt };
  } catch {
    // Storage can be blocked, or hold something unreadable
    return null;
  }
}

export function writeCache<T>(userId: string, name: string, data: T): void {
  try {
    const entry: Entry<T> = { v: ENTRY_VERSION, savedAt: Date.now(), data };
    window.localStorage.setItem(keyFor(userId, name), JSON.stringify(entry));
  } catch {
    // Storage is full or blocked, so the value is simply not kept
  }
}

export function removeCache(userId: string, name: string): void {
  try {
    window.localStorage.removeItem(keyFor(userId, name));
  } catch {
    // Nothing to remove if storage is blocked
  }
}

export function writeSessionCache(userId: string, session: ChatSession): void {
  writeCache(userId, `session.${session.id}`, session);

  // Drops the least recently saved sessions once there are too many
  try {
    const prefix = keyFor(userId, "session.");
    Object.keys(window.localStorage)
      .filter((key) => key.startsWith(prefix))
      .map((key) => ({
        key,
        savedAt: (JSON.parse(window.localStorage.getItem(key) ?? "null") as Entry<unknown> | null)?.savedAt ?? 0,
      }))
      .sort((a, b) => b.savedAt - a.savedAt)
      .slice(MAX_CACHED_SESSIONS)
      .forEach(({ key }) => window.localStorage.removeItem(key));
  } catch {
    // Pruning is best effort. Entries left over are only overwritten or dropped later
  }
}

// Removes every cached value, or every value except one user's when keepUserId is given.
// Sign-out clears everything; signing in keeps only the new user's values.
export function clearCache(keepUserId?: string): void {
  try {
    const keep = keepUserId ? `${PREFIX}${keepUserId}.` : null;
    Object.keys(window.localStorage)
      .filter((key) => key.startsWith(PREFIX) && !(keep && key.startsWith(keep)))
      .forEach((key) => window.localStorage.removeItem(key));
  } catch {
    // Nothing to clear if storage is blocked
  }
}

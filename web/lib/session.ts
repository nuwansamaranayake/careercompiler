/* The session token lives in this browser tab only (sessionStorage) and carries its own
   expiry, so a tab left open drops a dead token before spending a request on a 401. */
import type { Session, StoredSession } from "./types";

export const SESSION_KEY = "cc-session";

/* Treat the last 30 seconds as already expired: a compile takes about that long, and a
   token that dies mid-compile is a worse experience than a fresh session up front. */
const SAFETY_MS = 30_000;

type Store = Pick<Storage, "getItem" | "setItem" | "removeItem">;

export function stamp(session: Session, now: number): StoredSession {
  return { ...session, expires_at: now + session.expires_in * 1000 };
}

export function isLive(session: StoredSession, now: number): boolean {
  return session.expires_at - SAFETY_MS > now;
}

export function saveSession(store: Store, session: StoredSession): void {
  store.setItem(SESSION_KEY, JSON.stringify(session));
}

export function loadSession(store: Store, now: number): StoredSession | null {
  const raw = store.getItem(SESSION_KEY);
  if (!raw) return null;
  try {
    const s = JSON.parse(raw) as StoredSession;
    if (typeof s?.token === "string" && typeof s.expires_at === "number" && isLive(s, now)) return s;
  } catch {
    /* unreadable: fall through and clear it */
  }
  store.removeItem(SESSION_KEY);
  return null;
}

export function clearSession(store: Store): void {
  store.removeItem(SESSION_KEY);
}

export function minutesLeft(session: StoredSession, now: number): number {
  return Math.max(0, Math.ceil((session.expires_at - now) / 60_000));
}

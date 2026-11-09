import { describe, expect, it } from "vitest";
import {
  SESSION_KEY, clearSession, isLive, loadSession, minutesLeft, saveSession, stamp,
} from "./session";
import type { Session } from "./types";

const WIRE: Session = {
  token: "tok", expires_in: 1800, request_budget: 60, synthetic: true,
  candidate_id: 1, candidate_name: "Jordan Alvarez", jobs: [],
};
const T0 = 1_800_000_000_000;

function memoryStore() {
  const data = new Map<string, string>();
  return {
    data,
    getItem: (k: string) => data.get(k) ?? null,
    setItem: (k: string, v: string) => { data.set(k, v); },
    removeItem: (k: string) => { data.delete(k); },
  };
}

describe("session storage", () => {
  it("stamps the wall-clock expiry from expires_in", () => {
    expect(stamp(WIRE, T0).expires_at).toBe(T0 + 1_800_000);
  });

  it("is live until 30 seconds before expiry", () => {
    const s = stamp(WIRE, T0);
    expect(isLive(s, T0)).toBe(true);
    expect(isLive(s, T0 + 1_769_999)).toBe(true);
    expect(isLive(s, T0 + 1_770_000)).toBe(false);
    expect(isLive(s, T0 + 1_800_001)).toBe(false);
  });

  it("round-trips a live session", () => {
    const store = memoryStore();
    const s = stamp(WIRE, T0);
    saveSession(store, s);
    expect(loadSession(store, T0 + 60_000)).toEqual(s);
  });

  it("drops and clears an expired session", () => {
    const store = memoryStore();
    saveSession(store, stamp(WIRE, T0));
    expect(loadSession(store, T0 + 1_800_000)).toBeNull();
    expect(store.data.has(SESSION_KEY)).toBe(false);
  });

  it("drops and clears unreadable or malformed storage", () => {
    const store = memoryStore();
    store.setItem(SESSION_KEY, "{not json");
    expect(loadSession(store, T0)).toBeNull();
    expect(store.data.has(SESSION_KEY)).toBe(false);

    store.setItem(SESSION_KEY, JSON.stringify({ token: 5, expires_at: T0 + 999_999 }));
    expect(loadSession(store, T0)).toBeNull();
    store.setItem(SESSION_KEY, JSON.stringify({ token: "t" }));
    expect(loadSession(store, T0)).toBeNull();
    store.setItem(SESSION_KEY, "null");
    expect(loadSession(store, T0)).toBeNull();
  });

  it("returns null when nothing is stored", () => {
    expect(loadSession(memoryStore(), T0)).toBeNull();
  });

  it("clears on request", () => {
    const store = memoryStore();
    saveSession(store, stamp(WIRE, T0));
    clearSession(store);
    expect(store.data.size).toBe(0);
  });

  it("reports whole minutes left, never negative", () => {
    const s = stamp(WIRE, T0);
    expect(minutesLeft(s, T0)).toBe(30);
    expect(minutesLeft(s, T0 + 1_740_001)).toBe(1);
    expect(minutesLeft(s, T0 + 9_999_999)).toBe(0);
  });
});

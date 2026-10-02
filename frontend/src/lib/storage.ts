// localStorage can throw (private mode, blocked storage); every access is guarded.
export function readStore<T>(key: string, fallback: T): T {
  try {
    const raw = window.localStorage.getItem(key);
    return raw === null ? fallback : (JSON.parse(raw) as T);
  } catch {
    return fallback;
  }
}

export function writeStore(key: string, value: unknown): void {
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* storage unavailable: the preference simply isn't remembered */
  }
}

export function removeStore(key: string): void {
  try {
    window.localStorage.removeItem(key);
  } catch {
    /* ignore */
  }
}

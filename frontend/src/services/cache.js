/**
 * Tiny namespaced localStorage cache with a TTL.
 *
 * The NOC dashboard re-reads the same metrics and log pages constantly, so
 * caching responses on the client keeps the backend load down. Entries are
 * scoped under a single prefix so they can be wiped on sign-out.
 */

const PREFIX = "naap.cache.";
const MAX_ENTRIES = 60;

function isStorageAvailable() {
  try {
    const probe = "__naap_probe__";
    window.localStorage.setItem(probe, "1");
    window.localStorage.removeItem(probe);
    return true;
  } catch {
    return false;
  }
}

const AVAILABLE = typeof window !== "undefined" && isStorageAvailable();

function cacheKeys() {
  const keys = [];
  for (let index = 0; index < window.localStorage.length; index += 1) {
    const key = window.localStorage.key(index);
    if (key && key.startsWith(PREFIX)) keys.push(key);
  }
  return keys;
}

function evictOldest() {
  const keys = cacheKeys();
  if (keys.length < MAX_ENTRIES) return;
  const entries = keys
    .map((key) => {
      try {
        return { key, expiry: JSON.parse(window.localStorage.getItem(key))?.expiry ?? 0 };
      } catch {
        return { key, expiry: 0 };
      }
    })
    .sort((a, b) => a.expiry - b.expiry);
  entries.slice(0, Math.max(1, entries.length - MAX_ENTRIES + 1)).forEach(({ key }) => {
    window.localStorage.removeItem(key);
  });
}

/** Read a cached value, or `null` when missing/expired/corrupt. */
export function readCache(key) {
  if (!AVAILABLE) return null;
  try {
    const raw = window.localStorage.getItem(PREFIX + key);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed.expiry !== "number") return null;
    if (Date.now() > parsed.expiry) {
      window.localStorage.removeItem(PREFIX + key);
      return null;
    }
    return parsed.value;
  } catch {
    return null;
  }
}

/** Store a value with a TTL in milliseconds. */
export function writeCache(key, value, ttlMs = 120000) {
  if (!AVAILABLE) return;
  try {
    evictOldest();
    window.localStorage.setItem(PREFIX + key, JSON.stringify({ value, expiry: Date.now() + ttlMs }));
  } catch {
    /* Quota exceeded — caching is best-effort. */
  }
}

/** Drop every cached response (called on sign-out so users never share data). */
export function clearCache() {
  if (!AVAILABLE) return;
  cacheKeys().forEach((key) => window.localStorage.removeItem(key));
}

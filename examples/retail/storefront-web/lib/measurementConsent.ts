/** A preference, not a user identifier. No optional storage is accessed here. */
export type MeasurementChoice = "unknown" | "granted" | "denied";
export const MEASUREMENT_PREFERENCE_KEY = "dufynd_measurement_preference_v1";
export const MEASUREMENT_PROTOCOL = "granted-v1";
export const PREFERENCE_LIFETIME_MS = 180 * 24 * 60 * 60 * 1000;
type Preference = { version: 1; choice: "granted" | "denied"; savedAt: number };
const listeners = new Set<() => void>();
let current: Preference | null = null;
let initialized = false;
let memoryOnly = false;
let generation = 0;
let notifying = false;
let installed = false;

function validPreference(raw: string | null): Preference | null {
  if (!raw) return null;
  try {
    const value = JSON.parse(raw) as Partial<Preference>;
    if (value.version !== 1 || !["granted", "denied"].includes(value.choice || "") ||
        typeof value.savedAt !== "number" || !Number.isFinite(value.savedAt) ||
        value.savedAt > Date.now() || Date.now() - value.savedAt >= PREFERENCE_LIFETIME_MS) return null;
    return { version: 1, choice: value.choice as Preference["choice"], savedAt: value.savedAt };
  } catch { return null; }
}
function synchronize(next: Preference | null): void {
  const changed = !initialized || current?.choice !== next?.choice || current?.savedAt !== next?.savedAt;
  current = next; initialized = true;
  if (!changed) return;
  generation += 1;
  if (notifying) return;
  notifying = true;
  try {
    for (const notify of [...listeners]) {
      try { notify(); } catch { /* A presentation listener must not block other privacy listeners. */ }
    }
  } finally { notifying = false; }
}
function refresh(): void {
  if (typeof window === "undefined") return;
  if (memoryOnly) {
    if (current && Date.now() - current.savedAt >= PREFERENCE_LIFETIME_MS) synchronize(null);
    return;
  }
  try { synchronize(validPreference(window.localStorage.getItem(MEASUREMENT_PREFERENCE_KEY))); }
  catch {
    // A previously persisted permission cannot silently survive inaccessible storage.
    // An explicit new choice may be used in memory for this document only.
    synchronize(null); memoryOnly = true;
  }
}
function install(): void {
  if (installed || typeof window === "undefined") return;
  installed = true;
  window.addEventListener("storage", (event: StorageEvent) => {
    if (event.key !== null && event.key !== MEASUREMENT_PREFERENCE_KEY) return;
    memoryOnly = false; refresh();
  });
  // A choice that could not be persisted is valid only for this document.
  // Revoke it during document teardown so reload/BFCache cannot silently carry
  // an in-memory grant into a fresh page.
  window.addEventListener("pagehide", () => {
    if (memoryOnly) synchronize(null);
  });
  window.addEventListener("pageshow", () => {
    const wasMemoryOnly = memoryOnly;
    memoryOnly = false;
    if (wasMemoryOnly) synchronize(null);
    refresh();
  });
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") refresh();
  });
}
export function measurementChoice(): MeasurementChoice {
  if (typeof window === "undefined") return "unknown";
  install(); refresh();
  return current?.choice || "unknown";
}
export function measurementAllowed(): boolean { return measurementChoice() === "granted"; }
export function measurementGeneration(): number { measurementChoice(); return generation; }
export function measurementStillAllowed(epoch: number): boolean {
  return measurementAllowed() && generation === epoch;
}
export function setMeasurementChoice(choice: "granted" | "denied"): void {
  if (typeof window === "undefined" || !["granted", "denied"].includes(choice)) return;
  install();
  const next: Preference = { version: 1, choice, savedAt: Date.now() };
  try { window.localStorage.setItem(MEASUREMENT_PREFERENCE_KEY, JSON.stringify(next)); memoryOnly = false; }
  catch { memoryOnly = true; }
  synchronize(next);
}
export function subscribeMeasurement(listener: () => void): () => void {
  listeners.add(listener); install();
  return () => { listeners.delete(listener); };
}

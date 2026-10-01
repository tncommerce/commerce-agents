export const FRAGRANCE_LIBRARY_STORAGE_KEY =
  "scentai_fragrance_library_v1";

export const FRAGRANCE_LIBRARY_EVENT =
  "scentai:fragrance-library-changed";

export type FragranceLibraryState = {
  version: 1;
  wishlist: string[];
  owned: string[];
};

const EMPTY_LIBRARY: FragranceLibraryState = {
  version: 1,
  wishlist: [],
  owned: [],
};

function validProductId(value: unknown): value is string {
  return (
    typeof value === "string" &&
    /^SC-[A-Z0-9-]+$/.test(value) &&
    value.length <= 80
  );
}

function cleanIds(value: unknown): string[] {
  if (!Array.isArray(value)) return [];

  return Array.from(
    new Set(value.filter(validProductId)),
  ).slice(0, 500);
}

export function normalizeFragranceLibrary(
  value: unknown,
): FragranceLibraryState {
  if (!value || typeof value !== "object") {
    return { ...EMPTY_LIBRARY };
  }

  const candidate = value as {
    wishlist?: unknown;
    owned?: unknown;
  };
  const owned = cleanIds(candidate.owned);
  const ownedSet = new Set(owned);

  return {
    version: 1,
    owned,
    wishlist: cleanIds(candidate.wishlist).filter(
      (productId) => !ownedSet.has(productId),
    ),
  };
}

export function parseFragranceLibraryBackup(
  value: unknown,
): FragranceLibraryState | null {
  if (!value || typeof value !== "object") return null;
  const candidate = value as Record<string, unknown>;
  if (
    candidate.version !== 1 ||
    !Array.isArray(candidate.wishlist) ||
    !Array.isArray(candidate.owned) ||
    candidate.wishlist.length > 500 ||
    candidate.owned.length > 500 ||
    !candidate.wishlist.every(validProductId) ||
    !candidate.owned.every(validProductId)
  ) {
    return null;
  }

  return normalizeFragranceLibrary(candidate);
}

// A failed read must not become an empty list for a subsequent save.
export function tryReadFragranceLibrary(): FragranceLibraryState | null {
  if (typeof window === "undefined") return null;

  try {
    const raw = window.localStorage.getItem(
      FRAGRANCE_LIBRARY_STORAGE_KEY,
    );
    if (!raw) return { ...EMPTY_LIBRARY };

    return normalizeFragranceLibrary(JSON.parse(raw));
  } catch {
    return null;
  }
}

export function readFragranceLibrary(): FragranceLibraryState {
  return tryReadFragranceLibrary() ?? { ...EMPTY_LIBRARY };
}

function writeFragranceLibrary(
  next: FragranceLibraryState,
): FragranceLibraryState | null {
  if (typeof window === "undefined") return null;

  const normalized = normalizeFragranceLibrary(next);

  try {
    window.localStorage.setItem(
      FRAGRANCE_LIBRARY_STORAGE_KEY,
      JSON.stringify(normalized),
    );
    window.dispatchEvent(
      new CustomEvent(FRAGRANCE_LIBRARY_EVENT),
    );
    return normalized;
  } catch {
    return null;
  }
}

export function replaceFragranceLibrary(
  next: FragranceLibraryState,
): boolean {
  if (typeof window === "undefined") return false;
  try {
    window.localStorage.setItem(
      FRAGRANCE_LIBRARY_STORAGE_KEY,
      JSON.stringify(normalizeFragranceLibrary(next)),
    );
    window.dispatchEvent(new CustomEvent(FRAGRANCE_LIBRARY_EVENT));
    return true;
  } catch {
    return false;
  }
}

export function setWishlistState(
  productId: string,
  saved: boolean,
): FragranceLibraryState | null {
  const current = tryReadFragranceLibrary();

  if (!current) return null;
  if (!validProductId(productId)) return current;

  const wishlist = new Set(current.wishlist);

  if (saved) wishlist.add(productId);
  else wishlist.delete(productId);

  return writeFragranceLibrary({
    ...current,
    wishlist: [...wishlist],
  });
}

export function setOwnedState(
  productId: string,
  owned: boolean,
): FragranceLibraryState | null {
  const current = tryReadFragranceLibrary();

  if (!current) return null;
  if (!validProductId(productId)) return current;

  const ownedIds = new Set(current.owned);
  const wishlist = new Set(current.wishlist);

  if (owned) {
    ownedIds.add(productId);
    wishlist.delete(productId);
  } else {
    ownedIds.delete(productId);
  }

  return writeFragranceLibrary({
    ...current,
    owned: [...ownedIds],
    wishlist: [...wishlist],
  });
}

export function clearFragranceLibrary(): boolean {
  if (typeof window === "undefined") return false;

  try {
    window.localStorage.removeItem(
      FRAGRANCE_LIBRARY_STORAGE_KEY,
    );
    window.dispatchEvent(
      new CustomEvent(FRAGRANCE_LIBRARY_EVENT),
    );
    return true;
  } catch {
    return false;
  }
}

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

export function readFragranceLibrary(): FragranceLibraryState {
  if (typeof window === "undefined") {
    return { ...EMPTY_LIBRARY };
  }

  try {
    const raw = window.localStorage.getItem(
      FRAGRANCE_LIBRARY_STORAGE_KEY,
    );
    if (!raw) return { ...EMPTY_LIBRARY };

    return normalizeFragranceLibrary(JSON.parse(raw));
  } catch {
    return { ...EMPTY_LIBRARY };
  }
}

function writeFragranceLibrary(
  next: FragranceLibraryState,
): FragranceLibraryState {
  if (typeof window === "undefined") return next;

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
    return readFragranceLibrary();
  }
}

export function setWishlistState(
  productId: string,
  saved: boolean,
): FragranceLibraryState {
  const current = readFragranceLibrary();

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
): FragranceLibraryState {
  const current = readFragranceLibrary();

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

export function clearFragranceLibrary(): void {
  if (typeof window === "undefined") return;

  try {
    window.localStorage.removeItem(
      FRAGRANCE_LIBRARY_STORAGE_KEY,
    );
    window.dispatchEvent(
      new CustomEvent(FRAGRANCE_LIBRARY_EVENT),
    );
  } catch {
    // Nothing else is required if browser storage is unavailable.
  }
}

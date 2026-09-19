"use client";

import { useEffect, useState } from "react";

import { trackAnalyticsEvent } from "@/lib/analytics";
import {
  FRAGRANCE_LIBRARY_EVENT,
  FRAGRANCE_LIBRARY_STORAGE_KEY,
  readFragranceLibrary,
  setOwnedState,
  setWishlistState,
} from "@/lib/fragranceLibrary";

type LibraryState = {
  wishlist: boolean;
  owned: boolean;
};

function currentState(productId: string): LibraryState {
  const library = readFragranceLibrary();

  return {
    wishlist: library.wishlist.includes(productId),
    owned: library.owned.includes(productId),
  };
}

export default function FragranceSaveControls({
  productId,
  source = "fragrance_detail",
  compact = false,
}: {
  productId: string;
  source?: string;
  compact?: boolean;
}) {
  const [state, setState] = useState<LibraryState>({
    wishlist: false,
    owned: false,
  });
  const [storageAvailable, setStorageAvailable] =
    useState(true);

  useEffect(() => {
    const sync = () => setState(currentState(productId));
    const handleStorage = (event: StorageEvent) => {
      if (
        event.key === FRAGRANCE_LIBRARY_STORAGE_KEY ||
        event.key === null
      ) {
        sync();
      }
    };

    try {
      window.localStorage.getItem(
        FRAGRANCE_LIBRARY_STORAGE_KEY,
      );
      sync();
    } catch {
      setStorageAvailable(false);
    }

    window.addEventListener(
      FRAGRANCE_LIBRARY_EVENT,
      sync,
    );
    window.addEventListener("storage", handleStorage);

    return () => {
      window.removeEventListener(
        FRAGRANCE_LIBRARY_EVENT,
        sync,
      );
      window.removeEventListener(
        "storage",
        handleStorage,
      );
    };
  }, [productId]);

  if (!storageAvailable) return null;

  const buttonClass = compact
    ? "rounded-lg border border-(--line) bg-(--surface) px-2.5 py-1.5 text-[11px] font-semibold transition hover:border-(--accent)"
    : "rounded-xl border border-(--line) bg-(--card) px-3.5 py-2.5 text-[12.5px] font-semibold transition hover:border-(--accent)";

  return (
    <div className="flex flex-wrap items-center gap-2">
      <button
        type="button"
        aria-pressed={state.wishlist}
        onClick={() => {
          const nextSaved = !state.wishlist;
          const next = setWishlistState(
            productId,
            nextSaved,
          );
          setState({
            wishlist: next.wishlist.includes(productId),
            owned: next.owned.includes(productId),
          });
          void trackAnalyticsEvent(
            nextSaved
              ? "wishlist_add"
              : "wishlist_remove",
            {
              product_id: productId,
              source,
              surface: "personal_library",
            },
          );
        }}
        disabled={state.owned}
        className={`${buttonClass} ${
          state.wishlist
            ? "border-(--accent) text-(--accent-ink)"
            : "text-(--ink)"
        } disabled:cursor-not-allowed disabled:opacity-45`}
      >
        {state.wishlist
          ? "✓ Gemerkt"
          : state.owned
            ? "Bereits in Sammlung"
            : "♡ Merken"}
      </button>

      <button
        type="button"
        aria-pressed={state.owned}
        onClick={() => {
          const nextOwned = !state.owned;
          const next = setOwnedState(
            productId,
            nextOwned,
          );
          setState({
            wishlist: next.wishlist.includes(productId),
            owned: next.owned.includes(productId),
          });
          void trackAnalyticsEvent(
            nextOwned
              ? "collection_add"
              : "collection_remove",
            {
              product_id: productId,
              source,
              surface: "personal_library",
            },
          );
        }}
        className={`${buttonClass} ${
          state.owned
            ? "border-(--accent) text-(--accent-ink)"
            : "text-(--ink)"
        }`}
      >
        {state.owned
          ? "✓ In meiner Sammlung"
          : "+ Meine Sammlung"}
      </button>
    </div>
  );
}

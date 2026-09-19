"use client";

import { useEffect, useState } from "react";

import {
  FRAGRANCE_LIBRARY_EVENT,
  FRAGRANCE_LIBRARY_STORAGE_KEY,
  readFragranceLibrary,
} from "@/lib/fragranceLibrary";

export default function PersonalLibrarySummary() {
  const [wishlistCount, setWishlistCount] = useState(0);
  const [ownedCount, setOwnedCount] = useState(0);

  useEffect(() => {
    const sync = () => {
      const library = readFragranceLibrary();
      setWishlistCount(library.wishlist.length);
      setOwnedCount(library.owned.length);
    };
    const handleStorage = (event: StorageEvent) => {
      if (
        event.key === FRAGRANCE_LIBRARY_STORAGE_KEY ||
        event.key === null
      ) {
        sync();
      }
    };

    sync();
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
  }, []);

  if (!wishlistCount && !ownedCount) return null;

  return (
    <section className="rounded-2xl border border-(--line) bg-(--card) p-4 shadow-(--shadow-sm)">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-[0.08em] text-(--ink-soft)">
            Deine SCENTAI Duftwelt
          </div>
          <div className="mt-1 text-[14px] font-semibold text-(--ink)">
            {ownedCount
              ? `${ownedCount} ${ownedCount === 1 ? "Duft" : "Düfte"} in deiner Sammlung`
              : "Noch keine Düfte in deiner Sammlung"}
            {wishlistCount
              ? ` · ${wishlistCount} gemerkt`
              : ""}
          </div>
          <p className="mt-1 text-[11.5px] leading-5 text-(--ink-soft)">
            Deine Auswahl bleibt lokal auf diesem Gerät gespeichert.
          </p>
        </div>

        <div className="flex flex-wrap gap-2">
          {ownedCount ? (
            <a
              href="/sammlung"
              className="rounded-xl bg-(--ink) px-3 py-2 text-[12px] font-semibold text-(--surface)"
            >
              Sammlung öffnen
            </a>
          ) : null}
          {wishlistCount ? (
            <a
              href="/merkliste"
              className="rounded-xl border border-(--line) bg-(--surface) px-3 py-2 text-[12px] font-semibold text-(--ink) hover:border-(--accent)"
            >
              Merkliste öffnen
            </a>
          ) : null}
        </div>
      </div>
    </section>
  );
}

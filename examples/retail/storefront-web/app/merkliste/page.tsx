import type { Metadata } from "next";

import FragranceLibraryHub from "@/components/FragranceLibraryHub";
import LegalFooter from "@/components/LegalFooter";
import { LIVE_FRAGRANCES } from "@/lib/fragranceCatalog";

export const metadata: Metadata = {
  title: "Meine Merkliste",
  description:
    "Deine lokal gespeicherte SCENTAI Merkliste für interessante Parfums.",
  robots: {
    index: false,
    follow: true,
  },
};

export default function WishlistPage() {
  return (
    <main className="min-h-screen bg-(--surface) px-4 py-7 text-(--ink) sm:px-6 sm:py-10">
      <div className="mx-auto max-w-[1080px]">
        <a
          href="/"
          className="inline-flex items-center gap-2 text-[13px] font-semibold text-(--accent-ink) hover:underline"
        >
          ← Zurück zu SCENTAI
        </a>
        <FragranceLibraryHub
          mode="wishlist"
          fragrances={LIVE_FRAGRANCES}
        />
        <LegalFooter />
      </div>
    </main>
  );
}

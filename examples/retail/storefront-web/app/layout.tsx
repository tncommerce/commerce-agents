// Copyright 2026 Anthropic PBC
// SPDX-License-Identifier: Apache-2.0

import type { Metadata } from "next";
import { Instrument_Sans } from "next/font/google";
import "./globals.css";
import { SITE_INDEXABLE, SITE_URL } from "@/lib/site";

const instrumentSans = Instrument_Sans({
  subsets: ["latin"],
  variable: "--font-body",
  display: "swap",
});

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  applicationName: "SCENTAI",
  creator: "TNCommerce",
  publisher: "TNCommerce",
  title: {
    default: "SCENTAI – Duftberatung & Parfumvergleich",
    template: "%s | SCENTAI",
  },
  description:
    "Finde passende Parfums nach Duftprofil, Anlass und Budget. Vergleiche Düfte, Community-Erfahrungen und Händlerangebote mit SCENTAI.",
  alternates: {
    canonical: "/",
  },
  robots: SITE_INDEXABLE
    ? {
        index: true,
        follow: true,
      }
    : {
        index: false,
        follow: false,
        nocache: true,
      },
  openGraph: {
    type: "website",
    locale: "de_DE",
    url: SITE_URL,
    siteName: "SCENTAI",
    title: "SCENTAI – Duftberatung & Parfumvergleich",
    description:
      "Persönliche Duftempfehlungen, Duftvergleiche und transparente Händlerangebote.",
  },
  twitter: {
    card: "summary",
    title: "SCENTAI – Duftberatung & Parfumvergleich",
    description:
      "Persönliche Duftempfehlungen, Duftvergleiche und transparente Händlerangebote.",
  },
};

const websiteStructuredData = {
  "@context": "https://schema.org",
  "@type": "WebSite",
  name: "SCENTAI",
  url: SITE_URL,
  inLanguage: "de-DE",
  description:
    "Duftberatung, Parfumvergleich und transparente Händlerangebote.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="de" className={instrumentSans.variable}>
      <body>
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{
            __html: JSON.stringify(websiteStructuredData),
          }}
        />
        {children}
      </body>
    </html>
  );
}

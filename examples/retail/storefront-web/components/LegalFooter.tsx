// Copyright 2026 Anthropic PBC
// SPDX-License-Identifier: Apache-2.0

export default function LegalFooter() {
  return (
    <footer className="mt-8 border-t border-(--line) pt-5 text-[12px] text-(--ink-soft)">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <span>© 2026 DUFYND · TNCommerce</span>
        <a href="/impressum" className="font-medium text-(--accent-ink) hover:underline">
          Impressum
        </a>
        <a href="/datenschutz" className="font-medium text-(--accent-ink) hover:underline">
          Datenschutz
        </a>
        <a href="/transparenz" className="font-medium text-(--accent-ink) hover:underline">
          Transparenz
        </a>
        <a href="/duftfinder" className="font-medium text-(--accent-ink) hover:underline">
          Duftfinder
        </a>
        <a href="/parfum-alternativen" className="font-medium text-(--accent-ink) hover:underline">
          Parfum-Alternativen
        </a>
        <a href="/sammlung" className="font-medium text-(--accent-ink) hover:underline">
          Meine Sammlung
        </a>
        <a href="/merkliste" className="font-medium text-(--accent-ink) hover:underline">
          Merkliste
        </a>
      </div>
    </footer>
  );
}

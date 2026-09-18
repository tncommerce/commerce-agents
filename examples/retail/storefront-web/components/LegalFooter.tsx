// Copyright 2026 Anthropic PBC
// SPDX-License-Identifier: Apache-2.0

export default function LegalFooter() {
  return (
    <footer className="mt-8 border-t border-(--line) pt-5 text-[12px] text-(--ink-soft)">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <span>© 2026 SCENTAI · TNCommerce</span>
        <a href="/impressum" className="font-medium text-(--accent-ink) hover:underline">
          Impressum
        </a>
        <a href="/datenschutz" className="font-medium text-(--accent-ink) hover:underline">
          Datenschutz
        </a>
        <a href="/transparenz" className="font-medium text-(--accent-ink) hover:underline">
          Transparenz
        </a>
      </div>
    </footer>
  );
}

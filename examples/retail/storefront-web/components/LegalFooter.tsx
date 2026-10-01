// Copyright 2026 Anthropic PBC
// SPDX-License-Identifier: Apache-2.0

import AcquisitionInternalLink from "@/components/AcquisitionInternalLink";

export default function LegalFooter() {
  return (
    <footer className="mt-8 border-t border-(--line) pt-5 text-[12px] text-(--ink-soft)">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <span>© 2026 DUFYND · TNCommerce</span>
        <AcquisitionInternalLink href="/impressum" className="font-medium text-(--accent-ink) hover:underline">
          Impressum
        </AcquisitionInternalLink>
        <AcquisitionInternalLink href="/datenschutz" className="font-medium text-(--accent-ink) hover:underline">
          Datenschutz
        </AcquisitionInternalLink>
        <AcquisitionInternalLink href="/transparenz" className="font-medium text-(--accent-ink) hover:underline">
          Transparenz
        </AcquisitionInternalLink>
        <AcquisitionInternalLink href="/bildnachweise" className="font-medium text-(--accent-ink) hover:underline">
          Bildnachweise
        </AcquisitionInternalLink>
        <AcquisitionInternalLink href="/duftfinder" className="font-medium text-(--accent-ink) hover:underline">
          Duftfinder
        </AcquisitionInternalLink>
        <AcquisitionInternalLink href="/parfum-alternativen" className="font-medium text-(--accent-ink) hover:underline">
          Parfum-Alternativen
        </AcquisitionInternalLink>
        <AcquisitionInternalLink href="/sammlung" className="font-medium text-(--accent-ink) hover:underline">
          Meine Sammlung
        </AcquisitionInternalLink>
        <AcquisitionInternalLink href="/merkliste" className="font-medium text-(--accent-ink) hover:underline">
          Merkliste
        </AcquisitionInternalLink>
      </div>
    </footer>
  );
}

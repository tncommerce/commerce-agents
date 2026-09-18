"use client";

import { useEffect, useState } from "react";

import {
  fetchMerchantPartners,
  merchantPartnerClickoutUrl,
} from "@/lib/api";
import { trackAnalyticsEvent } from "@/lib/analytics";
import type { MerchantPartnersPayload } from "@/lib/types";

export default function MerchantDiscovery() {
  const [payload, setPayload] = useState<
    MerchantPartnersPayload | null
  >(null);

  useEffect(() => {
    let active = true;

    void fetchMerchantPartners()
      .then((value) => {
        if (active) setPayload(value);
      })
      .catch(() => {
        if (active) setPayload(null);
      });

    return () => {
      active = false;
    };
  }, []);

  if (!payload?.partners.length) return null;

  return (
    <section
      aria-label="Partnerhändler entdecken"
      className="rounded-2xl border border-(--line) bg-(--card) p-4 shadow-(--shadow-sm)"
    >
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <h2 className="text-[15px] font-semibold">
          Bei Partnerhändlern entdecken
        </h2>
        <span className="text-[11.5px] text-(--ink-soft)">
          Auch für weitere Beauty- und Parfumkäufe
        </span>
      </div>
      <p className="mt-1 max-w-2xl text-[12px] leading-5 text-(--ink-soft)">
        Wenn du ohnehin bei einem Partnerhändler stöbern möchtest,
        kannst du SCENTAI über diesen Einstieg unterstützen. Deine
        Duftempfehlungen werden dadurch nicht beeinflusst.
      </p>

      <div className="mt-3 flex flex-wrap gap-2">
        {payload.partners.map((partner) => (
          <a
            key={partner.merchant_id}
            href={merchantPartnerClickoutUrl(
              partner.merchant_id,
            )}
            target="_blank"
            rel="sponsored noopener noreferrer"
            onClick={() => {
              void trackAnalyticsEvent(
                "merchant_clickout",
                {
                  source: partner.merchant_id,
                  surface: "merchant_discovery",
                },
              );
            }}
            className="rounded-xl border border-(--line-strong) bg-(--surface) px-3.5 py-2 text-[12.5px] font-semibold text-(--ink) transition hover:border-(--accent)"
          >
            {partner.merchant_name} öffnen
            {partner.description ? (
              <span className="ml-1 font-normal text-(--ink-soft)">
                · {partner.description}
              </span>
            ) : null}
          </a>
        ))}
      </div>

      <p className="mt-3 text-[10.5px] leading-4 text-(--ink-soft)">
        {payload.affiliate_disclosure}
      </p>
    </section>
  );
}

"use client";

import { Composer, useStoreFrame } from "web-shared";
import { catalogAudienceFor, LIVE_FRAGRANCES } from "@/lib/fragranceCatalog";
import AcquisitionInternalLink from "../AcquisitionInternalLink";
import AtelierHero from "../AtelierHero";
import AtelierSelection from "../AtelierSelection";
import ScentAtlas from "../ScentAtlas";
import LegalFooter from "../LegalFooter";
import MerchantDiscovery from "../MerchantDiscovery";
import PersonalLibrarySummary from "../PersonalLibrarySummary";

const AUDIENCES = [{ key: "women", label: "Damen", world: "silk" }, { key: "men", label: "Herren", world: "mineral" }, { key: "unisex", label: "Unisex", world: "amber" }] as const;

export default function HomeView({ shopperName: _shopperName, sessionSettled }: { shopperName: string; sessionSettled: boolean }) {
  const { chat, ask } = useStoreFrame();
  // Include the source-verified editorial release pages in public counts,
  // even when the merchant API has no price/offer for those fragrances.
  const scentCount = LIVE_FRAGRANCES.length;
  const audienceCounts = LIVE_FRAGRANCES.reduce(
    (counts, fragrance) => {
      const audience = catalogAudienceFor(fragrance.target_groups);
      if (audience) counts[audience] += 1;
      return counts;
    },
    { women: 0, men: 0, unisex: 0 },
  );
  return <div className="wow-home wow-polish vr-home mx-auto w-full">
    <AtelierHero />
    <AtelierSelection />
    <div id="duft-atlas"><ScentAtlas /></div>
    <section className="wow-audiences" data-dufynd-home-audience-stage aria-labelledby="dufynd-audience-discovery-heading">
      <div className="wow-section-heading"><div><p className="wow-kicker">03 / Deine Duftwelt</p><h2 id="dufynd-audience-discovery-heading">Wo zieht es dich hin?</h2></div></div>
      <div className="wow-audience-index">{AUDIENCES.map(({ key, label, world }, i) => <AcquisitionInternalLink key={key} href={`/duft?zielgruppe=${key}`} data-dufynd-home-audience-card data-dufynd-home-world={world}>
        <span className="wow-audience-number" aria-hidden>0{i+1}</span><div><h3>{label}</h3><p>{audienceCounts[key] === 1 ? "1 Duft" : `${audienceCounts[key]} Düfte`} im aktuellen Katalog</p></div><span aria-hidden>↗</span>
      </AcquisitionInternalLink>)}</div>
      <nav aria-label="Duftwelten im Katalog"><span>Nach Duftgefühl</span>{[["freshness","Frisch"],["sweetness","Süß"],["woodiness","Holzig"],["spiciness","Würzig"]].map(([profile,label])=><AcquisitionInternalLink key={profile} href={`/duft?profil=${profile}`}>{label} ↗</AcquisitionInternalLink>)}</nav>
      <AcquisitionInternalLink className="wow-catalog-index-link" href="/duft">Alle {scentCount} Düfte im Katalog entdecken →</AcquisitionInternalLink>
    </section>
    <section id="duftberatung" className="wow-advisor" aria-labelledby="wow-advisor-title">
      <div><p className="wow-kicker">Persönliche Duftberatung</p><h2 id="wow-advisor-title">Noch unentschlossen?</h2><p>Beschreibe, was du suchst. Wir helfen dir beim Vergleichen.</p></div>
      <Composer send={ask} ready={chat?.ready ?? false} busy={chat?.busy ?? false} label="Nachricht an DUFYND Advisor" placeholder="Was suchst du?" />
      <div className="wow-advisor-links"><AcquisitionInternalLink href="/parfum-alternativen">Alternative finden ↗</AcquisitionInternalLink><AcquisitionInternalLink href="/parfum-geschenkberater">Duft verschenken ↗</AcquisitionInternalLink></div>
    </section>
    <PersonalLibrarySummary />
    <MerchantDiscovery sessionSettled={sessionSettled} />
    <aside className="wow-affiliate-note" aria-label="Händlerrolle und Partnerlinks"><p><strong>Entdecken bei DUFYND. Kaufen beim Händler.</strong> Kaufvertrag, Zahlung und Versand erfolgen beim ausgewählten Händler.</p><p>Werbung: Händlerlinks können Partnerlinks sein. Bei einem Kauf kann DUFYND eine Provision erhalten. Für dich soll sich der Händlerpreis dadurch nicht erhöhen.</p><AcquisitionInternalLink href="/transparenz">So bewerten wir Empfehlungen und Angebote ↗</AcquisitionInternalLink></aside>
    <LegalFooter />
  </div>;
}

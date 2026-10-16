"use client";

import staticCatalog from "../../lib/generated/public-catalog.json";
import { Composer, useCatalogIndex, useStoreFrame } from "web-shared";
import { fetchProducts } from "@/lib/api";
import { catalogAudienceFor, getLiveFragranceByProductId } from "@/lib/fragranceCatalog";
import type { Product } from "@/lib/types";
import AcquisitionInternalLink from "../AcquisitionInternalLink";
import AtelierHero from "../AtelierHero";
import AtelierSelection from "../AtelierSelection";
import HomeComparison from "../HomeComparison";
import HomeOffers from "../HomeOffers";
import styles from "../VisualHome.module.css";
import ScentAtlas from "../ScentAtlas";
import LegalFooter from "../LegalFooter";
import MerchantDiscovery from "../MerchantDiscovery";
import PersonalLibrarySummary from "../PersonalLibrarySummary";

const STATIC_CATALOG: Record<string, Product> = Object.fromEntries((staticCatalog.products as unknown as Product[]).map(product => [product.product_id, product]));
const AUDIENCES = [{ key: "women", label: "Damen", world: "silk" }, { key: "men", label: "Herren", world: "mineral" }, { key: "unisex", label: "Unisex", world: "amber" }] as const;

export default function HomeView({ shopperName: _shopperName, sessionSettled }: { shopperName: string; sessionSettled: boolean }) {
  const { chat, ask } = useStoreFrame();
  const liveCatalog = useCatalogIndex(fetchProducts);
  const loadedCatalog = Object.keys(liveCatalog).length
    ? liveCatalog
    : STATIC_CATALOG;
  const catalog = Object.fromEntries(
    Object.entries(loadedCatalog).filter(([id]) => getLiveFragranceByProductId(id)).map(([id, product]) => [id, {
      ...product, review_count: 0, rating: undefined,
      attributes: Object.fromEntries(Object.entries(product.attributes || {}).filter(([key]) => !/community|rating|rank|longevity|projection/i.test(key))),
    }]),
  );
  const scentCount = Object.values(catalog).filter(
    (product) =>
      String(product.product_id).startsWith("SC-") &&
      product.in_stock !== false &&
      Boolean(
        getLiveFragranceByProductId(
          String(product.product_id),
        ),
      ),
  ).length;
  const audienceCounts = Object.values(catalog).reduce(
    (counts, product) => {
      if (
        !String(product.product_id).startsWith("SC-") ||
        product.in_stock === false
      ) {
        return counts;
      }

      const fragrance = getLiveFragranceByProductId(
        String(product.product_id),
      );

      const audience = fragrance
        ? catalogAudienceFor(fragrance.target_groups)
        : null;
      if (audience) {
        counts[audience] += 1;
      }

      return counts;
    },
    { women: 0, men: 0, unisex: 0 },
  );
  return <div className={`wow-home wow-polish mx-auto w-full ${styles.home}`} data-dufynd-visual-reset>
    <AtelierHero />
    <AtelierSelection />
    <HomeComparison />
    <HomeOffers />
    <section className="wow-audiences" data-dufynd-home-audience-stage aria-labelledby="dufynd-audience-discovery-heading">
      <div className="wow-section-heading"><div><p className="wow-kicker">Deine Duftwelt</p><h2 id="dufynd-audience-discovery-heading">Wo zieht es dich hin?</h2></div></div>
      <div className="wow-audience-index">{AUDIENCES.map(({ key, label, world }, i) => <AcquisitionInternalLink key={key} href={`/duft?zielgruppe=${key}`} data-dufynd-home-audience-card data-dufynd-home-world={world}>
        <span className="wow-audience-number" aria-hidden>0{i+1}</span><div><h3>{label}</h3><p>{audienceCounts[key] === 1 ? "1 Duft" : `${audienceCounts[key]} Düfte`} im aktuellen Katalog</p></div><span aria-hidden>↗</span>
      </AcquisitionInternalLink>)}</div>
      <nav aria-label="Duftwelten im Katalog"><span>Nach Duftgefühl</span>{[["freshness","Frisch"],["sweetness","Süß"],["woodiness","Holzig"],["spiciness","Würzig"]].map(([profile,label])=><AcquisitionInternalLink key={profile} href={`/duft?profil=${profile}`}>{label} ↗</AcquisitionInternalLink>)}</nav>
      <AcquisitionInternalLink className="wow-catalog-index-link" href="/duft">Alle {scentCount} Düfte im Katalog entdecken →</AcquisitionInternalLink>
    </section>
    <details id="duft-atlas" className={styles.atlasDisclosure} data-atlas-disclosure>
      <summary><span><small>Für Neugierige</small><strong>Folge einer Duftnote.</strong></span><span>Duftnoten-Atlas öffnen <i aria-hidden>＋</i></span></summary>
      <ScentAtlas />
    </details>
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

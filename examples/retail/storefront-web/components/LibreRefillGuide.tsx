import AcquisitionInternalLink from "@/components/AcquisitionInternalLink";
import OfferSectionLink from "@/components/OfferSectionLink";

// Buyer-intent editorial from WORK49, scoped only to SC-YSL-LIBRE-EDP-90.
// This guide intentionally contains no cached merchant price, stock or discount.
// Live eligible offers remain owned by FragranceOffers and its 72-hour gate.
export const LIBRE_REFILL_SEO_TITLE =
  "YSL Libre EDP 90 ml: nachfüllbarer Flakon oder Refill?";

export const LIBRE_REFILL_SEO_DESCRIPTION =
  "Libre EDP 90 ml richtig kaufen: nachfüllbaren Flakon und Refill unterscheiden, die Variante prüfen und passende Händlerangebote auf DUFYND finden.";

const identity = [
  { label: "Marke", value: "Yves Saint Laurent" },
  { label: "Duft", value: "Libre – nicht Intense oder Le Parfum" },
  { label: "Konzentration", value: "Eau de Parfum (EDP)" },
  { label: "Ausführung", value: "90 ml, nachfüllbarer Flakon" },
] as const;

const decisions = [
  {
    title: "Du möchtest einen kompletten Flakon.",
    description:
      "Wähle Libre Eau de Parfum, 90 ml, als nachfüllbaren Flakon. Ein Refill allein ist kein vollständiger Flakon.",
  },
  {
    title: "Du möchtest deinen Flakon nachfüllen.",
    description:
      "Prüfe eine passende Libre-EDP-Ersatzfüllung und die Hinweise für deinen konkreten, nachfüllbaren Flakon.",
  },
  {
    title: "Du bist nicht sicher, welche Version du besitzt.",
    description:
      "Klär die Nachfüllbarkeit zuerst anhand von Verpackung und Herstellerangaben. Nicht jedes ältere Exemplar ist automatisch kompatibel.",
  },
] as const;

export default function LibreRefillGuide() {
  return (
    <section
      id="libre-nachfuellbar"
      aria-labelledby="libre-refill-title"
      data-dufynd-libre-refill-guide
      className="mt-5 scroll-mt-24 rounded-2xl border border-(--line) bg-(--card) p-4 shadow-(--shadow-sm) sm:p-6 lg:p-8"
    >
      <div className="max-w-3xl">
        <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-(--accent-ink)">
          DUFYND Kaufratgeber · Produktvariante verstehen
        </p>
        <h2
          id="libre-refill-title"
          className="mt-2 text-[24px] font-semibold leading-tight tracking-[-0.025em] text-(--ink) sm:text-[28px]"
        >
          {LIBRE_REFILL_SEO_TITLE}
        </h2>
        <p className="mt-4 text-[14px] leading-6 text-(--ink-soft) sm:text-[15px]">
          Du suchst Libre, findest aber Angebote mit „nachfüllbar“, „Refill“
          und unterschiedlichen Milliliterangaben? Entscheidend ist nicht nur
          der Duftname: Auch der Lieferumfang muss passen.
        </p>
        <p className="mt-3 text-[14px] leading-6 text-(--ink-soft) sm:text-[15px]">
          Der auf DUFYND zugeordnete{" "}
          <strong className="font-semibold text-(--ink)">
            Yves Saint Laurent Libre Eau de Parfum mit 90 ml ist ein
            nachfüllbarer Flakon
          </strong>
          . Er ist keine bloße Ersatzfüllung. Beim zugeordneten Notino-Artikel
          lautet der Code <strong className="font-semibold text-(--ink)">VZR11010</strong>.
          Eine Refill-Packung wird dort ausdrücklich als Ersatzfüllung geführt.
          Welche Variante du tatsächlich erhältst, prüfst du vor dem Kauf
          beim Händler.
        </p>
        <OfferSectionLink
          productId="SC-YSL-LIBRE-EDP-90"
          source="libre_refill_editorial_intro"
          className="mt-4 inline-flex min-h-11 items-center justify-center rounded-xl bg-(--accent-strong) px-4 py-3 text-[13px] font-semibold text-white hover:brightness-95"
        >
          Libre EDP 90 ml · Händlerangebote prüfen →
        </OfferSectionLink>

        <h3 className="mt-8 text-[18px] font-semibold tracking-tight text-(--ink)">
          „Nachfüllbar“ beschreibt den Flakon – „Refill“ den Nachfüller
        </h3>
        <p className="mt-2 text-[14px] leading-6 text-(--ink-soft)">
          YSL führt Libre Eau de Parfum als vollständigen nachfüllbaren
          90-ml-Flakon und den 100-ml-Nachfüllpack als getrennte Varianten.
          Was du benötigst, hängt davon ab, ob du einen kompletten Flakon
          kaufen oder einen kompatiblen vorhandenen Flakon auffüllen möchtest.
        </p>
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-3">
        {decisions.map((item) => (
          <div
            key={item.title}
            className="min-w-0 rounded-xl border border-(--line) bg-(--well)/35 p-4"
          >
            <h4 className="text-[14px] font-semibold leading-5 text-(--ink)">
              {item.title}
            </h4>
            <p className="mt-2 text-[13px] leading-5 text-(--ink-soft)">
              {item.description}
            </p>
          </div>
        ))}
      </div>

      <div className="mt-4 max-w-3xl space-y-6 text-[14px] leading-6 text-(--ink-soft)">
        <p>
          Dass die aktuelle Ausführung nachfüllbar ist, beweist nicht die
          Kompatibilität jedes älteren Flakons. Versuche nicht, einen unklaren
          oder festsitzenden Sprühkopf mit Gewalt zu öffnen.
        </p>

        <div>
          <h3 className="text-[18px] font-semibold leading-6 text-(--ink)">
            Diese Libre-Variante ist gemeint – und diese nicht
          </h3>
          <p className="mt-2">
            Für den hier beschriebenen Kaufweg müssen vier Angaben
            zusammenpassen:
          </p>
          <dl className="mt-3 grid gap-2 sm:grid-cols-2">
            {identity.map((item) => (
              <div
                key={item.label}
                className="min-w-0 rounded-lg border border-(--line) bg-(--surface) px-3 py-2"
              >
                <dt className="text-[11px] font-semibold uppercase tracking-[0.06em] text-(--ink-soft)">
                  {item.label}
                </dt>
                <dd className="mt-1 text-[14px] font-medium text-(--ink)">
                  {item.value}
                </dd>
              </div>
            ))}
          </dl>
          <p className="mt-3">
            Libre Eau de Parfum Intense und Libre Le Parfum sind eigenständige
            Produkte. Solche Zusätze sind nicht austauschbar. Ein Angebot
            kann preislich attraktiv aussehen und trotzdem eine andere
            Konzentration, Füllmenge oder einen Nachfüller enthalten.
          </p>
          <p className="mt-3">
            Auf DUFYND ist der Angebotsbereich dem vollständigen
            EDP-90-ml-Flakon zugeordnet. Prüfe die Variante im ausgewählten
            Händlerangebot und vor dem Bezahlen im Warenkorb erneut.
          </p>
        </div>

        <div>
          <h3 className="text-[18px] font-semibold leading-6 text-(--ink)">
            So vergleichst du die Angebote sinnvoll
          </h3>
          <p className="mt-2">
            Vergleiche zuerst identische Produkte – erst danach Preise.
            Ein kleinerer Flakon und eine Ersatzfüllung sind kein direkter
            Preisvergleich mit dem vollständigen 90-ml-Flakon.
          </p>
          <ul className="mt-3 list-disc space-y-2 pl-5 marker:text-(--accent-ink)">
            <li>
              <strong className="text-(--ink)">Was bekommst du?</strong>{" "}
              Duftversion, Konzentration, Inhalt sowie Flakon oder Nachfüllung
              müssen übereinstimmen.
            </li>
            <li>
              <strong className="text-(--ink)">Was zahlst du insgesamt?</strong>{" "}
              Beachte die ausgewiesenen Versandkosten und den tatsächlichen
              Gesamtpreis.
            </li>
            <li>
              <strong className="text-(--ink)">Welche Bedingungen gelten?</strong>{" "}
              Ein Preis mit Rabattcode ist nicht automatisch ohne Code
              erhältlich. Prüfe die Gutscheinbedingungen.
            </li>
          </ul>
          <p className="mt-3">
            Für Größenvergleiche kannst du den Preis pro 100 ml berechnen:
            Artikelpreis geteilt durch Füllmenge, mal 100. Vergleiche die
            tatsächliche Bestellsumme trotzdem separat. Der günstigere
            Milliliter hilft wenig, wenn du eine andere Menge oder einen
            vollständigen Flakon brauchst.
          </p>
        </div>

        <div>
          <h3 className="text-[18px] font-semibold leading-6 text-(--ink)">
            Welche Ausführung passt zu deinem nächsten Kauf?
          </h3>
          <p className="mt-2">
            Du brauchst einen kompletten Flakon und möchtest das reguläre
            Libre Eau de Parfum? Dann prüfe die hier beschriebene
            90-ml-Ausführung. Du willst nur einen vorhandenen Flakon
            auffüllen? Dann suche eine zu deinem Exemplar passende
            Ersatzfüllung – der DUFYND-Angebotsbereich zeigt nicht
            automatisch solche Refill-Produkte.
          </p>
          <p className="mt-3">
            Du bist noch unsicher, ob Libre zu dir passt? Entdecke zunächst
            das Duftprofil auf dieser Seite oder sieh dir den{" "}
            <AcquisitionInternalLink
              href="/duft"
              className="font-semibold text-(--accent-ink) underline underline-offset-2"
            >
              DUFYND-Duftkatalog
            </AcquisitionInternalLink>{" "}
            an. Dieser Kaufratgeber ersetzt keinen persönlichen Tragetest
            und macht keine Haltbarkeits- oder Komplimentversprechen.
          </p>
        </div>
      </div>

      <div className="mt-7 rounded-xl border border-(--line) bg-(--well)/45 p-4 sm:p-5">
        <h3 className="text-[17px] font-semibold text-(--ink)">
          Libre EDP 90 ml · Händlerangebote prüfen
        </h3>
        <p className="mt-2 max-w-3xl text-[13px] leading-5 text-(--ink-soft)">
          Im Angebotsbereich findest du die jeweils von DUFYND angezeigten
          Händlerangaben, Prüfzeitpunkte und Versandkosten. Preise und
          Verfügbarkeit können sich ändern; maßgeblich sind die Angaben
          beim Händler. Zeigt DUFYND gerade kein Angebot, bedeutet das
          nicht, dass der Duft generell ausverkauft ist.
        </p>
        <OfferSectionLink
          productId="SC-YSL-LIBRE-EDP-90"
          source="libre_refill_editorial_cta"
          className="mt-4 inline-flex min-h-11 items-center justify-center rounded-xl bg-(--accent-strong) px-4 py-3 text-[13px] font-semibold text-white hover:brightness-95"
        >
          Zum aktuellen Angebotsbereich ↑
        </OfferSectionLink>
        <p className="mt-3 text-[12px] leading-5 text-(--ink-soft)">
          Werbung · DUFYND enthält Affiliate-Links. Bei einem Kauf über
          einen Partnerlink kann DUFYND eine Provision erhalten. Weitere
          Informationen findest du unter{" "}
          <AcquisitionInternalLink
            href="/transparenz"
            className="font-semibold text-(--accent-ink) underline underline-offset-2"
          >
            Transparenz
          </AcquisitionInternalLink>
          .
        </p>
      </div>

      <div className="mt-6 max-w-3xl border-t border-(--line) pt-4">
        <h3 className="text-[13px] font-semibold text-(--ink)">
          Quellen zur Produkt- und Variantenabgrenzung
        </h3>
        <ol className="mt-2 list-decimal space-y-2 pl-5 text-[12px] leading-5 text-(--ink-soft)">
          <li>
            <a
              href="https://www.notino.de/yves-saint-laurent/yves-saint-laurent-libre-eau-de-parfum-fuer-damen/p-15968532/"
              target="_blank"
              rel="noopener noreferrer"
              className="underline underline-offset-2 hover:text-(--ink)"
            >
              Notino: Libre Eau de Parfum, nachfüllbarer Flakon, 90 ml,
              Artikel VZR11010
            </a>
          </li>
          <li>
            <a
              href="https://www.notino.de/yves-saint-laurent/yves-saint-laurent-libre-eau-de-parfum-fuer-damen/p-16199341/"
              target="_blank"
              rel="noopener noreferrer"
              className="underline underline-offset-2 hover:text-(--ink)"
            >
              Notino: separat bezeichnete Libre-EDP-Ersatzfüllung
            </a>
          </li>
          <li>
            <a
              href="https://www.yslbeauty.de/dufte/dufte-fur-sie/libre/libre-eau-de-parfum/WW-50424YSL.html"
              target="_blank"
              rel="noopener noreferrer"
              className="underline underline-offset-2 hover:text-(--ink)"
            >
              YSL Beauty: Libre Eau de Parfum, Größen und Nachfüllpack
            </a>
          </li>
        </ol>
        <p className="mt-2 text-[12px] leading-5 text-(--ink-soft)">
          Sachquellen geprüft am 18.10.2026. Kein Nachweis für heute
          gültige Händlerpreise oder Lieferbarkeit. Es wurden keine
          fremden Bilder oder Werbetexte übernommen.
        </p>
      </div>
    </section>
  );
}

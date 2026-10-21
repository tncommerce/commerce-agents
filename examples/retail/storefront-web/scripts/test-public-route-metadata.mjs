// Check the actual exported HTML head, not a JSX string or client-side rewrite.
// Existing public routes must render their own canonical, search snippet,
// OpenGraph and Twitter metadata. No network traffic or analytics.
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const root = fileURLToPath(new URL("../out/", import.meta.url));
const origin = process.env.NEXT_PUBLIC_SITE_URL?.replace(/\/$/, "") || "https://dufynd.de";
const cases = [
  {
    route: "/duft",
    title: "Parfums entdecken",
    description: "Entdecke den unabhängigen DUFYND Duftkatalog mit exakten Varianten, dokumentierten Duftnoten und separat geprüften Händlerangeboten.",
  },
  {
    route: "/duftfinder",
    title: "Duftfinder – Parfum nach Anlass, Budget & Profil",
    description: "Finde mit DUFYND passende Parfums nach Anlass, Budget, Duftprofil, Haltbarkeit und Ausstrahlung.",
  },
  {
    route: "/parfum-alternativen",
    title: "Parfum-Alternativen finden & vergleichen",
    description: "Finde mit DUFYND Parfum-Alternativen und vergleiche Duftrichtung, Performance, Community-Daten und Preis.",
  },
  {
    route: "/parfum-geschenkberater",
    title: "Parfum-Geschenkberater – Duft als Geschenk finden",
    description: "Finde mit DUFYND ein Parfumgeschenk anhand von Person, Anlass, Budget und bekannten Duftvorlieben.",
  },
  {
    route: "/start",
    title: "DUFYND – Duftfinder, Katalog, Alternativen & Geschenkberatung",
    description: "Starte bei DUFYND mit Duftfinder, Duftkatalog, Parfum-Alternativen oder Geschenkberatung.",
    noindex: true,
  },
  {
    route: "/vergleich",
    title: "Parfumvergleiche",
    description: "Vergleiche ausgewählte Parfums bei DUFYND anhand exakter Varianten, redaktioneller Duftprofile und historischer Preisreferenzen.",
  },
];

function exportedHtml(route) {
  const relative = route.slice(1);
  const alternatives = [
    path.join(root, relative + ".html"),
    path.join(root, relative, "index.html"),
  ];
  const located = alternatives.find(existsSync);
  assert.ok(located, `Missing static public export ${route}`);
  return readFileSync(located, "utf8");
}

function headFor(route) {
  const html = exportedHtml(route);
  const match = html.match(/<head(?:\s[^>]*)?>([\s\S]*?)<\/head>/i);
  assert.ok(match, `Missing initial HTML head ${route}`);
  return match[1];
}

function attr(tag, name) {
  const match = [...tag.matchAll(/([A-Za-z_:][-A-Za-z0-9_:]*)\s*=\s*(?:"([^"]*)"|'([^']*)')/g)]
    .find((candidate) => candidate[1].toLowerCase() === name.toLowerCase());
  return match ? match[2] ?? match[3] : null;
}

function decode(value) {
  return String(value || "")
    .replaceAll("&amp;", "&")
    .replaceAll("&quot;", '"')
    .replaceAll("&#39;", "'")
    .replaceAll("&lt;", "<")
    .replaceAll("&gt;", ">");
}

function uniqueTag(head, pattern, attribute, selector, route) {
  const found = [...head.matchAll(pattern)].map((m) => m[0])
    .filter((t) => attr(t, attribute)?.toLowerCase() === selector.toLowerCase());
  assert.equal(found.length, 1, `${route}: exactly one ${selector} expected in initial HTML head`);
  return found[0];
}

function meta(head, attribute, selector, route) {
  return decode(attr(uniqueTag(head, /<meta\b[^>]*>/gi, attribute, selector, route), "content"));
}

let checks = 0;
for (const row of cases) {
  const head = headFor(row.route);
  const titleTags = [...head.matchAll(/<title\b[^>]*>([\s\S]*?)<\/title>/gi)];
  assert.equal(titleTags.length, 1, `${row.route}: exactly one title expected`);
  assert.ok(decode(titleTags[0][1]).startsWith(row.title), `${row.route}: route-specific document title missing`);
  checks++;
  assert.equal(meta(head, "name", "description", row.route), row.description,
    `${row.route}: route-specific meta description missing`);
  checks++;
  const canonical = uniqueTag(head, /<link\b[^>]*>/gi, "rel", "canonical", row.route);
  assert.equal(attr(canonical, "href"), origin + row.route, `${row.route}: canonical mismatch`);
  checks++;
  assert.equal(meta(head, "property", "og:title", row.route), row.title,
    `${row.route}: OpenGraph title falls back to homepage`);
  checks++;
  assert.equal(meta(head, "property", "og:description", row.route), row.description);
  checks++;
  assert.equal(meta(head, "property", "og:url", row.route), origin + row.route);
  checks++;
  assert.equal(meta(head, "name", "twitter:title", row.route), row.title);
  checks++;
  assert.equal(meta(head, "name", "twitter:description", row.route), row.description);
  checks++;
  const robots = meta(head, "name", "robots", row.route);
  assert.equal(robots.includes("noindex"), Boolean(row.noindex),
    `${row.route}: robots indexing policy changed`);
  checks++;
}
const home = headFor("/");
assert.equal(meta(home, "property", "og:url", "/"), origin,
  "Root homepage OpenGraph URL must stay unchanged");
checks++;
console.log(JSON.stringify({
  status: "PASS",
  checks,
  pages: cases.length + 1,
  source: "initial static export HTML head",
  networkRequests: 0,
  analyticsEvents: 0,
  merchantClickouts: 0,
}));

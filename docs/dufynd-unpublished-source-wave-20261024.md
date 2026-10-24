# DUFYND · Unveröffentlichte 20 Düfte – reale Quellenprüf-Charge

**Stand:** 24.10.2026 · Nur Entwickler-Dokumentation, keine Produkt-/Bildfreigabe.

`docs/dufynd-unpublished-source-wave-20261024.json` enthält die **erste klare
20er-Charge ohne bereits öffentliche Düfte**, aus den vorhandenen
Repository-Dateien berechnet. **Keine externe Feed-Suche wurde behauptet.**

- 50 Staging-Profile, 5 bereits öffentlich, 45 unveröffentlicht.
- 20 Produkttargets, davon 0 mit registriertem Originalbild.
- 1 vorhandene Affiliate-Routen in historischen Angebotsdaten; keine frisch bestätigten Preise.
- 1 Konflikt zwischen gespeicherten Händler-GTINs, **HOLD bis exakte Variante geklärt**.

## Priorisierte manuelle Quellenarbeit

| Reihenfolge | Duft | GTIN-/Bildstatus |
|---:|---|---|
| 1 | Lattafa Eclaire 100 ml | TRACKED ROUTE IMAGE HOLD |
| 2 | Amouage Reflection Man 100 ml | GTIN CONFLICT HOLD |
| 3 | Burberry Goddess 100 ml | SOURCE ACQUISITION HOLD |
| 4 | Hugo Boss BOSS Bottled 100 ml | SOURCE ACQUISITION HOLD |
| 5 | Jean Paul Gaultier Le Male Le Parfum 125 ml | SOURCE ACQUISITION HOLD |
| 6 | Narciso Rodriguez for her PURE MUSC 100 ml | SOURCE ACQUISITION HOLD |
| 7 | Prada L'Homme Intense 100 ml | SOURCE ACQUISITION HOLD |
| 8 | Prada Paradoxe 90 ml | SOURCE ACQUISITION HOLD |
| 9 | Viktor & Rolf Spicebomb Extreme 90 ml | SOURCE ACQUISITION HOLD |
| 10 | Amouage Guidance 46 100 ml | SOURCE ACQUISITION HOLD |
| 11 | Chloé Chloé 100 ml | SOURCE ACQUISITION HOLD |
| 12 | Hugo Boss BOSS Bottled Absolu 100 ml | SOURCE ACQUISITION HOLD |
| 13 | Jean Paul Gaultier Fleur du Mâle (2026) 125 ml | SOURCE ACQUISITION HOLD |
| 14 | Kayali Yum Boujee Marshmallow | 81 100 ml | SOURCE ACQUISITION HOLD |
| 15 | Lattafa Angham 100 ml | SOURCE ACQUISITION HOLD |
| 16 | Parfums de Marly Valaya Exclusif 75 ml | SOURCE ACQUISITION HOLD |
| 17 | Yves Saint Laurent MYSLF Le Parfum 100 ml | SOURCE ACQUISITION HOLD |
| 18 | Dior Hypnotic Poison 100 ml | SOURCE ACQUISITION HOLD |
| 19 | Dior Sauvage Elixir 100 ml | SOURCE ACQUISITION HOLD |
| 20 | Dolce & Gabbana The One for Men (2025) 100 ml | SOURCE ACQUISITION HOLD |

Jede Händler-SKU ist nur eine **historisch vermerkte Zuordnung**. Ein aktueller
offizieller Quellbeleg mit EAN/GTIN, identischer Konzentration, Größe und
eindeutigem Flakon bleibt zwingend. Ein offizieller Awin-Feed kann
Review-Kandidaten belegen; Rechtebeleg und **Owner-Fotoabnahme** bleiben
separate Tore. Händlerpreise, Tracking-Links, Bestände und Bild-URLs
werden in diesem Dossier weder ergänzt noch aktiviert.

**Bestehender Review-Weg:** `python scripts/report_dufynd_unpublished_photo_sources.py --batch-size 20 --output /tmp/dufynd-unpublished-source-queue.json`.
Eine optionale aktuelle offizielle Feed-Datei wird ausschließlich von
`report_dufynd_public_photo_feed_leads.create_review` verarbeitet.
Keine neuen Zugänge, Abos, Migrations-/Render-Aktionen oder Kosten freigegeben.

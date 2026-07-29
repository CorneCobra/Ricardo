# Kenteken check

Een openbare pagina met een formulier dat basisgegevens van een voertuig
ophaalt op basis van het kenteken, via de [open data van de RDW](https://opendata.rdw.nl/),
en waarmee je een keuring/inname kunt vastleggen en als **PDF** kunt downloaden.

## Hoe het werkt

- Statische site — alleen HTML, CSS en JavaScript, geen backend.
- De browser van de bezoeker roept rechtstreeks de openbare
  [SODA-API](https://dev.socrata.com/) van de RDW aan. Er is **geen
  API-sleutel** nodig.
- Gebruikte datasets:
  - `m9d7-ebf2` — Gekentekende voertuigen (algemene gegevens)
  - `8ys7-d773` — Gekentekende voertuigen (brandstof)
- Het kenteken wordt tijdens het typen automatisch in Nederlandse notatie
  gezet (streepjes op basis van de RDW-sidecodes).

## Keuring / inname + PDF

Na een geslaagde zoekopdracht verschijnt een keuringsformulier met o.a.:

- Schade (ja/nee, met omschrijving), velgschade (ja/nee, met omschrijving én
  eigen foto's), onderhoud (ja/nee, met omschrijving), datum en kilometerstand
  laatste onderhoud;
- Laadkabel, slotbout, werking airco;
- Bandenprofiel voor en achter (mm);
- **APK nodig?** — automatisch bepaald uit de RDW-vervaldatum;
- **Foto's toevoegen** — uit galerij of camera; deze worden in de PDF opgenomen.

Met **Download PDF** wordt een rapport (`keuring-<kenteken>.pdf`) gegenereerd met
de RDW-gegevens, de ingevulde controle én de foto's (6 per pagina). De PDF wordt volledig in de
browser gemaakt met [jsPDF](https://github.com/parallax/jsPDF) (lokaal
meegeleverd in `vendor/jspdf.umd.min.js`, geen CDN). Foto's worden **niet
geüpload** — alles blijft in de browser.

### jsPDF bijwerken

```bash
npm install jspdf
cp node_modules/jspdf/dist/jspdf.umd.min.js vendor/jspdf.umd.min.js
```

## Lokaal draaien

Omdat het een statische site is, volstaat elke webserver:

```bash
# Python
python3 -m http.server 8000
# of Node
npx serve .
```

Open daarna <http://localhost:8000>.

> Let op: bij openen via `file://` blokkeren sommige browsers de API-aanvraag
> (CORS). Gebruik daarom een lokale webserver.

## Gebruik

- Voer een Nederlands kenteken in (met of zonder streepjes) en klik op **Zoek**.
- Je kunt ook een kenteken via de URL meegeven: `?kenteken=XX999X`.
- Vul daarna het keuringsformulier in en klik op **Download PDF**.

## Publiceren (GitHub Pages)

De workflow in `.github/workflows/deploy-pages.yml` publiceert de site
automatisch naar GitHub Pages bij elke push naar `main`. Zet daarvoor eenmalig
in de repo-instellingen **Settings → Pages → Source** op **GitHub Actions**.

## Disclaimer

Aan de getoonde gegevens kunnen geen rechten worden ontleend. De brongegevens
zijn eigendom van de RDW.

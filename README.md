# Kenteken check

Een openbare pagina met een formulier dat basisgegevens van een voertuig
ophaalt op basis van het kenteken, via de [open data van de RDW](https://opendata.rdw.nl/).

## Hoe het werkt

- Statische site — alleen HTML, CSS en JavaScript, geen backend.
- De browser van de bezoeker roept rechtstreeks de openbare
  [SODA-API](https://dev.socrata.com/) van de RDW aan. Er is **geen
  API-sleutel** nodig.
- Gebruikte datasets:
  - `m9d7-ebf2` — Gekentekende voertuigen (algemene gegevens)
  - `8ys7-d773` — Gekentekende voertuigen (brandstof)

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

## Publiceren (GitHub Pages)

De workflow in `.github/workflows/deploy-pages.yml` publiceert de site
automatisch naar GitHub Pages bij elke push naar `main`. Zet daarvoor eenmalig
in de repo-instellingen **Settings → Pages → Source** op **GitHub Actions**.

## Disclaimer

Aan de getoonde gegevens kunnen geen rechten worden ontleend. De brongegevens
zijn eigendom van de RDW.

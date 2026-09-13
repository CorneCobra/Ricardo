# Hair by Simone — afsprakenapp

> Deze app staat tijdelijk in deze repo (map `kapsalon/`) naast de losstaande
> Kenteken check-app. Hij is bedoeld om later naar een eigen repository te
> verhuizen; er is geen enkele koppeling tussen de twee apps.

Een kleine webapp waarmee Simone haar afspraken, omzet, bankstortingen en
zakelijke kilometers bijhoudt. Mobiel-eerst gebouwd: bedoeld om op de telefoon
te gebruiken, tussen twee klanten door.

> **Let op — dit is een demo met proefgegevens.** Er is (nog) geen server en
> geen database. Bij het openen van de pagina wordt een startset met verzonnen
> klanten en afspraken geladen. Alles wat je invoert blijft alleen in dat ene
> browservenster staan en is na verversen weer weg.

## Wat kun je ermee?

**Afspraken** (startscherm)

Twee weergaven, met de schakelaar **Lijst / Dag** bovenin.

*Lijst* — alle komende afspraken, gegroepeerd per dag, met naam, behandeling,
tijdstip, duur, plaats en telefoonnummer (aantikken = bellen).

*Dag* — een tijdlijn van 08:00 tot 20:00 voor één dag, met pijltjes om te
bladeren. Afspraken staan als blokken op hun eigen tijd en hoogte; tik op een
vrije plek en de nieuwe-afspraakdialoog staat meteen op dat kwartier. Tik op
een blok voor omzet, verplaatsen of verwijderen.

In beide weergaven:

- Per afspraak zie je in één oogopslag de omzetstatus:
  - grijs — nog geen omzet geregistreerd;
  - oranje — bedrag bekend, nog niet betaald;
  - groen — betaald, met bank of cash erbij.
- **Omzet** registreren of corrigeren, **Verplaatsen** naar een andere dag of
  tijd (de afspraak krijgt dan het label *Verplaatst*) en **Verwijderen**.
- Met *Toon ook afgelopen afspraken* haal je de afgelopen dagen erbij, zodat je
  omzet van gisteren alsnog kunt invullen.
- **+ Nieuwe afspraak**: kies een bestaande klant of maak er direct een nieuwe
  aan. De plaats van de klant wordt automatisch overgenomen als locatie; met de
  knop *Salon* zet je de afspraak in de salon.
- **Botst het?** Bij inplannen en verplaatsen zie je welke afspraken al op die
  dag staan, krijg je knopjes met vrije tijdstippen, en volgt er een
  waarschuwing als je over een bestaande afspraak heen plant. Je kunt die
  waarschuwing negeren door nog een keer op Opslaan te klikken.

**Klanten**

Het lijstje dat op de achtergrond meegroeit. Naam, telefoonnummer, plaats, een
notitie en de afstand heen en terug in kilometers.

**Omzetstorting**

Bedrag en datum van een storting naar de bank, met het totaal van deze maand.

**Afsluiten (dagafsluiting)**

Kies een dag en zie wat die heeft opgeleverd: de omzet, gesplitst naar cash,
bank en nog openstaand, het aantal afspraken, de gereden kilometers en de
gewerkte uren. Die laatste twee worden berekend uit de afspraken van die dag —
kilometers uit de vaste afstand per klant (dezelfde klant twee keer op een dag
telt als één rit), uren uit de duur van de afspraken — en blijven corrigeerbaar
voor je de dag vastzet. Staat er nog een afspraak zonder omzet, dan waarschuwt
het scherm en kun je die omzet er meteen invullen. Een afgesloten dag kun je
heropenen om iets te corrigeren.

## Lokaal draaien

Het is een statische site, maar de code gebruikt JavaScript-modules — die
werken niet als je `index.html` rechtstreeks vanaf de schijf opent
(`file://`). Start dus een kleine webserver vanuit deze map:

```bash
cd kapsalon
# Python
python3 -m http.server 8000
# of Node
npx serve .
```

Open daarna <http://localhost:8000>.

## Publiceren (GitHub Pages)

De bestaande workflow in `.github/workflows/deploy-pages.yml` (in de hoofdmap
van de repo) publiceert de hele repo bij elke push naar `main`. Zodra deze map
op `main` staat, is de app bereikbaar op `<pages-url>/kapsalon/`.

## Opbouw van de code

Geen build-stap, geen framework, geen externe libraries.

```
index.html            één pagina met de vier tabbladen en alle dialogen
styles.css            opmaak; alle kleuren als CSS-variabelen bovenin
js/app.js             tabnavigatie en het opnieuw tekenen na een wijziging
js/data.js            de proefgegevens (datums relatief aan vandaag)
js/store.js           alle gegevens in het geheugen + alle wijzigingen
js/format.js          geld, datum, tijd en telefoon in Nederlandse notatie
js/ui.js              dialoog- en meldinghulpjes
js/views/*.js         één bestand per tabblad (afspraken, klanten,
                      stortingen, dagafsluiting)
```

Bedragen worden intern in hele centen bewaard, zodat totalen niet gaan
afwijken door afrondingen.

## Wat er nog niet in zit

Opslag die blijft bewaard, inloggen, echte routeberekening voor de kilometers,
koppeling met een agenda, herinneringen naar klanten, facturen en export naar de
boekhouding.

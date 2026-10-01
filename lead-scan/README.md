# Leadscan – Fase 1: Salesforce-fundament

Metadatapakket voor de testomgeving. Bevat de nieuwe velden, objecten, regels en rechten uit het solution design.

## Wat zit erin

| Onderdeel | Inhoud |
| --- | --- |
| Lead – nieuwe velden | Alleen `Scan_Score__c` (score 0-100, voor sorteren en het bijstellen van de drempel) en `Scan_Segment__c` (lookup, voor het leren per segment). Openingszin, signaal, bronnen, KvK-nummer en run staan in `Description`; alle details staan in het runrapport (zie fase 2). |
| Lead – validation rules | Scan_Reason_Unqualified_Required (reden verplicht bij Unqualified, alleen voor scan-leads) · Scan_Block_Convert_Placeholder_Name (geen conversie met achternaam 'Onbekend') |
| Scan_Segment__c | Zoeksegmenten met strategie, gewicht en conversiecijfers |
| Scan_Run__c | Eén record per run, met Run_Key__c als unieke sleutel (idempotent). Geen lookup op Lead: de leads van een run zijn te vinden via LeadSource + integratiegebruiker + Started/Finished |
| Lead_Scan_Setting__mdt | Uitschakelknop en limieten; record 'Default' (max 10 leads, min. score 70, max 15 zoekacties per kandidaat, max 240 min, 30% verkennen, max 20% gewichtswijziging, leren uit) |
| Queue | Claude Leads (Lead) |
| Matching rules | Lead: Company (fuzzy) OF Website (exact) · Account: Name (fuzzy) OF Website (exact) – bewust zonder achternaam |
| Duplicate rule | Lead_Scan_Block_Duplicates: blokkeert scan-leads die al als Lead of Account bestaan; geldt alleen voor LeadSource 'Claude Weekly Scan' en negeert sharing |
| Permission set | Lead_Scan_Integration voor de integratiegebruiker |

## Stap 1 – Handmatig vooraf in Setup (verplicht)

Picklistwaarden worden bewust niet via deploy gezet: een deploy van een bestaande picklist overschrijft alle (ook inactieve) waarden.

1. **Lead Source** (Object Manager > Lead > Lead Source): voeg de waarde `Claude Weekly Scan` toe. Controleer daarna of de waarde ook bij Account Source beschikbaar is; zo niet, voeg hem daar ook toe.
2. **Reason unqualified** (Lead > Reason_unqualified__c): voeg de waarde `Duplicate or existing customer` toe.
3. **Lead Settings**: zet *Require Validation for Converted Leads* aan. Zonder deze instelling werkt de conversieblokkade niet.

## Stap 2 – Deploy fundament

```bash
sf org login web --instance-url https://test.salesforce.com --alias cobra-test
sf project deploy start --manifest manifest/package-1-foundation.xml --target-org cobra-test --dry-run
sf project deploy start --manifest manifest/package-1-foundation.xml --target-org cobra-test
```

## Stap 3 – Wacht tot de matching rules actief zijn

Setup > Matching Rules: beide 'Scan'-regels moeten status **Active** hebben (Salesforce bouwt eerst een index, dat kan enkele minuten duren).

## Stap 4 – Deploy duplicate rule

```bash
sf project deploy start --manifest manifest/package-2-duplicate-rule.xml --target-org cobra-test
```

Fout over *sortOrder*? Er staan nu 3 (inactieve) duplicate rules op Lead, daarom is sortOrder 4 gezet. Pas dit aan naar het aantal bestaande Lead-regels + 1.

## Stap 5 – Handmatig na de deploy

1. **Queue Claude Leads**: leden toevoegen (de afgesproken eigenaar vanuit sales).
2. **Integratiegebruiker**: aanmaken (Salesforce Integration-licentie of API-only profiel) en permission set *Lead Scan Integration* toewijzen.
3. **Page layout Lead**: `Scan Score` en `Scan Segment` toevoegen (bijv. bij Lead Information); related list 'Leads' op Scan Segment. List view 'Claude Leads' op de queue, gesorteerd op Scan Score.
4. **Account Engagement**: controleer de sync-criteria, zodat leads met LeadSource 'Claude Weekly Scan' niet in marketingprogramma's terechtkomen.

## Controle na deploy

```bash
sf data query --target-org cobra-test --query "SELECT DeveloperName, IsActive FROM DuplicateRule WHERE SobjectType = 'Lead'"
sf data query --target-org cobra-test --query "SELECT DeveloperName, Max_Leads_Per_Run__c, Minimum_Score__c, Kill_Switch__c FROM Lead_Scan_Setting__mdt"
```

Go/no-go fase 1: alle onderdelen gedeployed, de drie handmatige voorbereidingen gedaan, en een testlead met LeadSource 'Claude Weekly Scan' voor een bestaand Account wordt geblokkeerd door de duplicate rule.

---

# Leadscan – Fase 2: de runner

Python-runner buiten Salesforce (GitHub Actions). Salesforce blijft de bron van waarheid; de runner is de enige component met credentials. Claude krijgt geen Salesforce-toegang en levert alleen JSON via een strikte tool, die de runner opnieuw valideert.

## Structuur

| Bestand | Doel |
| --- | --- |
| `runner/main.py` | Orkestratie van één run (`Run_Key__c` = ISO-week van de maandag, bv. `2026-W41`) |
| `runner/config.py` | Vastgepind model (`claude-opus-5-5`), constanten, `Lead_Scan_Setting__mdt` en `Scan_Segment__c` als dataclasses |
| `runner/salesforce.py` | JWT-login, queries, upsert `Scan_Run__c` op `Run_Key__c`, Composite insert zonder duplicate-override |
| `runner/exclusion.py` | Laag 1: uitsluitlijst (klanttypes, eerste gewonnen opportunity, hele Account-boom, Unqualified-leads) |
| `runner/matching.py` | Laag 2: domein, e-maildomein, KvK, genormaliseerde naam + aliassen; fuzzy = twijfelgeval |
| `runner/review_doubt.py` | Laag 3: Claude beoordeelt twijfelgevallen; alleen `different` mag door |
| `runner/discover.py` | Claude + web search per segment → kandidaten |
| `runner/research.py` | Claude als agent per kandidaat (web search + fetch) → verrijkte, gescoorde lead |
| `runner/verify_sources.py` | Domein bestaat (DNS) en elke bron-URL is bereikbaar; anders valt de lead af |
| `runner/allocate.py` | Bandit-verdeling van het zoekbudget (verkennen/benutten) |
| `runner/lead_mapping.py` | JSON → Lead- en Task-velden (code, geen oordeel) |
| `runner/slack.py` | Weekupdate (ingepland voor maandag 08:00), runrapport als bestand en directe foutmeldingen |
| `runner/report.py` | Runrapport per run (Markdown + JSON): elke kandidaat met besluit per laag, onderzoek, claims en bronnen |
| `runner/rollback.py` | Lead-Id's van één run (CSV) om terug te draaien |
| `runner/preflight.py` | Controle van koppelingen en fase 1-metadata, schrijft niets |
| `runner/seed_segments.py` + `data/segments.json` | Segmenten laden of bijwerken (startvoorstel: 9 segmenten) |
| `runner/learning.py` | Segmentcijfers bijwerken; reflectie en gewichtsaanpassing volgen in fase 6 |
| `runner/golden.py` + `tests/golden_set.json` | Gouden testset door de dubbelcheck (harde poort fase 3) |
| `runner/icp.py` | ICP-tekst en -versie (**v1-concept, nog vast te stellen door sales**) |
| `runner/industry_map.py` | Oude Industry-waarden → huidige picklist (`AMBIGUOUS` = beslissing nodig) |

## Pipeline per run

1. Instellingen lezen; kill switch aan → status *Stopped* + Slack, niets gedaan.
2. Bestaat de run al als *Completed* → niets doen (idempotent). *Failed*/*Running* → hervatten; al aangemaakte leads tellen mee voor het maximum.
3. Index opbouwen (Accounts, Contacts, open Leads) voor laag 1 en 2.
4. Zoekbudget verdelen (`DISCOVERY_SEARCH_BUDGET` = 60) en per segment ontdekken.
5. Elke kandidaat door laag 1-3. Laag 2-match met een niet-uitgesloten record → Task voor de eigenaar (geen lead).
6. Diep onderzoek per overgebleven kandidaat, daarna **opnieuw** laag 1-3 met de officiële naam, het eigen domein en het KvK-nummer.
7. Bronnencontrole, AVG-controle (geen e-mail/telefoon/LinkedIn-profielen), drempel `Minimum_Score__c`.
8. Kill switch opnieuw controleren, dan pas schrijven: top `Max_Leads_Per_Run__c` op score via Composite API (laag 4 = duplicate rule), daarna de Tasks.
9. Segmentcijfers bijwerken, `Scan_Run__c` op *Completed* met alle tellers en een log in `Errors__c`, runrapport en weekupdate naar Slack.

## Waar staat welke informatie?

| Waar | Wat | Voor wie |
| --- | --- | --- |
| Lead (Salesforce) | Bestaande velden + `Scan_Score__c` en `Scan_Segment__c`. In `Description`: openingszin, waarom nu, signaal, projectinschatting, score-onderbouwing, rol, KvK-nummer, CRM/partner, claims met bronnen en de run | Sales |
| `Scan_Run__c` (Salesforce) | Tellers per laag, model- en ICP-versie, log (`Errors__c`) | Beheer, het leren |
| Runrapport (Slack, bestand in #claude-leads) | Álle kandidaten, ook de afgevallen: besluit en reden per laag, volledige onderzoeksuitkomst, bronnencontrole | Beheer, kwaliteitscontrole, de maandelijkse reflectie |
| GitHub Actions-logs | Alleen aantallen | Iedereen (publieke repository) |

Het runrapport gaat bewust niet naar GitHub (artifact of log): de repository is publiek. De runner kan niet zelf in Claude Docs schrijven (dat vraagt een persoonlijke koppeling); op verzoek zet Claude een rapport uit Slack of Salesforce om in een document.

Harde limieten: zoekacties per kandidaat (search + fetch samen, ook over `pause_turn` heen), looptijd (`Max_Runtime_Minutes__c`, 10 minuten reserve om netjes af te ronden), maximum leads. Een fout halverwege → *Failed* + Slack, en er is niets weggeschreven (schrijven gebeurt pas aan het eind).

## Proefrun dubbelcheck (1 oktober 2026, testomgeving)

Uitgevoerd op een momentopname van de testomgeving (2.130 Accounts, 6.210 Contacts met e-mail, 4.690 open Leads), zonder schrijfacties:

| Controle | Resultaat |
| --- | --- |
| Gouden testset (49 gevallen) | 49/49 geslaagd |
| Elk uitgesloten record (1.642) per sleutel apart: naam, website, KvK, e-maildomein | 0 als nieuwe lead doorgelaten; alleen 20 records met een onzinnaam (`x`, `-`, `A`) hebben geen bruikbare sleutel |
| 50 bekende Nederlandse organisaties uit de kernbranches | 43 staan al in Salesforce en worden tegengehouden (5 laag 1, 38 laag 2 → Task), 3 twijfelgevallen, 4 nieuw |

Bevindingen die tot aanpassingen leidden: korte namen van twee letters werden genegeerd; e-maildomeinen van leads en contactpersonen blokkeerden hele hogescholen; `LastModifiedDate` is door een massa-update onbruikbaar als datum van diskwalificeren.

## Terugdraaien per run

```bash
python -m runner.rollback --run-key 2026-W41   # schrijft out/rollback-2026-W41.csv met Lead-Id's
```

Verwijderen doet een beheerder met Data Loader (Delete) of Setup > Mass Delete Records. De integratiegebruiker heeft bewust geen verwijderrechten.

## Lokaal draaien

```bash
cd lead-scan
pip install -r requirements-dev.txt
python -m pytest -q                       # unit tests (geen netwerk nodig)

export ANTHROPIC_API_KEY=... SF_USERNAME=... SF_CONSUMER_KEY=... SF_PRIVATE_KEY="$(cat server.key)"
export SF_DOMAIN=test                      # altijd de testomgeving
python -m runner.golden tests/golden_set.json            # gouden testset, laag 3 conservatief
python -m runner.golden tests/golden_set.json --with-claude
python -m runner.main --dry-run --dedup-only --no-slack --run-key 2026-W41-proef   # fase 3: niets schrijven
python -m runner.main --dry-run --no-slack                                          # volledige run, rapport in out/
```

## GitHub Actions

`.github/workflows/lead-scan.yml` draait zondag 22:07 (twee UTC-crons voor zomer- en wintertijd) en handmatig met de keuze `preflight`, `dry-run-dedup`, `dry-run`, `golden-set` of `run`. `.github/workflows/lead-scan-tests.yml` draait lint en tests bij elke wijziging in `lead-scan/`.

Inrichten (Settings → Environments → `lead-scan`):

| Soort | Naam | Inhoud |
| --- | --- | --- |
| Secret | `ANTHROPIC_API_KEY` | API-key (met budgetalert in de Anthropic Console) |
| Secret | `SF_USERNAME` | Gebruikersnaam van de integratiegebruiker (testomgeving) |
| Secret | `SF_CONSUMER_KEY` | Consumer key van de Connected App (JWT) |
| Secret | `SF_PRIVATE_KEY` | Private key (PEM) bij het certificaat van de Connected App |
| Secret | `SLACK_BOT_TOKEN` | Bottoken van de Slack-app (`chat:write`, `files:write`), lid van #claude-leads |
| Variable | `SF_DOMAIN` | `test` (standaard). Alleen na expliciet akkoord op `login` zetten |
| Variable | `SLACK_CHANNEL` | Kanaal-Id van #claude-leads (bijv. `C0123ABCD`); nodig voor het uploaden van het runrapport. Een naam werkt alleen met de extra scope `channels:read` |
| Repo-variable | `LEAD_SCAN_ENABLED` | `true` zet de geplande run aan; zonder deze variabele draaien alleen handmatige runs |

Geplande workflows draaien alleen vanaf de standaardbranch.

## Inrichting koppelingen (stap voor stap)

Volgorde: fase 1 deployen → koppelingen inrichten → `preflight` → segmenten laden → gouden testset → proefrun dubbelcheck.

1. **Certificaat voor de JWT-login** (lokaal, eenmalig):
   ```bash
   openssl req -x509 -newkey rsa:2048 -nodes -keyout server.key -out server.crt -days 730 -subj "/CN=cobra-leadscan"
   ```
   `server.key` is geheim en hoort alleen in het GitHub-secret `SF_PRIVATE_KEY`, nooit in de repository.
2. **Connected App** (of External Client App) in de testomgeving:
   - OAuth aan, callback `http://localhost:1717/OauthRedirect`;
   - *Use digital signatures* met `server.crt`; JWT Bearer Flow toegestaan;
   - scopes: *Manage user data via APIs (api)* en *Perform requests at any time (refresh_token, offline_access)*;
   - *Permitted Users*: "Admin approved users are pre-authorized", en de permission set *Lead Scan Integration* (of het profiel van de integratiegebruiker) toevoegen.
   - Consumer key → secret `SF_CONSUMER_KEY`; gebruikersnaam van de integratiegebruiker → secret `SF_USERNAME`.
3. **Slack-app** (api.slack.com/apps → Create New App → From scratch):
   - Bot Token Scopes: `chat:write` en `files:write`;
   - installeren in de workspace, de bot uitnodigen in #claude-leads (`/invite @<app>`);
   - Bot User OAuth Token (`xoxb-…`) → secret `SLACK_BOT_TOKEN`; kanaal-Id (kanaaldetails → Over) → variable `SLACK_CHANNEL`.
4. **Anthropic API-key**: in de Console een aparte key voor de leadscan met een maandlimiet en budgetalert → secret `ANTHROPIC_API_KEY`.
5. **GitHub**: environment `lead-scan` met de secrets en variables uit de tabel hierboven. Handmatige runs verschijnen pas als de workflow op de standaardbranch staat.
6. **Controleren**: workflow-modus `preflight` (of lokaal `python -m runner.preflight`). Alles moet OK zijn; "LET OP" bij de duplicate rule betekent alleen dat de integratiegebruiker die niet mag lezen.
7. **Segmenten laden** na akkoord van sales op het startvoorstel:
   ```bash
   python -m runner.seed_segments data/segments.json           # toont wat er gebeurt
   python -m runner.seed_segments data/segments.json --apply   # maakt aan of werkt bij op naam
   ```
8. **Fase 3**: workflow-modus `golden-set`, daarna `dry-run-dedup`.

## Bewuste keuzes en aandachtspunten

- **Model**: `claude-opus-5-5`, adaptive thinking, effort `high`, met server-side fallback (`fallbacks: "default"`) bij een weigering door de veiligheidsclassifiers. Web search/fetch: `web_search_20260209` / `web_fetch_20260209`. Wisselen alleen na een geslaagde gouden testset.
- **Strikter dan het ontwerp op twee punten**: de *hele* Account-boom van een klant valt af (ook zusterorganisaties), en elke bron-URL moet bereikbaar zijn (een 401/403/429 telt als bestaand, want veel sites weren bots).
- **E-maildomeinen**: de testomgeving maskeert e-mail met `.invalid`; dat wordt gestript. Eigen domeinen (`OWN_DOMAINS`) en domeinen die bij 5 of meer Account-bomen voorkomen zijn geen sleutel. E-maildomeinen zijn rommelig (een lead met het e-mailadres van een hogeschool, contactpersonen van een andere onderwijsinstelling bij een klant). Een match op alleen het e-maildomein telt daarom hard als het domein bij de naam van het record past (`domain_fits_name`); anders wordt het een twijfelgeval voor laag 3.
- **"Laatste 12 maanden Unqualified"** gebruikt de statusgeschiedenis (LeadHistory). Dekt die de periode niet (in de testomgeving begint ze op 12-08-2026, dezelfde dag als een massa-update van 1.155 leads), dan geldt `LastModifiedDate` als strenge benadering. In productie opnieuw controleren.
- **Permission set**: `Lead.Email` (lezen) toegevoegd, nodig voor de e-maildomeinmatching. Controleer bij de dry-run-deploy of de integratiegebruiker ook City/Country op Lead mag vullen.
- **Lookalikes**: het segment met signaaltype Lookalike krijgt de klanten met een gewonnen opportunity in de laatste 12 maanden mee (naam, branche, website; maximaal 15). Dat zijn organisatiegegevens die naar de Claude API gaan, net als de records die laag 3 vergelijkt.
- **Signaaltype**: staat niet op Lead. Geef elk segment één `Signal_Type__c`; de runner accepteert dan alleen kandidaten met dat signaal, zodat het leren per signaal via het segment loopt.
- **Publieke repository**: code, workflow en logs zijn openbaar. Daarom geen klantnamen in tests of documentatie (alleen fictieve voorbeelden), geen details in de Actions-logs (`LEADSCAN_QUIET_LOGS=1`) en geen runrapport als artifact.
- **Sub_Industry__c** is afhankelijk van Industry; de runner vult alleen bekende combinaties (`SUB_INDUSTRY_BY_INDUSTRY`). De koppeling van *Sociaal Ontwikkelbedrijf* nog controleren.
- **Tasks** gaan alleen naar een eigenaar die een gebruiker is; staat een bestaande lead in een queue, dan wordt dat gelogd.
- De gouden testset bevat alleen record-Id's; `runner/golden.py` haalt namen, websites en KvK live op, zodat er geen klantenlijst in de repository staat.

# Leadscan – Fase 1: Salesforce-fundament

Metadatapakket voor de testomgeving. Bevat de nieuwe velden, objecten, regels en rechten uit het solution design.

## Wat zit erin

| Onderdeel | Inhoud |
| --- | --- |
| Lead – nieuwe velden | Scan_Score__c, Scan_Signal__c, Scan_Opening_Line__c, Scan_Sources__c, Chamber_of_Commerce_Number__c, Scan_ICP_Version__c, Scan_Run__c, Scan_Segment__c |
| Lead – validation rules | Scan_Reason_Unqualified_Required (reden verplicht bij Unqualified, alleen voor scan-leads) · Scan_Block_Convert_Placeholder_Name (geen conversie met achternaam 'Onbekend') |
| Scan_Segment__c | Zoeksegmenten met strategie, gewicht en conversiecijfers |
| Scan_Run__c | Eén record per run, met Run_Key__c als unieke sleutel (idempotent) |
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

1. **Lead field mapping** (Lead > Fields > Map Lead Fields): `Chamber_of_Commerce_Number__c` → Account `Chamber of Commerce Number`.
2. **Queue Claude Leads**: leden toevoegen (de afgesproken eigenaar vanuit sales).
3. **Integratiegebruiker**: aanmaken (Salesforce Integration-licentie of API-only profiel) en permission set *Lead Scan Integration* toewijzen.
4. **Page layout Lead**: sectie 'Leadscan' met de nieuwe velden; related list 'Leads' op Scan Run en Scan Segment.
5. **Account Engagement**: controleer de sync-criteria, zodat leads met LeadSource 'Claude Weekly Scan' niet in marketingprogramma's terechtkomen.

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
| `runner/slack.py` | Weekupdate (ingepland voor maandag 08:00) en directe foutmeldingen |
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
9. Segmentcijfers bijwerken, `Scan_Run__c` op *Completed* met alle tellers en een log in `Errors__c`, Slack-weekupdate.

Harde limieten: zoekacties per kandidaat (search + fetch samen, ook over `pause_turn` heen), looptijd (`Max_Runtime_Minutes__c`, 10 minuten reserve om netjes af te ronden), maximum leads. Een fout halverwege → *Failed* + Slack, en er is niets weggeschreven (schrijven gebeurt pas aan het eind).

## Lokaal draaien

```bash
cd lead-scan
pip install -r requirements-dev.txt
python -m pytest -q                       # unit tests (geen netwerk nodig)

export ANTHROPIC_API_KEY=... SF_USERNAME=... SF_CONSUMER_KEY=... SF_PRIVATE_KEY="$(cat server.key)"
export SF_DOMAIN=test                      # altijd de testomgeving
python -m runner.golden tests/golden_set.json            # gouden testset, laag 3 conservatief
python -m runner.golden tests/golden_set.json --with-claude
python -m runner.main --dry-run --dedup-only --run-key 2026-W41-proef   # fase 3: niets schrijven
python -m runner.main --dry-run                                          # volledige run, niets schrijven
```

## GitHub Actions

`.github/workflows/lead-scan.yml` draait zondag 22:07 (twee UTC-crons voor zomer- en wintertijd) en handmatig met de keuze `dry-run-dedup`, `dry-run`, `golden-set` of `run`. `.github/workflows/lead-scan-tests.yml` draait lint en tests bij elke wijziging in `lead-scan/`.

Inrichten (Settings → Environments → `lead-scan`):

| Soort | Naam | Inhoud |
| --- | --- | --- |
| Secret | `ANTHROPIC_API_KEY` | API-key (met budgetalert in de Anthropic Console) |
| Secret | `SF_USERNAME` | Gebruikersnaam van de integratiegebruiker (testomgeving) |
| Secret | `SF_CONSUMER_KEY` | Consumer key van de Connected App (JWT) |
| Secret | `SF_PRIVATE_KEY` | Private key (PEM) bij het certificaat van de Connected App |
| Secret | `SLACK_BOT_TOKEN` | Bottoken van de Slack-app (`chat:write`), lid van #claude-leads |
| Variable | `SF_DOMAIN` | `test` (standaard). Alleen na expliciet akkoord op `login` zetten |
| Variable | `SLACK_CHANNEL` | `#claude-leads` (standaard) |
| Repo-variable | `LEAD_SCAN_ENABLED` | `true` zet de geplande run aan; zonder deze variabele draaien alleen handmatige runs |

Geplande workflows draaien alleen vanaf de standaardbranch.

## Bewuste keuzes en aandachtspunten

- **Model**: `claude-opus-5-5`, adaptive thinking, effort `high`, met server-side fallback (`fallbacks: "default"`) bij een weigering door de veiligheidsclassifiers. Web search/fetch: `web_search_20260209` / `web_fetch_20260209`. Wisselen alleen na een geslaagde gouden testset.
- **Strikter dan het ontwerp op twee punten**: de *hele* Account-boom van een klant valt af (ook zusterorganisaties), en elke bron-URL moet bereikbaar zijn (een 401/403/429 telt als bestaand, want veel sites weren bots).
- **E-maildomeinen**: de testomgeving maskeert e-mail met `.invalid`; dat wordt gestript. Eigen domeinen (`OWN_DOMAINS`) en domeinen die bij 5 of meer Account-bomen voorkomen (adviesbureaus, leveranciers) zijn geen sleutel. Contactpersonen met het domein van een andere organisatie (bv. een ROC-medewerker met een Saxion-adres) maken die andere organisatie ook uitgesloten; dat is bewust streng.
- **"Laatste 12 maanden Unqualified"** gebruikt `LastModifiedDate`, omdat er geen veldgeschiedenis op Status is. Dat sluit eerder te veel uit dan te weinig.
- **Permission set**: `Lead.Email` (lezen) toegevoegd, nodig voor de e-maildomeinmatching. Controleer bij de dry-run-deploy of de integratiegebruiker ook City/Country op Lead mag vullen.
- **Sub_Industry__c** is afhankelijk van Industry; de runner vult alleen bekende combinaties (`SUB_INDUSTRY_BY_INDUSTRY`). De koppeling van *Sociaal Ontwikkelbedrijf* nog controleren.
- **Tasks** gaan alleen naar een eigenaar die een gebruiker is; staat een bestaande lead in een queue, dan wordt dat gelogd.
- De gouden testset bevat alleen record-Id's; `runner/golden.py` haalt namen, websites en KvK live op, zodat er geen klantenlijst in de repository staat.

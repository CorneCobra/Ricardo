"""Ideal Customer Profile (ICP) waartegen Claude scoort.

Elke wijziging krijgt een nieuwe versie; de versie gaat mee naar
Lead.Scan_ICP_Version__c en Scan_Run__c.ICP_Version__c. Vanaf fase 6 stelt de
maandelijkse reflectie wijzigingen voor; oude versies blijven hier bewaard.

LET OP: v1 is een concept op basis van de koude start (klantverdeling in de
testomgeving). Het initiële ICP is nog een open punt en moet door sales worden
vastgesteld voordat fase 4 start.
"""

ICP_VERSION = "v1-concept"

ICP_TEXT = """\
Cobra CRM is een Nederlandse Salesforce-partner. Wij implementeren en beheren
Salesforce voor organisaties die hun relaties (leden, donateurs, studenten,
klanten) professioneel willen beheren.

Kernbranches (op basis van huidige klanten):
1. Nonprofit: goede doelen, fondsenwervers, ledenorganisaties, verenigingen,
   vakbonden, stichtingen met donateurs of leden.
2. Onderwijs: mbo, hbo, universiteiten en onderwijsgroepen (studentrelaties,
   werving, alumni, bedrijfsrelaties).
3. Manufacturing: productiebedrijven met een sales- of serviceorganisatie
   en dealer- of distributeursnetwerk.
Overige branches (financiële dienstverlening, consultancy, woningcorporaties,
energie) zijn kansrijk bij een sterk signaal.

Organisatiegrootte: bij voorkeur 50 tot 5.000 medewerkers, of een
ledenbestand/donateursbestand van minimaal 10.000 relaties.
Regio: Nederland (hoofdkantoor of grote vestiging in Nederland), daarna België.

Sterke signalen, van sterk naar minder sterk:
- Vacature waarin CRM, Salesforce, klantcontact-systemen of een CRM-functioneel
  beheerder/product owner wordt genoemd.
- Aanbesteding of marktconsultatie voor CRM, relatiebeheer of een
  ledenadministratie (TenderNed).
- Fusie of overname waardoor systemen moeten samengaan.
- Reorganisatie of nieuw meerjarenplan met nadruk op digitalisering of
  klant-/ledenbeleving.
- Snelle groei (nieuwe vestigingen, veel nieuwe medewerkers, financiering).

Negatieve signalen (lage score):
- Organisatie heeft net (minder dan 12 maanden geleden) een nieuw CRM ingevoerd.
- Organisatie is zelf een CRM-leverancier, Salesforce-partner of
  implementatiepartner (concurrent).
- Eenmanszaak of minder dan 10 medewerkers.
- Geen Nederlandse of Belgische aanwezigheid.

Scoringsrichtlijn (0-100):
- 85-100: kernbranche, passende grootte en een recent, concreet CRM-signaal.
- 70-84: passend profiel met een duidelijk signaal, of kernbranche met een
  indirect signaal.
- 40-69: twijfelachtig profiel of zwak/oud signaal.
- 0-39: past niet bij het ICP.
"""

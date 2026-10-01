"""Diep onderzoek: Claude als agent per kandidaat, levert een verrijkte lead op."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from . import config
from .claude_agent import UNTRUSTED_CONTENT_RULES, run_agent
from .icp import ICP_TEXT, ICP_VERSION
from .schemas import CRM_VALUES, ENRICHED_LEAD_SCHEMA, INDUSTRY_VALUES, SUB_INDUSTRY_BY_INDUSTRY, pii_violations

log = logging.getLogger(__name__)

SYSTEM = f"""\
Je bent een grondige B2B-analist voor Cobra CRM (Salesforce-partner). Je onderzoekt
één organisatie en beoordeelt hoe kansrijk die is als nieuwe klant.

Ideal Customer Profile (versie {ICP_VERSION}):
{ICP_TEXT}
{UNTRUSTED_CONTENT_RULES}"""

PROMPT = """\
Onderzoek deze kandidaat (data uit de ontdekfase):
{candidate_json}

Onderzoek met web search en web fetch: de eigen website, vacatures, nieuws,
jaarverslag, het huidige CRM-systeem, een eventuele huidige Salesforce-partner,
de organisatiegrootte, de vestigingsplaats van het hoofdkantoor en het
KvK-nummer (8 cijfers; laat leeg als je het niet met een bron kunt vinden).

Lever daarna één verrijkte lead aan:
- industry: precies één van: {industries}.
- sub_industry: alleen invullen als het past; toegestaan per industry: {sub_industries}.
- current_crm: één van: {crms}. Kies "Overig" voor een ander systeem (noem het in
  project_estimate) en null als je het niet weet.
- current_sf_partner: naam van de huidige Salesforce-partner, alleen als de
  organisatie al Salesforce gebruikt en je de partner met een bron vond.
- why_now: één zin (max 255 tekens) waarom juist nu contact zinvol is.
- project_estimate: inschatting van het mogelijke CRM-project.
- contact_role: de rol om te benaderen (bijv. "Manager Ledenservice"), nooit een naam.
- opening_line: voorgestelde openingszin voor sales (max 255 tekens), zonder namen.
- score: 0-100 tegen het ICP, volgens de scoringsrichtlijn. Wees streng.
- score_rationale: korte onderbouwing van de score.
- claims: elke feitelijke bewering die je gebruikt (signaal, grootte, CRM,
  partner, KvK) met de bron-URL waar je die zelf hebt gezien.
- Velden die je niet met een bron kunt onderbouwen: null.
- Je hebt maximaal {searches} zoek- en fetchacties. Dien in vóór je budget op is.

Dien je resultaat in via de tool submit_lead."""


@dataclass
class ResearchOutcome:
    lead: dict | None
    seen_urls: set[str] = field(default_factory=set)
    errors: list[str] = field(default_factory=list)


def research(client, candidate: dict, max_searches: int, deadline: config.Deadline | None) -> ResearchOutcome:
    candidate_json = json.dumps(
        {k: candidate[k] for k in ("company_name", "domain", "signal_type", "signal_summary", "source_urls")},
        ensure_ascii=False,
        indent=2,
    )
    result = run_agent(
        client,
        system=SYSTEM,
        prompt=PROMPT.format(
            candidate_json=candidate_json,
            industries=", ".join(INDUSTRY_VALUES),
            sub_industries=json.dumps(SUB_INDUSTRY_BY_INDUSTRY, ensure_ascii=False),
            crms=", ".join(CRM_VALUES),
            searches=max_searches,
        ),
        submit_name="submit_lead",
        submit_description="Lever de verrijkte en gescoorde lead aan.",
        schema=ENRICHED_LEAD_SCHEMA,
        max_searches=max_searches,
        deadline=deadline,
    )
    outcome = ResearchOutcome(lead=None, seen_urls=result.seen_urls, errors=list(result.errors))
    if result.data is None:
        return outcome
    pii = pii_violations(result.data)
    if pii:
        outcome.errors.append("AVG-controle: " + "; ".join(pii))
        return outcome
    outcome.lead = result.data
    return outcome

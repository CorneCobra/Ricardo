"""Ontdekken: Claude zoekt per segment organisaties met een concreet koopsignaal."""

from __future__ import annotations

import json
import logging

from . import config
from .claude_agent import UNTRUSTED_CONTENT_RULES, run_agent
from .icp import ICP_TEXT
from .schemas import CANDIDATE_SCHEMA, CANDIDATES_TOOL_SCHEMA, pii_violations, validate

log = logging.getLogger(__name__)

SYSTEM = f"""\
Je bent een zorgvuldige B2B-researcher voor Cobra CRM. Je zoekt op het open web naar
organisaties met een concreet, recent koopsignaal voor een CRM-traject.

Ideal Customer Profile:
{ICP_TEXT}
{UNTRUSTED_CONTENT_RULES}"""

PROMPT = """\
Zoek organisaties voor dit segment.

Segment (data uit Salesforce):
{segment_json}

Opdracht:
- Gebruik web search om organisaties te vinden met een concreet signaal dat bij
  het segment past: een vacature waarin CRM/Salesforce/klantcontact genoemd wordt,
  een fusie, reorganisatie, aanbesteding (TenderNed), snelle groei of een
  vergelijkbare organisatie als een bestaande klant (lookalike).
- Alleen signalen van de afgelopen 6 maanden. Alleen organisaties met
  aanwezigheid in Nederland of België.
- Kwaliteit boven aantal: lever maximaal {max_candidates} kandidaten, alleen als
  het signaal concreet en met een bron te onderbouwen is. Nul kandidaten is een
  geldig antwoord.
- Je hebt in totaal maximaal {searches} zoekacties. Dien in vóór je budget op is.
- Per kandidaat: officiële organisatienaam, eigen websitedomein (bijv.
  voorbeeld.nl, geen vacaturesite of social media), signaaltype, een korte
  samenvatting van het signaal en de bron-URL's waar je het signaal zag.
- Zet segment_id op "{segment_id}".

Dien je resultaat in via de tool submit_candidates."""


def discover(client, segment: config.Segment, searches: int, deadline: config.Deadline | None) -> tuple[list[dict], list[str]]:
    """Kandidaten voor één segment, plus fouten/afgewezen items voor het runlog."""
    segment_json = json.dumps(
        {
            "name": segment.name,
            "target_industry": segment.target_industry,
            "signal_type": segment.signal_type,
            "search_strategy": segment.search_strategy,
        },
        ensure_ascii=False,
        indent=2,
    )
    result = run_agent(
        client,
        system=SYSTEM,
        prompt=PROMPT.format(
            segment_json=segment_json,
            max_candidates=config.MAX_CANDIDATES_PER_SEGMENT,
            searches=searches,
            segment_id=segment.id,
        ),
        submit_name="submit_candidates",
        submit_description="Lever de gevonden kandidaten aan. Een lege lijst is toegestaan.",
        schema=CANDIDATES_TOOL_SCHEMA,
        max_searches=searches,
        deadline=deadline,
        use_fetch=False,
    )
    notes = [f"Segment {segment.name}: {e}" for e in result.errors]
    if result.data is None:
        return [], notes

    candidates = []
    for item in result.data["candidates"][: config.MAX_CANDIDATES_PER_SEGMENT]:
        item["segment_id"] = segment.id  # nooit vertrouwen op wat het model invult
        problems = validate(item, CANDIDATE_SCHEMA) + pii_violations(item)
        if problems:
            notes.append(f"Kandidaat {item.get('company_name')!r} verworpen: {'; '.join(problems)}")
            continue
        candidates.append(item)
    return candidates, notes

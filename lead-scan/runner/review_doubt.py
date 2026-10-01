"""Laag 3: Claude beoordeelt twijfelgevallen (naam lijkt op een bestaand record).

Alleen het oordeel 'different' laat de kandidaat door. Elk ander oordeel, een
fout of een ongeldig antwoord betekent: kandidaat valt af.
"""

from __future__ import annotations

import json

from . import config
from .claude_agent import UNTRUSTED_CONTENT_RULES, AgentError, run_agent
from .matching import MatchResult
from .schemas import DOUBT_SCHEMA

SYSTEM = f"""\
Je beoordeelt of twee organisatierecords over dezelfde organisatie gaan. Je bent
streng: bij twijfel kies je 'unsure'.
{UNTRUSTED_CONTENT_RULES}"""

PROMPT = """\
Nieuwe kandidaat:
{candidate_json}

Bestaande records in ons CRM die erop lijken:
{existing_json}

Is de kandidaat dezelfde organisatie als een van de bestaande records, een moeder-
of dochterorganisatie daarvan, een fusiepartner, of echt een andere organisatie?
Je mag web search gebruiken om dit te controleren (maximaal {searches} keer).

Kies verdict:
- same_organisation: dezelfde organisatie (ook bij andere schrijfwijze of oude naam).
- parent_or_subsidiary: moeder, dochter of zusterorganisatie.
- merger_partner: (voorgenomen) fusie of overname met een bestaand record.
- different: aantoonbaar een andere, niet-verbonden organisatie.
- unsure: je kunt het niet met zekerheid zeggen.

Dien je oordeel in via de tool submit_verdict."""

DOUBT_SEARCHES = 3


def review(client, candidate: dict, match: MatchResult, deadline: config.Deadline | None) -> tuple[bool, str]:
    """(mag_door, toelichting)."""
    candidate_json = json.dumps(
        {k: candidate.get(k) for k in ("company_name", "domain", "kvk_number", "city", "signal_summary")},
        ensure_ascii=False,
        indent=2,
    )
    existing_json = json.dumps([m.record.summary() for m in match.matches], ensure_ascii=False, indent=2)
    try:
        result = run_agent(
            client,
            system=SYSTEM,
            prompt=PROMPT.format(candidate_json=candidate_json, existing_json=existing_json, searches=DOUBT_SEARCHES),
            submit_name="submit_verdict",
            submit_description="Lever je oordeel over de twee records aan.",
            schema=DOUBT_SCHEMA,
            max_searches=DOUBT_SEARCHES,
            deadline=deadline,
            use_fetch=False,
        )
    except AgentError as exc:
        return False, f"laag 3 fout, kandidaat valt af: {exc}"
    if result.data is None:
        return False, "laag 3 zonder geldig oordeel: " + "; ".join(result.errors)
    verdict, rationale = result.data["verdict"], result.data["rationale"]
    return verdict == "different", f"{verdict}: {rationale}"

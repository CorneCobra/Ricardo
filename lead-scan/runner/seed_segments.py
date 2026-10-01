"""Segmenten laden of bijwerken uit een JSON-bestand (bijv. het goedgekeurde startvoorstel).

    python -m runner.seed_segments data/segments.json           # toont wat er zou gebeuren
    python -m runner.seed_segments data/segments.json --apply   # maakt aan of werkt bij op Name

Alleen de velden uit het bestand worden gezet; de conversiecijfers (Leads_Created__c
e.d.) blijven van de runner.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys

from . import config
from .main import configure_logging
from .salesforce import SalesforceClient
from .schemas import INDUSTRY_VALUES, SIGNAL_TYPES

log = logging.getLogger("leadscan.seed")

FIELDS = ["Name", "Target_Industry__c", "Signal_Type__c", "Search_Strategy__c", "Weight__c", "Active__c",
          "Exploration__c"]


def validate_segments(segments: list[dict]) -> list[str]:
    problems = []
    names = [s.get("Name") for s in segments]
    if len(names) != len(set(names)):
        problems.append("dubbele segmentnamen")
    for s in segments:
        name = s.get("Name") or "?"
        if not s.get("Name") or len(s["Name"]) > 80:
            problems.append(f"{name}: Name ontbreekt of is langer dan 80 tekens")
        if s.get("Signal_Type__c") not in SIGNAL_TYPES:
            problems.append(f"{name}: onbekend signaaltype {s.get('Signal_Type__c')!r}")
        if s.get("Target_Industry__c") not in (None, *INDUSTRY_VALUES):
            problems.append(f"{name}: {s.get('Target_Industry__c')!r} is geen actieve Industry-waarde")
        if not s.get("Search_Strategy__c"):
            problems.append(f"{name}: zoekstrategie ontbreekt")
        if not 0 <= float(s.get("Weight__c") or 0) <= 100:
            problems.append(f"{name}: gewicht buiten 0-100")
    active = [s for s in segments if s.get("Active__c", True) and not s.get("Exploration__c")]
    total = sum(float(s.get("Weight__c") or 0) for s in active)
    if active and abs(total - 100) > 0.01:
        problems.append(f"gewichten van de actieve, niet-verkennende segmenten tellen op tot {total:g} in plaats van 100")
    return problems


def plan(segments: list[dict], existing: list[dict]) -> list[tuple[str, str | None, dict]]:
    """[(actie, Id, velden)] met actie 'create' of 'update'."""
    by_name = {e["Name"]: e["Id"] for e in existing}
    steps = []
    for s in segments:
        fields = {k: s.get(k) for k in FIELDS if k in s}
        seg_id = by_name.get(s["Name"])
        steps.append(("update", seg_id, fields) if seg_id else ("create", None, fields))
    return steps


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scan_Segment__c laden uit JSON")
    parser.add_argument("path")
    parser.add_argument("--apply", action="store_true", help="echt aanmaken/bijwerken (anders alleen tonen)")
    args = parser.parse_args(argv)
    configure_logging()

    segments = json.load(open(args.path, encoding="utf-8"))["segments"]
    problems = validate_segments(segments)
    if problems:
        for p in problems:
            log.error(p)
        return 1
    sf = SalesforceClient.login(config.Env.load())
    for action, seg_id, fields in plan(segments, sf.all_segments()):
        log.info("%s %s", action, fields["Name"])
        if args.apply:
            if action == "create":
                sf.create_segment(fields)
            else:
                sf.update_segment(seg_id, {k: v for k, v in fields.items() if k != "Name"})
    if not args.apply:
        log.info("Niets gewijzigd; voeg --apply toe om door te voeren")
    return 0


if __name__ == "__main__":
    sys.exit(main())

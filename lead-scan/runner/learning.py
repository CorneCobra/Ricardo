"""Leren van uitkomsten.

Nu (fase 2): elke run telt per segment de uitkomsten van eerdere scan-leads en
schrijft die naar Scan_Segment__c. Dat is puur tellen, zonder oordeel; de
bandit-verdeling (allocate.py) gebruikt deze cijfers pas als Learning_Enabled__c
aan staat.

Later (fase 6): gewichten bijstellen (max Max_Weight_Change__c per maand) en de
maandelijkse reflectie door Claude op het ICP. Nog niet gebouwd.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

OUTCOME_SOQL = (
    "SELECT Scan_Segment__c, Status, IsConverted, ConvertedOpportunityId, ConvertedOpportunity.IsWon "
    "FROM Lead WHERE Scan_Segment__c != null"
)


def compute_segment_metrics(leads: list[dict], now: datetime | None = None) -> dict[str, dict]:
    counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for lead in leads:
        c = counts[lead["Scan_Segment__c"]]
        c["created"] += 1
        if lead.get("IsConverted") or lead.get("Status") in ("Qualified", "Converted"):
            c["qualified"] += 1
        if lead.get("Status") == "Unqualified":
            c["unqualified"] += 1
        if lead.get("ConvertedOpportunityId"):
            c["opps"] += 1
            if (lead.get("ConvertedOpportunity") or {}).get("IsWon"):
                c["won"] += 1

    stamp = (now or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        seg_id: {
            "Leads_Created__c": c["created"],
            "Leads_Qualified__c": c["qualified"],
            "Leads_Unqualified__c": c["unqualified"],
            "Opportunities_Created__c": c["opps"],
            "Deals_Won__c": c["won"],
            # Gestuurd op gewonnen deals per lead.
            "Conversion_Rate__c": round(100.0 * c["won"] / c["created"], 2) if c["created"] else 0,
            "Last_Evaluated__c": stamp,
        }
        for seg_id, c in counts.items()
    }


def update_segment_metrics(sf) -> int:
    metrics = compute_segment_metrics(sf.query_all(OUTCOME_SOQL))
    for seg_id, fields in metrics.items():
        sf.update_segment(seg_id, fields)
    return len(metrics)

"""Runrapport: alle details per kandidaat, buiten Salesforce.

Op Lead staan alleen de velden die sales en het leren nodig hebben. Al het andere
(besluit per laag, volledige onderzoeksuitkomst, claims met bronnen, bronnencontrole)
komt in dit rapport. Het gaat als bestand naar het private Slack-kanaal en niet naar
GitHub: de repository is publiek, en logs en artifacts zijn daar voor iedereen te zien.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime


STAT_LABELS = {
    "Candidates_Found__c": "Kandidaten gevonden",
    "Blocked_Layer_1__c": "Tegengehouden laag 1 (uitsluitlijst)",
    "Blocked_Layer_2__c": "Tegengehouden laag 2 (bestaand record)",
    "Blocked_Layer_3__c": "Tegengehouden laag 3 (twijfelgeval)",
    "Blocked_Layer_4__c": "Tegengehouden laag 4 (duplicate rule)",
    "Below_Threshold__c": "Onder de drempel",
    "Signals_To_Existing__c": "Tasks voor bestaande eigenaren",
    "Leads_Created__c": "Leads aangemaakt",
}


@dataclass
class Entry:
    company_name: str
    domain: str | None
    segment: str
    signal_type: str
    signal_summary: str
    source_urls: list[str]
    result: str = "in behandeling"
    steps: list[str] = field(default_factory=list)
    research: dict | None = None
    lead_id: str | None = None


class RunReport:
    def __init__(self, run_key: str, dry_run: bool, model: str, icp_version: str):
        self.run_key = run_key
        self.dry_run = dry_run
        self.model = model
        self.icp_version = icp_version
        self.entries: list[Entry] = []
        self.warnings: list[str] = []
        self.started: datetime | None = None
        self.finished: datetime | None = None
        self.stats: dict = {}
        self.segment_budget: dict[str, int] = {}

    def add(self, candidate: dict, segment_name: str) -> int:
        """Registreer een kandidaat; het volgnummer gaat mee als candidate['_report']."""
        self.entries.append(
            Entry(
                company_name=candidate["company_name"],
                domain=candidate.get("domain"),
                segment=segment_name,
                signal_type=candidate["signal_type"],
                signal_summary=candidate["signal_summary"],
                source_urls=list(candidate.get("source_urls", [])),
            )
        )
        return len(self.entries) - 1

    def _entry(self, candidate: dict) -> Entry | None:
        idx = candidate.get("_report")
        return self.entries[idx] if idx is not None and idx < len(self.entries) else None

    def step(self, candidate: dict, text: str, result: str | None = None) -> None:
        entry = self._entry(candidate)
        if entry:
            entry.steps.append(text)
            if result:
                entry.result = result

    def research(self, candidate: dict, lead: dict) -> None:
        entry = self._entry(candidate)
        if entry:
            entry.research = lead

    def created(self, candidate: dict, lead_id: str | None) -> None:
        entry = self._entry(candidate)
        if entry:
            entry.lead_id = lead_id
            entry.result = "lead aangemaakt" if lead_id else "lead (proefrun, niet aangemaakt)"

    # ---- uitvoer ------------------------------------------------------------

    def to_json(self) -> str:
        return json.dumps(
            {
                "run_key": self.run_key,
                "dry_run": self.dry_run,
                "model": self.model,
                "icp_version": self.icp_version,
                "started": self.started.isoformat() if self.started else None,
                "finished": self.finished.isoformat() if self.finished else None,
                "stats": self.stats,
                "segment_budget": self.segment_budget,
                "warnings": self.warnings,
                "candidates": [e.__dict__ for e in self.entries],
            },
            ensure_ascii=False,
            indent=2,
        )

    def to_markdown(self) -> str:
        title = f"# Leadscan {self.run_key}" + (" (proefrun, niets weggeschreven)" if self.dry_run else "")
        lines = [title, ""]
        if self.started:
            end = f" – {self.finished:%H:%M}" if self.finished else ""
            lines.append(f"Run {self.started:%Y-%m-%d %H:%M}{end} · model {self.model} · ICP {self.icp_version}")
        if self.stats:
            lines.append("")
            lines += [f"- {STAT_LABELS.get(k, k)}: {v}" for k, v in self.stats.items()]
        if self.segment_budget:
            lines.append("")
            lines.append("Zoekbudget: " + ", ".join(f"{k} {v}" for k, v in self.segment_budget.items()))
        if self.warnings:
            lines.append("")
            lines += [f"> Let op: {w}" for w in self.warnings]

        order = {"lead aangemaakt": 0, "lead (proefrun, niet aangemaakt)": 0}
        for entry in sorted(self.entries, key=lambda e: (order.get(e.result, 1), -(e.research or {}).get("score", -1))):
            lines += ["", f"## {entry.company_name} ({entry.domain or 'geen domein'}) — {entry.result}"]
            lines.append(f"Segment: {entry.segment} · signaal {entry.signal_type}: {entry.signal_summary}")
            if entry.lead_id:
                lines.append(f"Lead: {entry.lead_id}")
            lines += [f"- {s}" for s in entry.steps]
            r = entry.research
            if r:
                lines += [
                    "",
                    f"**Score {r['score']}** – {r['score_rationale']}",
                    f"- Waarom nu: {r['why_now']}",
                    f"- Openingszin: {r['opening_line']}",
                    f"- Rol: {r['contact_role']} · branche {r['industry']} · {r.get('city') or '?'}, {r.get('country') or '?'}",
                    f"- KvK: {r.get('kvk_number') or '–'} · medewerkers: {r.get('employees_estimate') or '–'}"
                    f" · CRM: {r.get('current_crm') or '–'} · SF-partner: {r.get('current_sf_partner') or '–'}",
                    f"- Project: {r['project_estimate']}",
                    "- Onderbouwing:",
                ]
                lines += [f"  - {c['claim']} ({c['source_url']})" for c in r["claims"]]
            elif entry.source_urls:
                lines.append("- Bronnen signaal: " + ", ".join(entry.source_urls))
        return "\n".join(lines) + "\n"

import json
from datetime import datetime

from runner.report import RunReport

from test_schemas import enriched


def cand(name, domain):
    return {"company_name": name, "domain": domain, "signal_type": "Vacancy", "signal_summary": "vacature",
            "source_urls": [f"https://{domain}/v"], "segment_id": "S1"}


def test_report_tracks_every_candidate():
    r = RunReport("2026-W41", dry_run=False, model="m", icp_version="v1")
    r.started = datetime(2026, 10, 4, 22, 7)
    a, b = cand("Fonds A", "a.nl"), cand("Fonds B", "b.nl")
    a["_report"] = r.add(a, "Nonprofit")
    b["_report"] = r.add(b, "Nonprofit")
    r.step(b, "L1 tegengehouden: domain=b.nl", "laag 1: uitgesloten")
    r.research(a, enriched(company_name="Fonds A", score=88))
    r.created(a, "00Q1")
    r.stats = {"Leads_Created__c": 1}
    md = r.to_markdown()
    assert md.index("Fonds A") < md.index("Fonds B")  # aangemaakte leads eerst
    assert "lead aangemaakt" in md and "Lead: 00Q1" in md and "**Score 88**" in md
    assert "laag 1: uitgesloten" in md and "L1 tegengehouden" in md
    data = json.loads(r.to_json())
    assert data["candidates"][0]["lead_id"] == "00Q1" and data["candidates"][1]["result"] == "laag 1: uitgesloten"


def test_dry_run_label():
    r = RunReport("2026-W41", dry_run=True, model="m", icp_version="v1")
    c = cand("Fonds A", "a.nl")
    c["_report"] = r.add(c, "S")
    r.created(c, None)
    md = r.to_markdown()
    assert "(proefrun, niets weggeschreven)" in md and "lead (proefrun, niet aangemaakt)" in md


def test_unknown_candidate_is_ignored():
    r = RunReport("k", False, "m", "v")
    r.step({"company_name": "X"}, "tekst")  # geen _report: geen fout
    assert r.entries == []

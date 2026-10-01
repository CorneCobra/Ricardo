import json
from datetime import datetime, timedelta

from runner import config
from runner.config import Segment, Settings
from runner.main import Pipeline
from runner.salesforce import InsertResult
from runner.verify_sources import Verification

from fakes import FakeClaude, FakeNotifier, response, search_result, tool_use
from test_schemas import enriched

TZ = config.TIMEZONE
NOW = datetime(2026, 10, 4, 22, 0, tzinfo=TZ)


class FakeSF:
    instance_url = "https://cobra--test.my.salesforce.com"

    def __init__(self, settings=None, run=None, duplicate_companies=(), accounts=None, leads=None):
        self._settings = settings or Settings()
        self.run = run
        self.duplicate_companies = set(duplicate_companies)
        self.accounts = accounts or []
        self.leads = leads or []
        self.upserts, self.inserted, self.tasks, self.segment_updates = [], [], [], []

    def settings(self):
        return self._settings

    def get_run(self, key):
        return self.run

    def scan_leads_between(self, started, finished=None):
        self.lead_window = (started, finished)
        return [{"Id": "00Q_old"}]

    def upsert_run(self, key, fields):
        self.upserts.append(fields)
        return "a0R1"

    def query_all(self, soql):
        if "FROM Account" in soql:
            return self.accounts
        if "FROM Contact" in soql:
            return []
        if "FROM LeadHistory" in soql:
            return []
        if "Scan_Segment__c != null" in soql:
            return [{"Scan_Segment__c": "SEG1", "Status": "New"}]
        if "FROM Lead" in soql:
            return self.leads
        raise AssertionError(soql)

    def active_segments(self):
        return [Segment(id="SEG1", name="Nonprofit vacatures", target_industry="Nonprofit", signal_type="Vacancy",
                        search_strategy="CRM-vacatures bij goede doelen", weight=100, exploration=False)]

    def recent_won_customers(self):
        return [{"name": "Fictief Fonds", "industry": "Nonprofit"}]

    def queue_id(self):
        return "00GQ"

    def partner_account_id(self, name):
        return None

    def insert_leads(self, records):
        self.inserted += records
        return [InsertResult(i, None if r["Company"] in self.duplicate_companies else f"00Q{i}",
                             r["Company"] in self.duplicate_companies,
                             ["DUPLICATES_DETECTED: x"] if r["Company"] in self.duplicate_companies else [])
                for i, r in enumerate(records)]

    def create_task(self, fields):
        self.tasks.append(fields)
        return "00T1"

    def update_segment(self, seg_id, fields):
        self.segment_updates.append((seg_id, fields))


def cand(name, domain):
    return {"company_name": name, "domain": domain, "signal_type": "Vacancy",
            "signal_summary": f"{name} zoekt een CRM-beheerder", "source_urls": [f"https://{domain}/vacature"],
            "segment_id": "x"}


CANDIDATES = [
    cand("Nieuw Fonds", "nieuwfonds.nl"),
    cand("Tweede Fonds", "tweedefonds.nl"),
    cand("De Zilvermeeuw", "zilvermeeuw.nl"),  # klant -> laag 1
    cand("Vastgoedpartners Oost", "vastgoedpartnersoost.nl"),  # prospect -> laag 2 + Task
    cand("Laag Fonds", "laagfonds.nl"),  # onder drempel
]
SCORES = {"Nieuw Fonds": 88, "Tweede Fonds": 75, "Laag Fonds": 40}


def handler(kwargs):
    names = {t.get("name") for t in kwargs["tools"]}
    if "submit_candidates" in names:
        return response([tool_use("submit_candidates", {"candidates": json.loads(json.dumps(CANDIDATES))})],
                        searches=4)
    if "submit_lead" in names:
        prompt = kwargs["messages"][0]["content"]
        name = next(n for n in SCORES if n in prompt)
        domain = name.lower().replace(" ", "") + ".nl"
        lead = enriched(company_name=name, domain=domain, kvk_number=None, score=SCORES[name],
                        claims=[{"claim": "vacature", "source_url": f"https://{domain}/vacature"}])
        return response([search_result(f"https://{domain}/vacature"), tool_use("submit_lead", lead)], searches=3)
    raise AssertionError(names)


# Fictieve organisaties.
ACCOUNTS = [
    {"Id": "001K", "Name": "Stichting De Zilvermeeuw", "Type": "Customer", "Website": "https://www.zilvermeeuw.nl/",
     "OwnerId": "005A"},
    {"Id": "001P", "Name": "Vastgoedpartners Oost", "Type": "Prospect", "Website": "https://vastgoedpartnersoost.nl/",
     "OwnerId": "005B"},
]


def ok_verifier(lead, cand, seen):
    return Verification(ok=True)


def pipeline(sf, claude=None, **kw):
    notifier = FakeNotifier()
    p = Pipeline(sf, claude or FakeClaude(handler=handler), notifier, run_key="2026-W41", clock=lambda: NOW,
                 verifier=kw.pop("verifier", ok_verifier), report_dir=kw.pop("report_dir", None), **kw)
    return p, notifier


def test_full_run_writes_qualified_leads_and_tasks():
    sf = FakeSF(accounts=ACCOUNTS)
    p, notifier = pipeline(sf, scheduled=True)
    assert p.run() == 0
    assert [r["Company"] for r in sf.inserted] == ["Nieuw Fonds", "Tweede Fonds"]  # gesorteerd op score
    assert all(r["OwnerId"] == "00GQ" for r in sf.inserted)
    assert all(r["Scan_Segment__c"] == "SEG1" for r in sf.inserted)  # nooit het model vertrouwen
    # Nieuw op Lead zijn alleen Scan_Score__c en Scan_Segment__c.
    assert all({k for k in r if k.startswith("Scan_")} == {"Scan_Score__c", "Scan_Segment__c"} for r in sf.inserted)
    assert "run 2026-W41" in sf.inserted[0]["Description"]
    assert len(sf.tasks) == 1 and sf.tasks[0]["WhatId"] == "001P"
    final = sf.upserts[-1]
    assert final["Status__c"] == "Completed"
    assert final["Candidates_Found__c"] == 5
    assert final["Blocked_Layer_1__c"] == 1 and final["Blocked_Layer_2__c"] == 1
    assert final["Below_Threshold__c"] == 1 and final["Leads_Created__c"] == 2
    assert final["Signals_To_Existing__c"] == 1
    assert sf.segment_updates and sf.segment_updates[0][0] == "SEG1"
    assert notifier.weekly_calls[0]["schedule"] is True
    assert [lead["company_name"] for lead in notifier.weekly_calls[0]["top"]] == ["Nieuw Fonds", "Tweede Fonds"]
    # Runrapport: elke kandidaat met zijn uitkomst, als bestand naar Slack.
    report = notifier.uploads[0]["content"]
    assert "Nieuw Fonds (nieuwfonds.nl) — lead aangemaakt" in report
    assert "De Zilvermeeuw (zilvermeeuw.nl) — laag 1: uitgesloten" in report
    assert "Laag Fonds (laagfonds.nl) — onder drempel" in report
    assert "Task aangemaakt" in report


def test_max_leads_per_run_is_enforced():
    sf = FakeSF(settings=Settings(max_leads_per_run=1), accounts=ACCOUNTS)
    p, _ = pipeline(sf)
    p.run()
    assert [r["Company"] for r in sf.inserted] == ["Nieuw Fonds"]


def test_duplicate_rule_block_counts_as_layer4():
    sf = FakeSF(accounts=ACCOUNTS, duplicate_companies={"Tweede Fonds"})
    p, _ = pipeline(sf)
    p.run()
    final = sf.upserts[-1]
    assert final["Blocked_Layer_4__c"] == 1 and final["Leads_Created__c"] == 1


def test_kill_switch_stops_immediately():
    sf = FakeSF(settings=Settings(kill_switch=True))
    claude = FakeClaude(handler=handler)
    p, notifier = pipeline(sf, claude)
    assert p.run() == 0
    assert sf.upserts[-1]["Status__c"] == "Stopped"
    assert claude.calls == [] and sf.inserted == []
    assert notifier.errors and "uitschakelknop" in notifier.errors[0]


def test_kill_switch_turned_on_mid_run_writes_nothing():
    sf = FakeSF(accounts=ACCOUNTS)
    calls = {"n": 0}

    def settings():
        calls["n"] += 1
        return Settings(kill_switch=calls["n"] > 1)

    sf.settings = settings
    p, _ = pipeline(sf)
    p.run()
    assert sf.inserted == [] and sf.tasks == []
    assert sf.upserts[-1]["Status__c"] == "Stopped"


def test_completed_run_is_not_repeated():
    sf = FakeSF(run={"Id": "a0R1", "Status__c": "Completed"})
    claude = FakeClaude(handler=handler)
    p, _ = pipeline(sf, claude)
    assert p.run() == 0
    assert sf.upserts == [] and claude.calls == []


def test_resumed_run_counts_existing_leads_toward_maximum():
    run = {"Id": "a0R1", "Status__c": "Failed", "Started__c": "2026-10-04T20:07:00.000+0000"}
    sf = FakeSF(settings=Settings(max_leads_per_run=2), run=run, accounts=ACCOUNTS)
    p, _ = pipeline(sf)
    p.run()
    assert len(sf.inserted) == 1  # 1 bestaand + 1 nieuw = maximum 2
    assert sf.upserts[-1]["Leads_Created__c"] == 2
    # Oorspronkelijke starttijd blijft: daarmee worden de leads van deze run gevonden.
    assert sf.lead_window[0] == run["Started__c"]
    assert sf.upserts[0]["Started__c"] == run["Started__c"]


def test_dry_run_writes_nothing_to_salesforce_but_reports(tmp_path):
    sf = FakeSF(accounts=ACCOUNTS)
    p, notifier = pipeline(sf, dry_run=True, report_dir=tmp_path)
    assert p.run() == 0
    assert sf.upserts == [] and sf.inserted == [] and sf.tasks == [] and sf.segment_updates == []
    assert notifier.weekly_calls and notifier.weekly_calls[0]["schedule"] is False
    assert "proefrun" in notifier.uploads[0]["content"]
    assert "Task zou worden aangemaakt" in notifier.uploads[0]["content"]
    assert (tmp_path / "leadscan-2026-W41.md").exists() and (tmp_path / "leadscan-2026-W41.json").exists()


def test_dedup_only_skips_research():
    sf = FakeSF(accounts=ACCOUNTS)
    claude = FakeClaude(handler=handler)
    p, _ = pipeline(sf, claude, dry_run=True, dedup_only=True)
    p.run()
    assert all("submit_lead" not in {t.get("name") for t in c["tools"]} for c in claude.calls)


def test_unreachable_sources_drop_the_lead():
    sf = FakeSF(accounts=ACCOUNTS)
    p, _ = pipeline(sf, verifier=lambda lead, cand, seen: Verification(ok=False, problems=["bron onbereikbaar"]))
    p.run()
    assert sf.inserted == []
    assert "bronnen afgekeurd" in sf.upserts[-1]["Errors__c"]


def test_claude_failure_marks_run_failed_and_writes_nothing():
    from runner.claude_agent import AgentError

    def broken(kwargs):
        raise AgentError("Claude API onbereikbaar")

    sf = FakeSF(accounts=ACCOUNTS)
    p, notifier = pipeline(sf, FakeClaude(handler=broken))
    assert p.run() == 1
    assert sf.upserts[-1]["Status__c"] == "Failed" and sf.inserted == [] and sf.tasks == []
    assert "Claude API" in notifier.errors[0]


def test_runtime_limit_stops_cleanly_and_still_writes():
    sf = FakeSF(accounts=ACCOUNTS)
    t = {"now": NOW}
    claude_calls = {"n": 0}

    def slow_handler(kwargs):
        claude_calls["n"] += 1
        t["now"] = t["now"] + timedelta(minutes=120)  # elke aanroep kost twee uur
        return handler(kwargs)

    notifier = FakeNotifier()
    p = Pipeline(sf, FakeClaude(handler=slow_handler), notifier, run_key="2026-W41", clock=lambda: t["now"],
                 verifier=ok_verifier, report_dir=None)
    assert p.run() == 0
    assert sf.upserts[-1]["Status__c"] == "Completed"
    assert "looptijd" in sf.upserts[-1]["Errors__c"]
    assert any("looptijd" in w for w in notifier.weekly_calls[0]["warnings"])

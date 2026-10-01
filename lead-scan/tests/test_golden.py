import json
from pathlib import Path

from runner.golden import build_candidate, evaluate
from runner.matching import ExistingRecord, MatchIndex

GOLDEN = Path(__file__).with_name("golden_set.json")


def test_golden_set_file_is_well_formed():
    doc = json.loads(GOLDEN.read_text(encoding="utf-8"))
    ids = [c["id"] for c in doc["cases"]]
    assert len(ids) == len(set(ids))
    for c in doc["cases"]:
        assert c["expected"] in ("blocked", "pass")
        assert c.get("record_id") or c.get("company_name")
        assert c["variant"] in ("as_is", "name_only", "legal_form", "typo", "website_only", "email_domain", "kvk_only")
    kinds = {c["kind"] for c in doc["cases"]}
    assert {"customer", "customer_hierarchy", "prospect", "open_lead", "control"} <= kinds


def test_build_candidate_variants():
    rec = {"Name": "Zonnebloem", "Website": "https://www.zonnebloem.nl", "Chamber_of_Commerce_Number__c": "41149287"}
    assert build_candidate({"variant": "website_only"}, rec, [])["domain"] == "zonnebloem.nl"
    assert build_candidate({"variant": "kvk_only"}, rec, [])["kvk_number"] == "41149287"
    assert build_candidate({"variant": "typo"}, rec, [])["company_name"] == "Znonebloem"
    assert build_candidate({"variant": "email_domain"}, rec, []) is None
    assert build_candidate({"variant": "email_domain"}, rec, ["zonnebloem.nl"])["domain"] == "zonnebloem.nl"


def test_evaluate_reports_misses():
    index = MatchIndex([ExistingRecord("001K", "Account", "Zonnebloem", excluded=True, domains={"zonnebloem.nl"})])
    records = {"001K": ({"Name": "Zonnebloem", "Website": "zonnebloem.nl"}, []),
               "001X": ({"Name": "Totaal Onbekend", "Website": None}, [])}
    cases = [
        {"id": "a", "record_id": "001K", "variant": "website_only", "expected": "blocked"},
        {"id": "b", "record_id": "001K", "variant": "typo", "expected": "blocked"},
        {"id": "c", "record_id": "001X", "variant": "name_only", "expected": "blocked"},  # gemist
        {"id": "d", "kind": "control", "variant": "as_is", "company_name": "Kwartelkoning", "domain": "kk.nl",
         "expected": "pass"},
    ]
    results = {r["id"]: r for r in evaluate(index, cases, lambda rid: records[rid])}
    assert results["a"]["ok"] and results["b"]["ok"] and results["d"]["ok"]
    assert results["b"]["outcome"] == "blocked_l3"
    assert not results["c"]["ok"]

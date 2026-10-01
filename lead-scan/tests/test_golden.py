import json
from pathlib import Path

from runner.golden import build_candidate, evaluate, report_markdown
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
    rec = {"Name": "Zilvermeeuw", "Website": "https://www.zilvermeeuw.nl", "Chamber_of_Commerce_Number__c": "01234567"}
    assert build_candidate({"variant": "website_only"}, rec, [])["domain"] == "zilvermeeuw.nl"
    assert build_candidate({"variant": "kvk_only"}, rec, [])["kvk_number"] == "01234567"
    assert build_candidate({"variant": "typo"}, rec, [])["company_name"] == "Zlivermeeuw"
    assert build_candidate({"variant": "email_domain"}, rec, []) is None
    assert build_candidate({"variant": "email_domain"}, rec, ["zilvermeeuw.nl"])["domain"] == "zilvermeeuw.nl"


def test_evaluate_reports_misses():
    index = MatchIndex([ExistingRecord("001K", "Account", "Zilvermeeuw", excluded=True, domains={"zilvermeeuw.nl"})])
    records = {"001K": ({"Name": "Zilvermeeuw", "Website": "zilvermeeuw.nl"}, []),
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


def test_report_markdown():
    results = [{"id": "a", "variant": "name_only", "expected": "blocked", "outcome": "clear", "ok": False,
                "candidate": {"company_name": "X | Y", "domain": None, "kvk_number": None}, "reason": "r|s"}]
    md = report_markdown(results, False)
    assert md.startswith("# Gouden testset dubbelcheck: 0/1 geslaagd") and "❌" in md and "r/s" in md

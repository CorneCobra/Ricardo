"""Gouden testset door de dubbelcheck (harde poort na fase 3).

De testset bevat alleen Salesforce record-Id's en het soort geval; namen,
websites, KvK-nummers en e-maildomeinen worden live uit de testomgeving gehaald.
Zo staat er geen klantenlijst in de repository.

Per geval wordt een kandidaat opgebouwd volgens een variant (bijv. alleen de
website, alleen het e-maildomein, een andere rechtsvorm) en door laag 1-3
gestuurd. Zonder --with-claude telt een twijfelgeval (laag 3) als
tegengehouden, net als 'bij twijfel valt af' in de echte run.

    python -m runner.golden tests/golden_set.json [--with-claude]

Exitcode 1 zodra één geval anders uitvalt dan verwacht.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys

from . import config, exclusion, review_doubt
from .matching import MatchIndex, email_domain, normalize_domain, normalize_kvk
from .salesforce import SalesforceClient, _soql_quote

log = logging.getLogger("golden")

NONSENSE_NAME = "Qwzx Onbestaande Testorganisatie"


def build_candidate(case: dict, record: dict | None, email_domains: list[str]) -> dict | None:
    """Kandidaat voor één geval, of None als het record de benodigde sleutel mist."""
    variant = case["variant"]
    if case.get("company_name"):  # controlegeval met vaste, fictieve gegevens
        return {"company_name": case["company_name"], "domain": case.get("domain"), "kvk_number": None}
    name = record.get("Name") or record.get("Company") or ""
    website = normalize_domain(record.get("Website"))
    kvk = normalize_kvk(record.get("Chamber_of_Commerce_Number__c"))
    if variant == "as_is":
        return {"company_name": name, "domain": website, "kvk_number": kvk}
    if variant == "name_only":
        return {"company_name": name, "domain": None, "kvk_number": None}
    if variant == "legal_form":
        return {"company_name": f"Stichting {name} B.V.", "domain": None, "kvk_number": None}
    if variant == "typo":
        # Eén letter verwisseld in het langste woord: moet minimaal een twijfelgeval worden.
        words = name.split()
        i = max(range(len(words)), key=lambda j: len(words[j]))
        w = words[i]
        if len(w) >= 4:
            words[i] = w[:1] + w[2] + w[1] + w[3:]
        return {"company_name": " ".join(words), "domain": None, "kvk_number": None}
    if variant == "website_only":
        return {"company_name": NONSENSE_NAME, "domain": website, "kvk_number": None} if website else None
    if variant == "email_domain":
        return {"company_name": NONSENSE_NAME, "domain": email_domains[0], "kvk_number": None} if email_domains else None
    if variant == "kvk_only":
        return {"company_name": NONSENSE_NAME, "domain": None, "kvk_number": kvk} if kvk else None
    raise ValueError(f"Onbekende variant {variant}")


def fetch_record(sf: SalesforceClient, record_id: str) -> tuple[dict | None, list[str]]:
    rid = _soql_quote(record_id)
    if record_id.startswith("001"):
        recs = sf.query_all(
            f"SELECT Id, Name, Website, Type, Chamber_of_Commerce_Number__c FROM Account WHERE Id = '{rid}'"
        )
        emails = sf.query_all(f"SELECT Email FROM Contact WHERE AccountId = '{rid}' AND Email != null LIMIT 50")
    else:
        recs = sf.query_all(f"SELECT Id, Company, Website, Email, Status FROM Lead WHERE Id = '{rid}'")
        emails = recs
    domains = []
    for e in emails:
        d = email_domain(e.get("Email"))
        if d and d not in domains:
            domains.append(d)
    return (recs[0] if recs else None), domains


def evaluate(index: MatchIndex, cases: list[dict], fetch, claude=None) -> list[dict]:
    results = []
    for case in cases:
        record, domains = (None, []) if case.get("company_name") else fetch(case["record_id"])
        if record is None and not case.get("company_name"):
            results.append({**case, "outcome": "record_not_found", "ok": False, "reason": "record bestaat niet"})
            continue
        cand = build_candidate(case, record, domains)
        if cand is None:
            results.append({**case, "outcome": "skipped", "ok": True, "reason": "sleutel ontbreekt op record"})
            continue
        match = index.check(cand["company_name"], cand["domain"], cand["kvk_number"])
        outcome, reason = match.outcome, match.reason
        if outcome == "doubt":
            if claude is None:
                outcome = "blocked_l3"
                reason = "twijfelgeval (zonder Claude conservatief tegengehouden) | " + reason
            else:
                allowed, why = review_doubt.review(claude, cand, match, None)
                outcome, reason = ("clear" if allowed else "blocked_l3"), f"{why} | {reason}"
        blocked = outcome.startswith("blocked")
        ok = blocked if case["expected"] == "blocked" else not blocked
        results.append({**case, "candidate": cand, "outcome": outcome, "ok": ok, "reason": reason})
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Gouden testset door de dubbelcheck")
    parser.add_argument("path")
    parser.add_argument("--with-claude", action="store_true", help="twijfelgevallen echt door laag 3 (Claude)")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    env = config.Env.load()
    sf = SalesforceClient.login(env)
    claude = None
    if args.with_claude:
        import anthropic

        claude = anthropic.Anthropic(max_retries=4)
    cases = json.load(open(args.path, encoding="utf-8"))["cases"]
    index = exclusion.build_index(sf)
    results = evaluate(index, cases, lambda rid: fetch_record(sf, rid), claude)

    failed = [r for r in results if not r["ok"]]
    for r in results:
        mark = "OK  " if r["ok"] else "FOUT"
        log.info("%s %-28s %-12s verwacht %-7s -> %-16s %s", mark, r["id"], r["variant"], r["expected"],
                 r["outcome"], r.get("reason", ""))
    log.info("%d/%d geslaagd", len(results) - len(failed), len(results))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

"""Preflight: staan alle koppelingen en de fase 1-metadata goed? Schrijft niets.

    python -m runner.preflight

Controleert de Salesforce-login (JWT), dat het een sandbox is, de instellingen,
queue, segmenten, picklistwaarden, de twee Lead-velden, de duplicate rule, de
statusgeschiedenis, de Slack-app en de Anthropic API-key. Exitcode 1 bij een fout.
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass

from . import config
from .main import configure_logging
from .salesforce import SalesforceClient

log = logging.getLogger("leadscan.preflight")

OK, WARN, FAIL = "OK", "LET OP", "FOUT"


@dataclass
class Check:
    name: str
    status: str
    detail: str = ""


def _picklist_values(describe: dict, field: str) -> set[str]:
    for f in describe.get("fields", []):
        if f["name"] == field:
            return {v["value"] for v in f.get("picklistValues", []) if v.get("active")}
    return set()


def salesforce_checks(sf: SalesforceClient, domain: str) -> list[Check]:
    checks: list[Check] = []

    def run(name, fn):
        try:
            checks.append(fn())
        except Exception as exc:  # elke controle apart; één fout stopt de rest niet
            checks.append(Check(name, FAIL, f"{exc.__class__.__name__}: {str(exc)[:200]}"))

    def org():
        rec = sf.query_all("SELECT IsSandbox FROM Organization")[0]
        if rec["IsSandbox"]:
            return Check("Omgeving", OK, "sandbox (testomgeving)")
        return Check("Omgeving", FAIL if domain == "test" else WARN,
                     "PRODUCTIE – alleen na expliciet akkoord gebruiken")

    def settings():
        s = sf.settings()
        status = WARN if s.kill_switch else OK
        return Check("Lead_Scan_Setting__mdt", status,
                     f"kill switch {'AAN' if s.kill_switch else 'uit'}, max {s.max_leads_per_run} leads, "
                     f"drempel {s.minimum_score}")

    def queue():
        sf.queue_id()
        return Check("Queue Claude Leads", OK)

    def segments():
        segs = sf.active_segments()
        if not segs:
            return Check("Scan_Segment__c", FAIL, "geen actieve segmenten (laad data/segments.json)")
        exploit = [s for s in segs if not s.exploration]
        total = sum(s.weight for s in exploit)
        status = OK if not exploit or abs(total - 100) < 0.01 else WARN
        return Check("Scan_Segment__c", status, f"{len(segs)} actief, gewichten samen {total:g}%")

    def lead_describe():
        d = sf.sf.Lead.describe()
        problems = []
        if config.LEAD_SOURCE not in _picklist_values(d, "LeadSource"):
            problems.append(f"LeadSource mist '{config.LEAD_SOURCE}'")
        if "Duplicate or existing customer" not in _picklist_values(d, "Reason_unqualified__c"):
            problems.append("Reason unqualified mist 'Duplicate or existing customer'")
        fields = {f["name"]: f for f in d.get("fields", [])}
        for name in ("Scan_Score__c", "Scan_Segment__c"):
            if name not in fields or not fields[name].get("createable"):
                problems.append(f"{name} ontbreekt of is niet schrijfbaar voor de integratiegebruiker")
        return Check("Lead (picklists en velden)", FAIL if problems else OK, "; ".join(problems))

    def duplicate_rule():
        try:
            rules = sf.query_all(
                "SELECT DeveloperName, IsActive FROM DuplicateRule WHERE DeveloperName = 'Lead_Scan_Block_Duplicates'"
            )
        except Exception:
            # Duplicate rules lezen vraagt 'View Setup'; dat heeft de integratiegebruiker bewust niet.
            return Check("Duplicate rule", WARN, "niet leesbaar voor de integratiegebruiker; controleer in Setup")
        if not rules:
            return Check("Duplicate rule", FAIL, "Lead_Scan_Block_Duplicates niet gevonden")
        return Check("Duplicate rule", OK if rules[0]["IsActive"] else FAIL,
                     "actief" if rules[0]["IsActive"] else "niet actief")

    def history():
        sf.query_all("SELECT Id FROM LeadHistory WHERE Field = 'Status' LIMIT 1")
        return Check("Statusgeschiedenis Lead", OK)

    run("Omgeving", org)
    run("Lead_Scan_Setting__mdt", settings)
    run("Queue Claude Leads", queue)
    run("Scan_Segment__c", segments)
    run("Lead (picklists en velden)", lead_describe)
    run("Duplicate rule", duplicate_rule)
    run("Statusgeschiedenis Lead", history)
    return checks


def slack_check(env: config.Env, client=None) -> Check:
    if not env.slack_token:
        return Check("Slack", WARN, "geen SLACK_BOT_TOKEN: berichten en rapporten worden overgeslagen")
    try:
        from slack_sdk import WebClient

        web = client or WebClient(token=env.slack_token)
        web.auth_test()
        from .slack import Notifier

        channel_id = Notifier(env.slack_token, env.slack_channel, client=web).channel_id()
        if not channel_id:
            return Check("Slack", FAIL, f"kanaal {env.slack_channel} niet gevonden; gebruik het kanaal-Id")
        web.conversations_info(channel=channel_id)
        return Check("Slack", OK, f"kanaal {channel_id}")
    except Exception as exc:
        return Check("Slack", FAIL, f"{exc.__class__.__name__}: {str(exc)[:200]}")


def anthropic_check(client=None) -> Check:
    try:
        import anthropic

        client = client or anthropic.Anthropic()
        client.models.retrieve(config.MODEL)
        return Check("Anthropic API", OK, f"model {config.MODEL} beschikbaar")
    except Exception as exc:
        return Check("Anthropic API", FAIL, f"{exc.__class__.__name__}: {str(exc)[:200]}")


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    try:
        env = config.Env.load()
    except RuntimeError as exc:
        log.error("%s %s", FAIL, exc)
        return 1
    checks: list[Check] = []
    try:
        sf = SalesforceClient.login(env)
        checks.append(Check("Salesforce-login (JWT)", OK))
        checks += salesforce_checks(sf, env.sf_domain)
    except Exception as exc:
        checks.append(Check("Salesforce-login (JWT)", FAIL, f"{exc.__class__.__name__}: {str(exc)[:200]}"))
    checks.append(slack_check(env))
    checks.append(anthropic_check())

    for c in checks:
        log.info("%-7s %-28s %s", c.status, c.name, c.detail)
    failed = [c for c in checks if c.status == FAIL]
    log.info("%d controles, %d fout", len(checks), len(failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

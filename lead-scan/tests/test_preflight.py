from types import SimpleNamespace

from runner.config import Env, Segment, Settings
from runner.preflight import FAIL, OK, WARN, anthropic_check, salesforce_checks, slack_check


def lead_describe(lead_source=True, fields=True):
    picks = [{"value": "Claude Weekly Scan", "active": True}] if lead_source else []
    out = [
        {"name": "LeadSource", "picklistValues": picks},
        {"name": "Reason_unqualified__c", "picklistValues": [{"value": "Duplicate or existing customer", "active": True}]},
    ]
    if fields:
        out += [{"name": "Scan_Score__c", "createable": True}, {"name": "Scan_Segment__c", "createable": True}]
    return {"fields": out}


class FakeSF:
    def __init__(self, sandbox=True, rule_active=True, segments=None, describe=None):
        self.sandbox, self.rule_active = sandbox, rule_active
        self._segments = segments if segments is not None else [
            Segment("S1", "A", None, "Vacancy", "x", 100, False)]
        self.sf = SimpleNamespace(Lead=SimpleNamespace(describe=lambda: describe or lead_describe()))

    def query_all(self, soql):
        if "Organization" in soql:
            return [{"IsSandbox": self.sandbox}]
        if "DuplicateRule" in soql:
            return [{"DeveloperName": "Lead_Scan_Block_Duplicates", "IsActive": self.rule_active}]
        if "LeadHistory" in soql:
            return []
        raise AssertionError(soql)

    def settings(self):
        return Settings()

    def queue_id(self):
        return "00G1"

    def active_segments(self):
        return self._segments


def by_name(checks):
    return {c.name: c for c in checks}


def test_all_green():
    checks = salesforce_checks(FakeSF(), "test")
    assert all(c.status == OK for c in checks), [(c.name, c.status, c.detail) for c in checks]


def test_detects_production_missing_picklist_inactive_rule_and_no_segments():
    sf = FakeSF(sandbox=False, rule_active=False, segments=[], describe=lead_describe(lead_source=False, fields=False))
    checks = by_name(salesforce_checks(sf, "test"))
    assert checks["Omgeving"].status == FAIL
    assert checks["Duplicate rule"].status == FAIL
    assert checks["Scan_Segment__c"].status == FAIL
    lead = checks["Lead (picklists en velden)"]
    assert lead.status == FAIL and "Claude Weekly Scan" in lead.detail and "Scan_Score__c" in lead.detail


def test_one_failing_check_does_not_stop_the_others():
    sf = FakeSF()
    sf.queue_id = lambda: (_ for _ in ()).throw(RuntimeError("Queue Claude_Leads bestaat niet"))
    checks = by_name(salesforce_checks(sf, "test"))
    assert checks["Queue Claude Leads"].status == FAIL and checks["Duplicate rule"].status == OK


def env(token="xoxb", channel="C0123ABCD"):
    return Env("u", "k", "p", "test", token, channel)


def test_slack_check():
    class Web:
        def auth_test(self):
            return {"ok": True}

        def conversations_info(self, channel):
            return {"ok": True}

    assert slack_check(env(), Web()).status == OK
    assert slack_check(env(token=None)).status == WARN


def test_anthropic_check():
    good = SimpleNamespace(models=SimpleNamespace(retrieve=lambda m: {"id": m}))
    assert anthropic_check(good).status == OK

    def boom(m):
        raise RuntimeError("401")

    assert anthropic_check(SimpleNamespace(models=SimpleNamespace(retrieve=boom))).status == FAIL

import pytest

from runner.rollback import run_lead_ids


class FakeSF:
    def __init__(self, run):
        self.run = run
        self.window = None

    def get_run(self, key):
        return self.run

    def scan_leads_between(self, started, finished=None):
        self.window = (started, finished)
        return [{"Id": "00Q1"}, {"Id": "00Q2"}]


def test_run_lead_ids_uses_run_window():
    sf = FakeSF({"Started__c": "2026-10-04T20:07:00Z", "Finished__c": "2026-10-04T23:01:00Z"})
    assert run_lead_ids(sf, "2026-W41") == ["00Q1", "00Q2"]
    assert sf.window == ("2026-10-04T20:07:00Z", "2026-10-04T23:01:00Z")


def test_unknown_run():
    with pytest.raises(RuntimeError):
        run_lead_ids(FakeSF(None), "2026-W41")

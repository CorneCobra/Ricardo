from datetime import datetime

from runner import config
from runner.slack import Notifier, monday_0800, weekly_text

TZ = config.TIMEZONE


class FakeWebClient:
    def __init__(self):
        self.posted, self.scheduled = [], []

    def chat_postMessage(self, **kw):
        self.posted.append(kw)

    def chat_scheduleMessage(self, **kw):
        self.scheduled.append(kw)


def test_monday_0800():
    assert monday_0800(datetime(2026, 10, 4, 23, 30, tzinfo=TZ)) == datetime(2026, 10, 5, 8, 0, tzinfo=TZ)
    assert monday_0800(datetime(2026, 10, 5, 7, 0, tzinfo=TZ)) == datetime(2026, 10, 5, 8, 0, tzinfo=TZ)
    assert monday_0800(datetime(2026, 10, 5, 9, 0, tzinfo=TZ)) is None


def test_weekly_scheduled_vs_immediate():
    web = FakeWebClient()
    n = Notifier("xoxb", "#claude-leads", client=web)
    n.weekly({"run_key": "2026-W41"}, [], None, [], datetime(2026, 10, 4, 23, 0, tzinfo=TZ), schedule=True)
    n.weekly({"run_key": "2026-W41"}, [], None, [], datetime(2026, 10, 4, 23, 0, tzinfo=TZ), schedule=False)
    assert len(web.scheduled) == 1 and len(web.posted) == 1


def test_dry_run_without_token_posts_nothing():
    n = Notifier(None, "#claude-leads")
    assert n.dry_run
    n.error("2026-W41", "test")  # mag niet crashen


def test_weekly_text_numbers_and_top5():
    stats = {"run_key": "2026-W41", "Leads_Created__c": 2, "Candidates_Found__c": 20, "Blocked_Layer_1__c": 5,
             "Blocked_Layer_2__c": 3, "Blocked_Layer_3__c": 1, "Blocked_Layer_4__c": 0, "Below_Threshold__c": 4}
    top = [{"company_name": f"Org {i}", "score": 90 - i, "signal_type": "Vacancy", "why_now": "w"} for i in range(7)]
    t = weekly_text(stats, top, "https://x/run", ["let op"])
    assert "2 nieuwe leads" in t and "tegengehouden 9" in t
    assert "5. Org 4" in t and "Org 5" not in t
    assert "https://x/run" in t and "let op" in t


class FakeUploadClient(FakeWebClient):
    def __init__(self):
        super().__init__()
        self.uploads = []

    def conversations_list(self, **kw):
        return {"channels": [{"name": "claude-leads", "id": "C0123ABCD"}], "response_metadata": {"next_cursor": ""}}

    def files_upload_v2(self, **kw):
        self.uploads.append(kw)


def test_upload_resolves_channel_name_to_id():
    web = FakeUploadClient()
    Notifier("xoxb", "#claude-leads", client=web).upload("r.md", "# rapport", "Rapport", "toelichting")
    assert web.uploads[0]["channel"] == "C0123ABCD" and web.uploads[0]["content"] == "# rapport"


def test_upload_with_channel_id_and_disabled_slack():
    web = FakeUploadClient()
    Notifier("xoxb", "C0999XYZ1", client=web).upload("r.md", "x", "t", "c")
    assert web.uploads[0]["channel"] == "C0999XYZ1"
    Notifier("xoxb", "#claude-leads", dry_run=True, client=web).upload("r.md", "x", "t", "c")
    assert len(web.uploads) == 1

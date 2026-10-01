from datetime import datetime, timedelta

from runner import config
from runner.main import is_scheduled_window

TZ = config.TIMEZONE


def test_run_key_sunday_belongs_to_next_week():
    assert config.run_key(datetime(2026, 10, 4, 22, 0, tzinfo=TZ)) == "2026-W41"  # zondag
    assert config.run_key(datetime(2026, 10, 5, 9, 0, tzinfo=TZ)) == "2026-W41"  # maandag
    assert config.run_key(datetime(2026, 12, 27, 22, 0, tzinfo=TZ)) == "2026-W53"


def test_settings_from_record_defaults_and_values():
    s = config.Settings.from_record({"Kill_Switch__c": True, "Max_Leads_Per_Run__c": 5.0, "Minimum_Score__c": None})
    assert s.kill_switch and s.max_leads_per_run == 5 and s.minimum_score == 70


def test_deadline():
    start = datetime(2026, 10, 4, 22, 0, tzinfo=TZ)
    now = {"t": start}
    d = config.Deadline(started=start, minutes=60, clock=lambda: now["t"])
    assert not d.expired()
    now["t"] = start + timedelta(minutes=51)  # 60 - 10 minuten reserve
    assert d.expired()


def test_scheduled_window_summer_and_winter():
    # zomertijd: cron 20:00 UTC = 22:00 lokaal
    assert is_scheduled_window(datetime(2026, 10, 4, 20, 0, tzinfo=config.ZoneInfo("UTC")))
    # wintertijd: cron 20:00 UTC = 21:00 lokaal -> overslaan, 21:00 UTC = 22:00 -> draaien
    assert not is_scheduled_window(datetime(2026, 11, 1, 20, 0, tzinfo=config.ZoneInfo("UTC")))
    assert is_scheduled_window(datetime(2026, 11, 1, 21, 0, tzinfo=config.ZoneInfo("UTC")))
    assert not is_scheduled_window(datetime(2026, 10, 5, 20, 0, tzinfo=config.ZoneInfo("UTC")))  # maandag

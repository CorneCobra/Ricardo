import json
from pathlib import Path

from runner.seed_segments import plan, validate_segments

DATA = Path(__file__).resolve().parents[1] / "data" / "segments.json"


def test_proposed_segments_are_valid():
    segments = json.loads(DATA.read_text(encoding="utf-8"))["segments"]
    assert validate_segments(segments) == []
    assert len(segments) == 9
    assert sum(1 for s in segments if s["Exploration__c"]) == 3
    assert any(s["Signal_Type__c"] == "Lookalike" for s in segments)


def test_validation_catches_mistakes():
    base = {"Name": "A", "Target_Industry__c": "Nonprofit", "Signal_Type__c": "Vacancy",
            "Search_Strategy__c": "x", "Weight__c": 60, "Exploration__c": False}
    problems = validate_segments([base, {**base, "Name": "B", "Target_Industry__c": "HigherEducation",
                                         "Signal_Type__c": "Gossip"}])
    text = " ".join(problems)
    assert "HigherEducation" in text and "Gossip" in text and "120" in text


def test_plan_creates_or_updates_by_name():
    steps = plan([{"Name": "A", "Weight__c": 50}, {"Name": "B", "Weight__c": 50}], [{"Id": "a0S1", "Name": "A"}])
    assert steps[0][:2] == ("update", "a0S1") and steps[1][:2] == ("create", None)

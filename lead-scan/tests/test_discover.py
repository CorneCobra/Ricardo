from runner.config import Segment
from runner.discover import discover

from fakes import FakeClaude, response, tool_use


def seg(signal_type):
    return Segment(id="S1", name="Nonprofit vacatures", target_industry="Nonprofit", signal_type=signal_type,
                   search_strategy="CRM-vacatures", weight=100, exploration=False)


def cand(name, signal):
    return {"company_name": name, "domain": name.lower() + ".nl", "signal_type": signal,
            "signal_summary": "Vacature CRM-beheerder", "source_urls": ["https://x.nl/v"], "segment_id": "verzonnen"}


def test_segment_id_is_overwritten_and_signal_type_enforced():
    client = FakeClaude([response([tool_use("submit_candidates", {
        "candidates": [cand("Goed", "Vacancy"), cand("Fout", "Merger")]})])])
    found, notes = discover(client, seg("Vacancy"), 5, None)
    assert [c["company_name"] for c in found] == ["Goed"]
    assert found[0]["segment_id"] == "S1"
    assert any("Merger" in n for n in notes)
    assert "alleen signalen van het type Vacancy" in client.calls[0]["messages"][0]["content"]


def test_segment_without_signal_type_accepts_all():
    client = FakeClaude([response([tool_use("submit_candidates", {
        "candidates": [cand("Een", "Vacancy"), cand("Twee", "Merger")]})])])
    found, _ = discover(client, seg(None), 5, None)
    assert len(found) == 2


def test_lookalike_segment_gets_recent_customers_as_examples():
    lookalike = Segment(id="S2", name="Lookalikes", target_industry=None, signal_type="Lookalike",
                        search_strategy="lijkt op klanten", weight=10, exploration=False)
    client = FakeClaude([response([tool_use("submit_candidates", {"candidates": []})])])
    discover(client, lookalike, 5, None, [{"name": "Fictief Fonds", "industry": "Nonprofit"}])
    prompt = client.calls[0]["messages"][0]["content"]
    assert "Fictief Fonds" in prompt and "niet deze organisaties zelf" in prompt


def test_examples_are_not_sent_to_other_segments():
    client = FakeClaude([response([tool_use("submit_candidates", {"candidates": []})])])
    discover(client, seg("Vacancy"), 5, None, [{"name": "Fictief Fonds"}])
    assert "Fictief Fonds" not in client.calls[0]["messages"][0]["content"]

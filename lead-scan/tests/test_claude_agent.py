import pytest

from runner import config
from runner.claude_agent import DeadlineReached, run_agent, web_tools
from runner.schemas import DOUBT_SCHEMA

from fakes import FakeClaude, response, search_result, text, tool_use

OK = {"verdict": "different", "rationale": "Andere organisatie in een andere stad."}


def run(client, **kw):
    args = dict(system="s", prompt="p", submit_name="submit_verdict", submit_description="d",
                schema=DOUBT_SCHEMA, max_searches=5, deadline=None)
    args.update(kw)
    return run_agent(client, **args)


def test_submit_on_first_turn_and_request_shape():
    client = FakeClaude([response([search_result("https://a.nl/x"), tool_use("submit_verdict", OK)], searches=2)])
    res = run(client)
    assert res.data == OK and res.searches_used == 2 and "https://a.nl/x" in res.seen_urls
    call = client.calls[0]
    assert call["model"] == config.MODEL
    assert call["thinking"] == {"type": "adaptive"}
    assert call["tool_choice"] == {"type": "auto"}
    assert call["fallbacks"] == "default" and config.FALLBACK_BETA in call["betas"]
    submit = [t for t in call["tools"] if t.get("name") == "submit_verdict"][0]
    assert submit["strict"] is True and "maxLength" not in str(submit["input_schema"])


def test_search_and_fetch_share_one_budget():
    tools = web_tools(5)
    assert sum(t["max_uses"] for t in tools) == 5
    assert web_tools(1) == [{"type": config.WEB_SEARCH_TOOL, "name": "web_search", "max_uses": 1}]
    assert web_tools(0) == []


def test_pause_turn_is_resumed_with_remaining_budget():
    client = FakeClaude([
        response([text("zoeken...")], stop_reason="pause_turn", searches=3),
        response([tool_use("submit_verdict", OK)], searches=1),
    ])
    res = run(client)
    assert res.data == OK
    assert len(client.calls) == 2
    second_budget = sum(t["max_uses"] for t in client.calls[1]["tools"] if "max_uses" in t)
    assert second_budget == 2
    assert client.calls[1]["messages"][-1]["role"] == "assistant"  # geen extra 'ga door'-bericht


def test_budget_exhausted_stops_without_new_request():
    client = FakeClaude([response([text("nog niet klaar")], stop_reason="pause_turn", searches=5)])
    res = run(client)
    assert res.data is None and "Zoekbudget" in res.errors[0]
    assert len(client.calls) == 1


def test_reminder_once_then_give_up():
    client = FakeClaude([response([text("klaar")], stop_reason="end_turn"),
                         response([text("echt klaar")], stop_reason="end_turn")])
    res = run(client)
    assert res.data is None and len(client.calls) == 2


def test_invalid_submission_is_rejected():
    client = FakeClaude([response([tool_use("submit_verdict", {"verdict": "maybe", "rationale": "x"})])])
    res = run(client)
    assert res.data is None and res.errors


def test_refusal():
    client = FakeClaude([response([], stop_reason="refusal")])
    res = run(client)
    assert res.data is None and "refusal" in res.errors[0]


def test_deadline_raises_before_request():
    class Expired:
        def expired(self):
            return True

    client = FakeClaude([])
    with pytest.raises(DeadlineReached):
        run(client, deadline=Expired())
    assert client.calls == []

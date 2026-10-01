"""Nep-implementaties van Claude, Salesforce en Slack voor de unit tests."""

from __future__ import annotations

from types import SimpleNamespace


def tool_use(name, data):
    return SimpleNamespace(type="tool_use", name=name, input=data, id="tu_1")


def text(t):
    return SimpleNamespace(type="text", text=t)


def search_result(*urls):
    return SimpleNamespace(type="web_search_tool_result", content=[SimpleNamespace(url=u) for u in urls])


def response(content, stop_reason="tool_use", searches=0):
    usage = SimpleNamespace(server_tool_use=SimpleNamespace(web_search_requests=searches, web_fetch_requests=0))
    return SimpleNamespace(content=content, stop_reason=stop_reason, usage=usage)


class _Stream:
    def __init__(self, resp):
        self.resp = resp

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get_final_message(self):
        return self.resp


class FakeClaude:
    """Geeft per aanroep de volgende respons uit een lijst, of via een functie(kwargs)."""

    def __init__(self, responses=None, handler=None):
        self.responses = list(responses or [])
        self.handler = handler
        self.calls = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(stream=self._stream))

    def _stream(self, **kwargs):
        self.calls.append(kwargs)
        if self.handler:
            return _Stream(self.handler(kwargs))
        return _Stream(self.responses.pop(0))


class FakeNotifier:
    def __init__(self):
        self.weekly_calls = []
        self.errors = []

    def weekly(self, stats, top, run_url, warnings, now, schedule):
        self.weekly_calls.append({"stats": stats, "top": top, "warnings": warnings, "schedule": schedule})

    def error(self, run_key, message, run_url=None):
        self.errors.append(message)

    def info(self, run_key, message):
        pass

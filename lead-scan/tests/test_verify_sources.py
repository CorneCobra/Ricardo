import socket
from types import SimpleNamespace

import requests

from runner import verify_sources
from runner.verify_sources import url_reachable, verify

PUBLIC = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))]
PRIVATE = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.5", 0))]


class Session:
    def __init__(self, head_code, get_code=None, error=None):
        self.head_code, self.get_code, self.error = head_code, get_code, error

    def head(self, url, **kw):
        if self.error:
            raise self.error
        return SimpleNamespace(status_code=self.head_code)

    def get(self, url, **kw):
        return SimpleNamespace(status_code=self.get_code, close=lambda: None)


def test_url_reachable(monkeypatch):
    monkeypatch.setattr(verify_sources.socket, "getaddrinfo", lambda h, p: PUBLIC)
    assert url_reachable("https://a.nl/x", Session(200))[0]
    assert url_reachable("https://a.nl/x", Session(403))[0]  # bot-blokkade telt als bestaand
    assert url_reachable("https://a.nl/x", Session(405, 200))[0]  # HEAD niet ondersteund
    assert not url_reachable("https://a.nl/x", Session(404, 404))[0]
    assert not url_reachable("https://a.nl/x", Session(200, error=requests.ConnectionError()))[0]
    assert not url_reachable("ftp://a.nl/x", Session(200))[0]


def test_private_or_unknown_hosts_are_rejected(monkeypatch):
    monkeypatch.setattr(verify_sources.socket, "getaddrinfo", lambda h, p: PRIVATE)
    assert not url_reachable("http://intern.nl/", Session(200))[0]

    def fail(h, p):
        raise socket.gaierror()

    monkeypatch.setattr(verify_sources.socket, "getaddrinfo", fail)
    assert not verify_sources.domain_exists("bestaatniet.nl")


def test_verify(monkeypatch):
    monkeypatch.setattr(verify_sources.socket, "getaddrinfo", lambda h, p: PUBLIC)
    lead = {"domain": "a.nl", "claims": [{"claim": "x", "source_url": "https://a.nl/vacature/"}]}
    cand = {"source_urls": ["https://www.a.nl/vacature"]}
    res = verify(lead, cand, {"https://a.nl/vacature"}, Session(200))
    assert res.ok and res.unseen_urls == []
    res = verify(lead, cand, set(), Session(404, 404))
    assert not res.ok and len(res.problems) == 2

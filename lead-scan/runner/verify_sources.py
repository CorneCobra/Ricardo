"""Bronnencontrole: elke bewering moet herleidbaar zijn tot een bereikbare bron.

Een lead valt af als het organisatiedomein niet bestaat (DNS), of als één van de
bron-URL's van de claims onbereikbaar is. Sites die bots weren (401/403/429)
gelden als bereikbaar: de pagina bestaat, alleen niet voor een script.
"""

from __future__ import annotations

import ipaddress
import logging
import socket
from dataclasses import dataclass, field
from urllib.parse import urlsplit

import requests

log = logging.getLogger(__name__)

TIMEOUT = 15
USER_AGENT = "Mozilla/5.0 (compatible; CobraLeadScan/1.0; bronverificatie)"
BOT_BLOCK_CODES = {401, 403, 429}


@dataclass
class Verification:
    ok: bool
    problems: list[str] = field(default_factory=list)
    unseen_urls: list[str] = field(default_factory=list)


def _public_host(host: str) -> bool:
    """Bestaat de host en wijst die naar een publiek adres (geen intern netwerk)?"""
    try:
        infos = socket.getaddrinfo(host, None)
    except (socket.gaierror, UnicodeError):
        return False
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            return False
    return bool(infos)


def domain_exists(domain: str) -> bool:
    return _public_host(domain) or _public_host(f"www.{domain}")


def url_reachable(url: str, session: requests.Session | None = None) -> tuple[bool, str]:
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        return False, "geen http(s)-URL"
    if not _public_host(parts.hostname):
        return False, "host bestaat niet of is niet publiek"
    http = session or requests
    headers = {"User-Agent": USER_AGENT}
    try:
        resp = http.head(url, headers=headers, timeout=TIMEOUT, allow_redirects=True)
        if resp.status_code >= 400 and resp.status_code not in BOT_BLOCK_CODES:
            # Veel servers ondersteunen HEAD niet goed; probeer GET.
            resp = http.get(url, headers=headers, timeout=TIMEOUT, allow_redirects=True, stream=True)
            resp.close()
    except requests.RequestException as exc:
        return False, f"niet bereikbaar ({exc.__class__.__name__})"
    if resp.status_code < 400 or resp.status_code in BOT_BLOCK_CODES:
        return True, str(resp.status_code)
    return False, f"HTTP {resp.status_code}"


def _norm_url(url: str) -> str:
    p = urlsplit(url.strip())
    host = (p.hostname or "").lower().removeprefix("www.")
    return f"{host}{p.path.rstrip('/')}"


def verify(lead: dict, candidate: dict, seen_urls: set[str], session: requests.Session | None = None) -> Verification:
    problems: list[str] = []
    if not domain_exists(lead["domain"]):
        problems.append(f"domein {lead['domain']} bestaat niet")

    urls = {c["source_url"] for c in lead["claims"]} | set(candidate.get("source_urls", []))
    checked: dict[str, tuple[bool, str]] = {}
    for url in sorted(urls):
        checked[url] = url_reachable(url, session)
        if not checked[url][0]:
            problems.append(f"bron onbereikbaar: {url} ({checked[url][1]})")

    seen = {_norm_url(u) for u in seen_urls}
    unseen = [u for u in sorted(urls) if _norm_url(u) not in seen]
    return Verification(ok=not problems, problems=problems, unseen_urls=unseen)

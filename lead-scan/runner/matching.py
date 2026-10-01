"""Laag 1 en 2 van de dubbelcheck: matchen op meerdere sleutels, zonder oordeel.

Sleutels: websitedomein (Lead, Account), e-maildomein (Lead, Contact), KvK-nummer
(Account) en genormaliseerde naam. Een exacte match op een uitgesloten record is
laag 1; een exacte match op elk ander bestaand record is laag 2. Lijkt de naam
alleen op een bestaand record, dan is het een twijfelgeval voor laag 3.

E-maildomeinen zijn rommelig (een lead 'X' met een hogeschool-adres, contactpersonen
van andere organisaties bij een Account). Een match op alleen het e-maildomein telt
daarom hard als het domein bij de naam van het record past; anders is het een
twijfelgeval, zodat Claude de records vergelijkt en bij twijfel de kandidaat laat vallen.
"""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
from difflib import SequenceMatcher

from . import config

GENERIC_EMAIL_DOMAINS = {
    "gmail.com", "googlemail.com", "outlook.com", "outlook.nl", "hotmail.com", "hotmail.nl",
    "live.com", "live.nl", "msn.com", "yahoo.com", "yahoo.nl", "icloud.com", "me.com", "mac.com",
    "aol.com", "proton.me", "protonmail.com", "gmx.com", "gmx.net", "gmx.de", "web.de", "mail.com",
    "ziggo.nl", "kpnmail.nl", "kpnplanet.nl", "planet.nl", "home.nl", "xs4all.nl", "hetnet.nl",
    "casema.nl", "upcmail.nl", "chello.nl", "telfort.nl", "quicknet.nl", "online.nl", "tele2.nl",
    "zonnet.nl", "solcon.nl", "caiway.nl", "telenet.be", "skynet.be", "proximus.be",
}

# Domeinen van platforms (vacaturesites, social media, websitebouwers): nooit een sleutel.
PLATFORM_DOMAINS = {
    "homerun.co", "recruitee.com", "workable.com", "teamtailor.com", "werkzoeken.nl", "indeed.com",
    "nationalevacaturebank.nl", "linkedin.com", "facebook.com", "instagram.com", "twitter.com",
    "x.com", "youtube.com", "google.com", "wix.com", "wixsite.com", "wordpress.com", "blogspot.com",
    "jimdo.com", "jimdosite.com", "github.io", "squarespace.com", "webflow.io", "tenderned.nl",
    "kvk.nl", "example.com", "invalid",
}

# Tweede-niveau publieke suffixen waarvoor het registreerbare domein drie labels heeft.
_SECOND_LEVEL_SUFFIXES = {
    "co.uk", "org.uk", "ac.uk", "gov.uk", "com.au", "org.au", "net.au", "co.nz", "org.nz",
    "co.za", "com.br", "co.jp", "com.tr", "com.cn", "com.sg", "co.in", "com.mx",
}

# Woorden die bij het vergelijken van namen worden weggelaten.
_NAME_STOPWORDS = {
    "bv", "nv", "vof", "cv", "ua", "ba", "wa", "stichting", "vereniging", "cooperatie", "cooperatief",
    "holding", "groep", "group", "ltd", "limited", "inc", "gmbh", "ggmbh", "sa", "sarl", "ag", "plc",
    "llc", "co", "the", "de", "het", "nederland", "netherlands", "en",
}

_EMAIL_IN_TEXT = re.compile(r"@")


def registrable_domain(host: str) -> str:
    labels = host.split(".")
    if len(labels) >= 3 and ".".join(labels[-2:]) in _SECOND_LEVEL_SUFFIXES:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])


def normalize_domain(value: str | None) -> str | None:
    """'https://www.Voorbeeld.nl/over-ons' -> 'voorbeeld.nl'. Ongeldig of platform -> None."""
    if not value:
        return None
    s = value.strip().lower()
    if _EMAIL_IN_TEXT.search(s):
        s = s.rsplit("@", 1)[1]
    s = re.sub(r"^[a-z][a-z0-9+.-]*://", "", s)
    s = re.split(r"[/?#\s]", s, maxsplit=1)[0]
    s = s.split(":", 1)[0].strip(".")
    # Sandbox maskeert e-mailadressen met '.invalid'.
    while s.endswith(".invalid"):
        s = s[: -len(".invalid")]
    if s.startswith("www."):
        s = s[4:]
    if not re.fullmatch(r"[a-z0-9-]+(\.[a-z0-9-]+)+", s):
        return None
    domain = registrable_domain(s)
    if domain in PLATFORM_DOMAINS or domain in config.OWN_DOMAINS:
        return None
    return domain


def email_domain(email: str | None) -> str | None:
    """Domein van een e-mailadres, behalve generieke providers en eigen domeinen."""
    if not email or "@" not in email:
        return None
    domain = normalize_domain(email)
    if not domain or domain in GENERIC_EMAIL_DOMAINS:
        return None
    return domain


def normalize_kvk(value: str | None) -> str | None:
    """KvK-nummers hebben 8 cijfers; een weggevallen voorloopnul wordt aangevuld."""
    if not value:
        return None
    digits = re.sub(r"\D", "", str(value))
    if len(digits) == 7:
        digits = "0" + digits
    if len(digits) != 8 or digits in {"12345678", "00000000"}:
        return None
    return digits


def normalize_name(value: str | None) -> str:
    """'Stichting De Zonnebloem B.V.' -> 'zonnebloem'."""
    if not value:
        return ""
    s = unicodedata.normalize("NFKD", value)
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = s.replace("&", " en ").replace(".", "")
    s = re.sub(r"\([^)]*\)", " ", s)  # toevoegingen tussen haakjes, bv. '(KiKa)'
    s = re.sub(r"[^a-z0-9]+", " ", s)
    tokens = [t for t in s.split() if t not in _NAME_STOPWORDS]
    return " ".join(tokens)


def name_keys(value: str | None) -> set[str]:
    """Alle naamsleutels van een record: de volledige naam plus aliassen.

    'Stichting Kinderen Kankervrij (KiKa)' -> {'kinderen kankervrij', 'kika'}
    'Regio College / Talland'              -> {'regio college talland', 'regio college', 'talland'}
    """
    if not value:
        return set()
    keys = {normalize_name(value)}
    parts = re.findall(r"\(([^)]*)\)", value)
    parts += re.split(r"\s*/\s*", re.sub(r"\([^)]*\)", " ", value)) if "/" in value else []
    keys |= {normalize_name(p) for p in parts}
    # Twee tekens is genoeg voor een exacte sleutel (CZ, iO, EO); losse letters niet.
    return {k for k in keys if len(k) >= 2}


def domain_fits_name(domain: str, name: str) -> bool:
    """Past een domein bij een organisatienaam? 'apollovredestein.com' ~ 'Apollo Vredestein'."""
    label = domain.split(".")[0].replace("-", "")
    if len(label) < 2:
        return False
    for key in name_keys(name):
        compact = key.replace(" ", "")
        initials = "".join(t[0] for t in key.split())
        if label == compact or (len(initials) >= 2 and label == initials):
            return True
        if len(label) >= 3 and compact.startswith(label):  # 'kwf' ~ 'KWF Kankerbestrijding'
            return True
        if (len(compact) >= 4 and compact in label) or (len(label) >= 4 and label in compact):
            return True
    return False


def name_similarity(a: str, b: str) -> float:
    """Gelijkenis 0-1 tussen twee genormaliseerde namen, inclusief 'deelnaam'-gevallen."""
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    ta, tb = set(a.split()), set(b.split())
    short, long_ = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
    # 'landstede' in 'landstede vo', maar niet op korte, nietszeggende woorden.
    if short and short <= long_ and (len(short) >= 2 or len(next(iter(short))) >= 4):
        return 0.9
    matcher = SequenceMatcher(None, a, b)
    if matcher.real_quick_ratio() < config.FUZZY_DOUBT_THRESHOLD:
        return 0.0
    if matcher.quick_ratio() < config.FUZZY_DOUBT_THRESHOLD:
        return 0.0
    return matcher.ratio()


@dataclass
class ExistingRecord:
    """Een bestaand Account of Lead met alle sleutels waarop we matchen."""

    id: str
    object: str  # 'Account' of 'Lead'
    name: str
    owner_id: str | None = None
    type: str | None = None
    status: str | None = None
    excluded: bool = False
    exclusion_reason: str | None = None
    domains: set[str] = field(default_factory=set)  # websitedomein
    kvks: set[str] = field(default_factory=set)
    email_domains: set[str] = field(default_factory=set)  # van de Lead zelf of van Contacts

    def summary(self) -> dict:
        return {
            "id": self.id,
            "object": self.object,
            "name": self.name,
            "type": self.type,
            "status": self.status,
            "website_domains": sorted(self.domains),
            "email_domains": sorted(self.email_domains),
            "kvk_numbers": sorted(self.kvks),
        }


@dataclass
class Match:
    record: ExistingRecord
    key_type: str  # domain, email_domain, kvk, name, fuzzy_name, email_domain_unrelated
    key: str
    similarity: float = 1.0


@dataclass
class MatchResult:
    outcome: str  # clear, blocked_l1, blocked_l2, doubt
    matches: list[Match] = field(default_factory=list)

    @property
    def reason(self) -> str:
        if not self.matches:
            return ""
        m = self.matches[0]
        why = f" ({m.record.exclusion_reason})" if m.record.excluded and m.record.exclusion_reason else ""
        return f"{m.key_type}={m.key} -> {m.record.object} {m.record.name} [{m.record.id}]{why}"

    def task_target(self) -> ExistingRecord | None:
        """Bestaand niet-uitgesloten record waarvan de eigenaar een Task krijgt (Account eerst)."""
        if self.outcome != "blocked_l2":
            return None
        records = [m.record for m in self.matches if not m.record.excluded]
        records.sort(key=lambda r: 0 if r.object == "Account" else 1)
        return records[0] if records else None


class MatchIndex:
    """Index over alle bestaande Accounts en niet-geconverteerde Leads."""

    def __init__(self, records: list[ExistingRecord]):
        self.records = records
        self.by_domain: dict[str, list[ExistingRecord]] = defaultdict(list)
        self.by_email_domain: dict[str, list[ExistingRecord]] = defaultdict(list)
        self.by_kvk: dict[str, list[ExistingRecord]] = defaultdict(list)
        self.by_name: dict[str, list[ExistingRecord]] = defaultdict(list)
        for rec in records:
            for d in rec.domains:
                self.by_domain[d].append(rec)
            for d in rec.email_domains - rec.domains:
                self.by_email_domain[d].append(rec)
            for k in rec.kvks:
                self.by_kvk[k].append(rec)
            for n in name_keys(rec.name):
                self.by_name[n].append(rec)
        self._names = list(self.by_name.keys())

    def check(self, company_name: str, domain: str | None, kvk: str | None = None) -> MatchResult:
        strong: list[Match] = []
        weak: list[Match] = []
        d = normalize_domain(domain)
        if d:
            strong += [Match(r, "domain", d) for r in self.by_domain.get(d, [])]
            for r in self.by_email_domain.get(d, []):
                if domain_fits_name(d, r.name):
                    strong.append(Match(r, "email_domain", d))
                else:
                    weak.append(Match(r, "email_domain_unrelated", d, 0.85))
        k = normalize_kvk(kvk)
        if k:
            strong += [Match(r, "kvk", k) for r in self.by_kvk.get(k, [])]
        for n in name_keys(company_name):
            strong += [Match(r, "name", n) for r in self.by_name.get(n, [])]

        if strong:
            strong.sort(key=lambda m: (not m.record.excluded, m.record.object != "Account"))
            outcome = "blocked_l1" if strong[0].record.excluded else "blocked_l2"
            return MatchResult(outcome, strong)

        n = normalize_name(company_name)
        fuzzy: list[Match] = []
        for other in self._names:
            score = name_similarity(n, other)
            if score >= config.FUZZY_DOUBT_THRESHOLD:
                fuzzy += [Match(r, "fuzzy_name", other, score) for r in self.by_name[other]]
        doubts = weak + fuzzy
        if doubts:
            doubts.sort(key=lambda m: (-m.similarity, not m.record.excluded))
            return MatchResult("doubt", doubts[:5])
        return MatchResult("clear")


class RunDeduper:
    """Voorkomt dat dezelfde organisatie binnen één run twee keer wordt verwerkt."""

    def __init__(self):
        self._seen: set[str] = set()

    def seen(self, company_name: str, domain: str | None) -> bool:
        keys = {f"n:{normalize_name(company_name)}"}
        d = normalize_domain(domain)
        if d:
            keys.add(f"d:{d}")
        hit = bool(keys & self._seen)
        self._seen |= keys
        return hit

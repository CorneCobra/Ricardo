"""Laag 1: de uitsluitlijst, elke run opnieuw opgebouwd uit Salesforce.

Uitgesloten (een match betekent: kandidaat valt af, geen Task):
- Accounts met Type Customer, Customer - sleeping, Partner, Competitor, Supplier,
  Broker / Recruiter;
- Accounts met een gevulde Close_Date_first_Opportunity__c;
- de volledige Account-boom (moeder, dochters, zusters) van elke klant;
- Leads Unqualified met reden Former customer, Competitor of Wrong industry;
- Leads die in de afgelopen 12 maanden Unqualified zijn gezet.

Alle andere Accounts en open Leads komen ook in de index: een match daarop is
laag 2 (bestaand record, eventueel een Task voor de eigenaar).
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone

from . import config
from .matching import ExistingRecord, MatchIndex, email_domain, normalize_domain, normalize_kvk

ACCOUNT_SOQL = (
    "SELECT Id, Name, Website, Type, ParentId, OwnerId, Close_Date_first_Opportunity__c, "
    "Chamber_of_Commerce_Number__c FROM Account"
)
CONTACT_SOQL = "SELECT AccountId, Email FROM Contact WHERE Email != null AND AccountId != null"
LEAD_SOQL = (
    "SELECT Id, Company, Website, Email, Status, Reason_unqualified__c, OwnerId, LastModifiedDate "
    "FROM Lead WHERE IsConverted = false"
)

# Een e-maildomein dat bij zoveel verschillende Account-bomen voorkomt, is geen sleutel
# (bijvoorbeeld een adviesbureau of leverancier met contactpersonen bij veel klanten).
SHARED_EMAIL_DOMAIN_TREES = 5


def _parse_sf_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.strptime(value[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)


def _tree_roots(accounts: list[dict]) -> dict[str, str]:
    """Account-Id -> vaste vertegenwoordiger van zijn Account-boom (union-find, bestand tegen cycli)."""
    rep = {a["Id"]: a["Id"] for a in accounts}

    def find(x: str) -> str:
        while rep[x] != x:
            rep[x] = rep[rep[x]]
            x = rep[x]
        return x

    for a in accounts:
        parent = a.get("ParentId")
        if parent in rep:
            ra, rb = find(a["Id"]), find(parent)
            if ra != rb:
                rep[max(ra, rb)] = min(ra, rb)
    return {acc_id: find(acc_id) for acc_id in rep}


def build_account_records(accounts: list[dict], contacts: list[dict]) -> list[ExistingRecord]:
    roots = _tree_roots(accounts)
    customer_trees = {
        roots[a["Id"]]
        for a in accounts
        if a.get("Type") in config.CUSTOMER_TYPES or a.get("Close_Date_first_Opportunity__c")
    }

    # E-maildomeinen per Account, zonder domeinen die bij veel bomen voorkomen.
    domains_by_account: dict[str, set[str]] = defaultdict(set)
    trees_by_domain: dict[str, set[str]] = defaultdict(set)
    for c in contacts:
        d = email_domain(c.get("Email"))
        acc = c.get("AccountId")
        if d and acc in roots:
            domains_by_account[acc].add(d)
            trees_by_domain[d].add(roots[acc])
    shared = {d for d, trees in trees_by_domain.items() if len(trees) >= SHARED_EMAIL_DOMAIN_TREES}

    records = []
    for a in accounts:
        reason = None
        if a.get("Type") in config.ACCOUNT_TYPES_EXCLUDED:
            reason = f"Account Type {a['Type']}"
        elif a.get("Close_Date_first_Opportunity__c"):
            reason = "Account met eerste gewonnen opportunity"
        elif roots[a["Id"]] in customer_trees:
            reason = "Hoort bij de Account-boom van een klant"
        domains = {d for d in domains_by_account.get(a["Id"], set()) if d not in shared}
        site = normalize_domain(a.get("Website"))
        if site:
            domains.add(site)
        kvk = normalize_kvk(a.get("Chamber_of_Commerce_Number__c"))
        records.append(
            ExistingRecord(
                id=a["Id"],
                object="Account",
                name=a.get("Name") or "",
                owner_id=a.get("OwnerId"),
                type=a.get("Type"),
                excluded=reason is not None,
                exclusion_reason=reason,
                domains=domains,
                kvks={kvk} if kvk else set(),
            )
        )
    return records


def build_lead_records(leads: list[dict], now: datetime | None = None) -> list[ExistingRecord]:
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=round(config.UNQUALIFIED_LOOKBACK_MONTHS * 30.44))
    records = []
    for lead in leads:
        reason = None
        if lead.get("Status") == "Unqualified":
            # Benadering: LastModifiedDate als moment van diskwalificeren
            # (er is geen veldgeschiedenis op Status).
            changed = _parse_sf_datetime(lead.get("LastModifiedDate"))
            if lead.get("Reason_unqualified__c") in config.UNQUALIFIED_REASONS_EXCLUDED:
                reason = f"Lead Unqualified: {lead['Reason_unqualified__c']}"
            elif changed and changed >= cutoff:
                reason = "Lead minder dan 12 maanden geleden Unqualified"
        domains = {d for d in (normalize_domain(lead.get("Website")), email_domain(lead.get("Email"))) if d}
        records.append(
            ExistingRecord(
                id=lead["Id"],
                object="Lead",
                name=lead.get("Company") or "",
                owner_id=lead.get("OwnerId"),
                status=lead.get("Status"),
                excluded=reason is not None,
                exclusion_reason=reason,
                domains=domains,
            )
        )
    return records


def build_index(sf) -> MatchIndex:
    """Haalt Accounts, Contacts en open Leads op en bouwt de index voor laag 1 en 2."""
    accounts = sf.query_all(ACCOUNT_SOQL)
    contacts = sf.query_all(CONTACT_SOQL)
    leads = sf.query_all(LEAD_SOQL)
    return MatchIndex(build_account_records(accounts, contacts) + build_lead_records(leads))

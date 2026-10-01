"""Laag 1: de uitsluitlijst, elke run opnieuw opgebouwd uit Salesforce.

Uitgesloten (een match betekent: kandidaat valt af, geen Task):
- Accounts met Type Customer, Customer - sleeping, Partner, Competitor, Supplier,
  Broker / Recruiter;
- Accounts met een gevulde Close_Date_first_Opportunity__c;
- de volledige Account-boom (moeder, dochters, zusters) van elke klant;
- Leads Unqualified met reden Former customer, Competitor of Wrong industry;
- Leads die in de afgelopen 12 maanden Unqualified zijn gezet. Bron: de
  statusgeschiedenis (LeadHistory). Dekt die niet de hele periode (bijv. een
  sandbox die korter bestaat), dan geldt LastModifiedDate als strenge benadering.

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
    "SELECT Id, Company, Website, Email, Status, Reason_unqualified__c, OwnerId, CreatedDate, LastModifiedDate "
    "FROM Lead WHERE IsConverted = false"
)
STATUS_HISTORY_SOQL = (
    "SELECT LeadId, NewValue, CreatedDate FROM LeadHistory "
    "WHERE Field = 'Status' AND CreatedDate = LAST_N_MONTHS:13"
)
STATUS_HISTORY_START_SOQL = "SELECT MIN(CreatedDate) oudste FROM LeadHistory WHERE Field = 'Status'"

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
        site = normalize_domain(a.get("Website"))
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
                domains={site} if site else set(),
                kvks={kvk} if kvk else set(),
                email_domains={d for d in domains_by_account.get(a["Id"], set()) if d not in shared},
            )
        )
    return records


def unqualified_moments(history: list[dict]) -> dict[str, datetime]:
    """Lead-Id -> laatste moment waarop Status naar Unqualified ging (uit LeadHistory)."""
    moments: dict[str, datetime] = {}
    for row in history:
        if row.get("NewValue") != "Unqualified":
            continue
        at = _parse_sf_datetime(row.get("CreatedDate"))
        if at and (row["LeadId"] not in moments or at > moments[row["LeadId"]]):
            moments[row["LeadId"]] = at
    return moments


def build_lead_records(
    leads: list[dict],
    now: datetime | None = None,
    unqualified_at: dict[str, datetime] | None = None,
    history_start: datetime | None = None,
) -> list[ExistingRecord]:
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=round(config.UNQUALIFIED_LOOKBACK_MONTHS * 30.44))
    unqualified_at = unqualified_at or {}
    # Alleen als de geschiedenis de hele periode dekt, is 'geen overgang gevonden' betrouwbaar.
    history_covers = history_start is not None and history_start <= cutoff
    records = []
    for lead in leads:
        reason = None
        if lead.get("Status") == "Unqualified":
            created = _parse_sf_datetime(lead.get("CreatedDate"))
            changed = _parse_sf_datetime(lead.get("LastModifiedDate"))
            moment = unqualified_at.get(lead["Id"])
            if lead.get("Reason_unqualified__c") in config.UNQUALIFIED_REASONS_EXCLUDED:
                reason = f"Lead Unqualified: {lead['Reason_unqualified__c']}"
            elif moment and moment >= cutoff:
                reason = "Lead minder dan 12 maanden geleden Unqualified"
            elif created and created >= cutoff:
                reason = "Lead jonger dan 12 maanden en Unqualified"
            elif not history_covers and changed and changed >= cutoff:
                reason = "Lead Unqualified, gewijzigd in de laatste 12 maanden (statusgeschiedenis te kort)"
        records.append(
            ExistingRecord(
                id=lead["Id"],
                object="Lead",
                name=lead.get("Company") or "",
                owner_id=lead.get("OwnerId"),
                status=lead.get("Status"),
                excluded=reason is not None,
                exclusion_reason=reason,
                domains={d for d in [normalize_domain(lead.get("Website"))] if d},
                email_domains={d for d in [email_domain(lead.get("Email"))] if d},
            )
        )
    return records


def build_index(sf) -> MatchIndex:
    """Haalt Accounts, Contacts en open Leads op en bouwt de index voor laag 1 en 2."""
    accounts = sf.query_all(ACCOUNT_SOQL)
    contacts = sf.query_all(CONTACT_SOQL)
    leads = sf.query_all(LEAD_SOQL)
    history = sf.query_all(STATUS_HISTORY_SOQL)
    start_rows = sf.query_all(STATUS_HISTORY_START_SOQL)
    history_start = _parse_sf_datetime(start_rows[0].get("oudste")) if start_rows else None
    leads_records = build_lead_records(leads, None, unqualified_moments(history), history_start)
    return MatchIndex(build_account_records(accounts, contacts) + leads_records)

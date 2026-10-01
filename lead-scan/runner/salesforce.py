"""Alle Salesforce-communicatie van de runner. Claude komt hier nooit aan.

- Inloggen met de JWT-flow (Connected App + integratiegebruiker).
- Scan_Run__c upserten op Run_Key__c (idempotent).
- Leads aanmaken via de Composite sObject Collections API, zónder
  duplicate-rule-override: een blokkade door de duplicate rule is laag 4.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from simple_salesforce import Salesforce

from . import config

log = logging.getLogger(__name__)

SEGMENT_SOQL = (
    "SELECT Id, Name, Target_Industry__c, Signal_Type__c, Search_Strategy__c, Weight__c, Exploration__c, "
    "Leads_Created__c, Leads_Qualified__c, Leads_Unqualified__c, Opportunities_Created__c, Deals_Won__c "
    "FROM Scan_Segment__c WHERE Active__c = true ORDER BY Name"
)
SETTINGS_SOQL = (
    "SELECT Kill_Switch__c, Max_Leads_Per_Run__c, Minimum_Score__c, Max_Searches_Per_Candidate__c, "
    "Max_Runtime_Minutes__c, Exploration_Share__c, Max_Weight_Change__c, Learning_Enabled__c "
    "FROM Lead_Scan_Setting__mdt WHERE DeveloperName = 'Default'"
)
COLLECTION_SIZE = 200  # maximum van de sObject Collections API


@dataclass
class InsertResult:
    index: int
    id: str | None
    duplicate: bool
    errors: list[str]


def _soql_quote(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


class SalesforceClient:
    def __init__(self, sf: Salesforce, username: str | None = None):
        self.sf = sf
        self.username = username
        self._user_id: str | None = None

    @classmethod
    def login(cls, env: config.Env) -> "SalesforceClient":
        sf = Salesforce(
            username=env.sf_username,
            consumer_key=env.sf_consumer_key,
            privatekey=env.sf_private_key,
            domain=env.sf_domain,
        )
        return cls(sf, env.sf_username)

    @property
    def instance_url(self) -> str:
        return f"https://{self.sf.sf_instance}"

    # ---- lezen -------------------------------------------------------------

    def query_all(self, soql: str) -> list[dict]:
        return self.sf.query_all(soql)["records"]

    def settings(self) -> config.Settings:
        records = self.query_all(SETTINGS_SOQL)
        if not records:
            raise RuntimeError("Lead_Scan_Setting__mdt record 'Default' ontbreekt")
        return config.Settings.from_record(records[0])

    def active_segments(self) -> list[config.Segment]:
        return [config.Segment.from_record(r) for r in self.query_all(SEGMENT_SOQL)]

    def queue_id(self) -> str:
        records = self.query_all(
            f"SELECT Id FROM Group WHERE Type = 'Queue' AND DeveloperName = '{config.QUEUE_DEVELOPER_NAME}'"
        )
        if not records:
            raise RuntimeError(f"Queue {config.QUEUE_DEVELOPER_NAME} bestaat niet")
        return records[0]["Id"]

    def partner_account_id(self, partner_name: str | None) -> str | None:
        """Current_SF_Partner__c is een lookup: alleen vullen als de partner als Account bestaat."""
        if not partner_name:
            return None
        records = self.query_all(
            f"SELECT Id FROM Account WHERE Name = '{_soql_quote(partner_name)}' "
            f"AND Type IN ('Partner', 'Competitor') LIMIT 2"
        )
        return records[0]["Id"] if len(records) == 1 else None

    def recent_won_customers(self, limit: int = 15) -> list[dict]:
        """Klanten met een gewonnen opportunity in de laatste 12 maanden: voorbeelden voor lookalikes."""
        records = self.query_all(
            "SELECT AccountId, Account.Name, Account.Industry, Account.Website, CloseDate "
            "FROM Opportunity WHERE IsWon = true AND CloseDate = LAST_N_MONTHS:12 AND AccountId != null "
            "ORDER BY CloseDate DESC LIMIT 200"
        )
        seen, out = set(), []
        for r in records:
            acc = r.get("Account") or {}
            if r["AccountId"] in seen or not acc.get("Name"):
                continue
            seen.add(r["AccountId"])
            # Alleen velden waar de permission set leesrecht op geeft (geen adresvelden).
            out.append({"name": acc["Name"], "industry": acc.get("Industry"), "website": acc.get("Website")})
            if len(out) >= limit:
                break
        return out

    def get_run(self, run_key: str) -> dict | None:
        records = self.query_all(
            "SELECT Id, Status__c, Started__c, Finished__c, Leads_Created__c FROM Scan_Run__c "
            f"WHERE Run_Key__c = '{_soql_quote(run_key)}' LIMIT 1"
        )
        return records[0] if records else None

    def user_id(self) -> str:
        """Id van de integratiegebruiker; alle scan-leads zijn door deze gebruiker aangemaakt."""
        if self._user_id is None:
            records = self.query_all(f"SELECT Id FROM User WHERE Username = '{_soql_quote(self.username or '')}'")
            if not records:
                raise RuntimeError("Integratiegebruiker niet gevonden")
            self._user_id = records[0]["Id"]
        return self._user_id

    def scan_leads_between(self, started: str, finished: str | None = None) -> list[dict]:
        """Scan-leads van één run: LeadSource + integratiegebruiker + aanmaakmoment binnen de run.

        Er is bewust geen lookup naar Scan_Run__c op Lead; dit filter vervangt die.
        `started` en `finished` zijn Salesforce-datetimes (bv. 2026-10-04T20:07:00Z).
        """
        soql = (
            "SELECT Id, Company, Website, CreatedDate FROM Lead "
            f"WHERE LeadSource = '{_soql_quote(config.LEAD_SOURCE)}' AND CreatedById = '{self.user_id()}' "
            f"AND CreatedDate >= {started}"
        )
        if finished:
            soql += f" AND CreatedDate <= {finished}"
        return self.query_all(soql)

    # ---- schrijven ---------------------------------------------------------

    def upsert_run(self, run_key: str, fields: dict) -> str:
        """Upsert Scan_Run__c op Run_Key__c en geef het record-Id terug."""
        self.sf.Scan_Run__c.upsert(f"Run_Key__c/{run_key}", fields)
        run = self.get_run(run_key)
        if not run:
            raise RuntimeError(f"Scan_Run__c {run_key} niet gevonden na upsert")
        return run["Id"]

    def insert_leads(self, leads: list[dict]) -> list[InsertResult]:
        """Composite insert, allOrNone=false. Geen DuplicateRuleHeader: de duplicate rule blokkeert."""
        results: list[InsertResult] = []
        for start in range(0, len(leads), COLLECTION_SIZE):
            chunk = leads[start : start + COLLECTION_SIZE]
            body = {
                "allOrNone": False,
                "records": [{"attributes": {"type": "Lead"}, **lead} for lead in chunk],
            }
            response = self.sf.restful("composite/sobjects", method="POST", json=body)
            for offset, item in enumerate(response):
                errors = item.get("errors") or []
                codes = {e.get("statusCode") for e in errors}
                results.append(
                    InsertResult(
                        index=start + offset,
                        id=item.get("id") if item.get("success") else None,
                        duplicate="DUPLICATES_DETECTED" in codes,
                        errors=[f"{e.get('statusCode')}: {e.get('message')}" for e in errors],
                    )
                )
        return results

    def create_task(self, fields: dict) -> str:
        result = self.sf.Task.create(fields)
        return result["id"]

    def update_segment(self, segment_id: str, fields: dict) -> None:
        self.sf.Scan_Segment__c.update(segment_id, fields)

    def create_segment(self, fields: dict) -> str:
        return self.sf.Scan_Segment__c.create(fields)["id"]

    def all_segments(self) -> list[dict]:
        return self.query_all("SELECT Id, Name FROM Scan_Segment__c")

"""Vertaling van een verrijkte lead (JSON van Claude) naar Salesforce-records. Code, geen oordeel."""

from __future__ import annotations

from datetime import date, timedelta

from . import config
from .icp import ICP_VERSION
from .matching import ExistingRecord, normalize_domain, normalize_kvk
from .schemas import SUB_INDUSTRY_BY_INDUSTRY

DESCRIPTION_MAX = 32000


def _cut(text: str | None, limit: int) -> str | None:
    if text is None:
        return None
    text = text.strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def source_urls(lead: dict, candidate: dict) -> list[str]:
    urls = list(candidate.get("source_urls", [])) + [c["source_url"] for c in lead["claims"]]
    return list(dict.fromkeys(urls))  # uniek, volgorde behouden


def description(lead: dict, candidate: dict, run_key: str) -> str:
    """Alles wat sales nodig heeft, zonder extra velden op Lead."""
    parts = [
        f"Openingszin: {lead['opening_line']}",
        f"Waarom nu: {lead['why_now']}",
        f"Signaal ({candidate['signal_type']}): {candidate['signal_summary']}",
        f"Projectinschatting: {lead['project_estimate']}",
        f"Score {lead['score']}/100 (ICP {ICP_VERSION}): {lead['score_rationale']}",
        f"Rol om te benaderen: {lead['contact_role']}",
    ]
    kvk = normalize_kvk(lead.get("kvk_number"))
    if kvk:
        parts.append(f"KvK-nummer: {kvk}")
    if lead.get("current_crm"):
        parts.append(f"Huidig CRM: {lead['current_crm']}")
    if lead.get("current_sf_partner"):
        parts.append(f"Huidige Salesforce-partner: {lead['current_sf_partner']}")
    parts.append("Onderbouwing:")
    parts += [f"- {c['claim']} ({c['source_url']})" for c in lead["claims"]]
    parts.append("Bronnen:")
    parts += [f"- {u}" for u in source_urls(lead, candidate)]
    parts.append(f"Aangemaakt door de wekelijkse leadscan (Claude), run {run_key}. Controleer de bronnen voor gebruik.")
    return _cut("\n".join(parts), DESCRIPTION_MAX)


def lead_record(
    lead: dict,
    candidate: dict,
    *,
    run_key: str,
    queue_id: str,
    partner_account_id: str | None,
) -> dict:
    """Lead-velden. Nieuw op Lead zijn alleen Scan_Score__c en Scan_Segment__c; de rest staat in Description."""
    industry = lead["industry"]
    sub = lead.get("sub_industry")
    if sub not in SUB_INDUSTRY_BY_INDUSTRY.get(industry, []):
        sub = None  # afhankelijke picklist: alleen geldige combinaties
    record = {
        "Company": _cut(lead["company_name"], 255),
        "LastName": config.PLACEHOLDER_LAST_NAME,
        "Title": _cut(lead["contact_role"], 128),
        "Website": normalize_domain(lead["domain"]) or normalize_domain(candidate["domain"]),
        "Industry": industry,
        "Sub_Industry__c": sub,
        "NumberOfEmployees": lead.get("employees_estimate"),
        "City": _cut(lead.get("city"), 40),
        "Country": _cut(lead.get("country"), 80),
        "Huidige_CRM__c": lead.get("current_crm"),
        "Current_SF_Partner__c": partner_account_id,
        "Need_Pain__c": _cut(lead["why_now"], 255),
        "Description": description(lead, candidate, run_key),
        "LeadSource": config.LEAD_SOURCE,
        "Status": config.LEAD_STATUS,
        "OwnerId": queue_id,
        "Scan_Score__c": lead["score"],
        "Scan_Segment__c": candidate["segment_id"],
    }
    return {k: v for k, v in record.items() if v not in (None, "")}


def task_record(target: ExistingRecord, candidate: dict, today: date | None = None) -> dict | None:
    """Task voor de eigenaar van een bestaand record; None als de eigenaar geen gebruiker is (bv. een queue)."""
    if not target.owner_id or not target.owner_id.startswith("005"):
        return None
    today = today or date.today()
    body = "\n".join(
        [
            f"De wekelijkse leadscan vond een signaal bij {target.name}.",
            f"Signaal ({candidate['signal_type']}): {candidate['signal_summary']}",
            "Bronnen:",
            *[f"- {u}" for u in candidate.get("source_urls", [])],
            "Er is bewust geen nieuwe lead aangemaakt, omdat deze organisatie al in Salesforce staat.",
        ]
    )
    record = {
        "Subject": _cut(f"Leadscan: signaal ({candidate['signal_type']}) bij {target.name}", 255),
        "Description": _cut(body, DESCRIPTION_MAX),
        "OwnerId": target.owner_id,
        "ActivityDate": (today + timedelta(days=7)).isoformat(),
    }
    record["WhatId" if target.object == "Account" else "WhoId"] = target.id
    return record

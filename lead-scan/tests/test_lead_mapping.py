from datetime import date

from runner.lead_mapping import lead_record, task_record
from runner.matching import ExistingRecord

from test_schemas import enriched

CAND = {"company_name": "Voorbeeld Fonds", "domain": "https://www.voorbeeldfonds.nl", "signal_type": "Vacancy",
        "signal_summary": "Vacature CRM-beheerder", "source_urls": ["https://werk.nl/v/1"], "segment_id": "a0S1"}


def test_lead_record_field_mapping():
    rec = lead_record(enriched(why_now="w" * 255), CAND, run_key="2026-W41", queue_id="00G1", partner_account_id=None)
    assert rec["LastName"] == "Onbekend"
    assert rec["LeadSource"] == "Claude Weekly Scan" and rec["Status"] == "New" and rec["OwnerId"] == "00G1"
    assert rec["Website"] == "voorbeeldfonds.nl"
    assert rec["Title"] == "Manager Fondsenwerving"
    assert rec["Sub_Industry__c"] == "Fondsenwervers"
    assert rec["Scan_Segment__c"] == "a0S1" and rec["Scan_Score__c"] == 82
    assert {k for k in rec if k.startswith("Scan_")} == {"Scan_Score__c", "Scan_Segment__c"}
    assert "Chamber_of_Commerce_Number__c" not in rec
    assert len(rec["Need_Pain__c"]) <= 255
    assert "Current_SF_Partner__c" not in rec  # lookup alleen als Account bestaat
    # Wat geen eigen veld meer heeft, staat in Description.
    desc = rec["Description"]
    assert desc.startswith("Openingszin: Ik zag dat jullie een CRM-functioneel beheerder zoeken.")
    assert "Signaal (Vacancy): Vacature CRM-beheerder" in desc
    assert "KvK-nummer: 12345670" in desc
    assert "- https://werk.nl/v/1" in desc and "- https://voorbeeldfonds.nl/vacatures/crm" in desc
    assert "run 2026-W41" in desc


def test_invalid_sub_industry_combination_is_dropped():
    rec = lead_record(enriched(industry="Education", sub_industry="Fondsenwervers"), CAND,
                      run_key="r", queue_id="q", partner_account_id="001P")
    assert "Sub_Industry__c" not in rec and rec["Current_SF_Partner__c"] == "001P"


def test_task_record():
    target = ExistingRecord("001B", "Account", "Vastgoedpartners Oost", owner_id="005U")
    task = task_record(target, CAND, today=date(2026, 10, 5))
    assert task["OwnerId"] == "005U" and task["WhatId"] == "001B" and task["ActivityDate"] == "2026-10-12"
    lead_target = ExistingRecord("00QL", "Lead", "X", owner_id="005U")
    assert task_record(lead_target, CAND)["WhoId"] == "00QL"
    assert task_record(ExistingRecord("00QL", "Lead", "X", owner_id="00G9"), CAND) is None  # queue

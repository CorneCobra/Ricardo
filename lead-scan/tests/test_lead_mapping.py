from datetime import date

from runner.lead_mapping import lead_record, task_record
from runner.matching import ExistingRecord

from test_schemas import enriched

CAND = {"company_name": "Voorbeeld Fonds", "domain": "https://www.voorbeeldfonds.nl", "signal_type": "Vacancy",
        "signal_summary": "Vacature CRM-beheerder", "source_urls": ["https://werk.nl/v/1"], "segment_id": "a0S1"}


def test_lead_record_field_mapping():
    rec = lead_record(enriched(why_now="w" * 255), CAND, run_id="a0R1", queue_id="00G1", partner_account_id=None)
    assert rec["LastName"] == "Onbekend"
    assert rec["LeadSource"] == "Claude Weekly Scan" and rec["Status"] == "New" and rec["OwnerId"] == "00G1"
    assert rec["Website"] == "voorbeeldfonds.nl"
    assert rec["Title"] == "Manager Fondsenwerving"
    assert rec["Sub_Industry__c"] == "Fondsenwervers"
    assert rec["Scan_Run__c"] == "a0R1" and rec["Scan_Segment__c"] == "a0S1"
    assert rec["Scan_Signal__c"] == "Vacancy" and rec["Scan_Score__c"] == 82
    assert len(rec["Need_Pain__c"]) <= 255
    assert rec["Scan_Sources__c"].splitlines() == ["https://werk.nl/v/1", "https://voorbeeldfonds.nl/vacatures/crm"]
    assert "Vacature CRM-beheerder" in rec["Description"]
    assert "Current_SF_Partner__c" not in rec  # lookup alleen als Account bestaat


def test_invalid_sub_industry_combination_is_dropped():
    rec = lead_record(enriched(industry="Education", sub_industry="Fondsenwervers"), CAND,
                      run_id="r", queue_id="q", partner_account_id="001P")
    assert "Sub_Industry__c" not in rec and rec["Current_SF_Partner__c"] == "001P"


def test_task_record():
    target = ExistingRecord("001B", "Account", "Realiance", owner_id="005U")
    task = task_record(target, CAND, today=date(2026, 10, 5))
    assert task["OwnerId"] == "005U" and task["WhatId"] == "001B" and task["ActivityDate"] == "2026-10-12"
    lead_target = ExistingRecord("00QL", "Lead", "X", owner_id="005U")
    assert task_record(lead_target, CAND)["WhoId"] == "00QL"
    assert task_record(ExistingRecord("00QL", "Lead", "X", owner_id="00G9"), CAND) is None  # queue

from datetime import datetime, timezone

from runner.learning import compute_segment_metrics


def test_compute_segment_metrics():
    leads = [
        {"Scan_Segment__c": "S1", "Status": "New"},
        {"Scan_Segment__c": "S1", "Status": "Unqualified"},
        {"Scan_Segment__c": "S1", "Status": "Qualified"},
        {"Scan_Segment__c": "S1", "Status": "Converted", "IsConverted": True, "ConvertedOpportunityId": "006A",
         "ConvertedOpportunity": {"IsWon": True}},
        {"Scan_Segment__c": "S2", "Status": "Converted", "IsConverted": True, "ConvertedOpportunityId": "006B",
         "ConvertedOpportunity": {"IsWon": False}},
    ]
    m = compute_segment_metrics(leads, datetime(2026, 10, 4, tzinfo=timezone.utc))
    assert m["S1"]["Leads_Created__c"] == 4 and m["S1"]["Leads_Qualified__c"] == 2
    assert m["S1"]["Leads_Unqualified__c"] == 1 and m["S1"]["Deals_Won__c"] == 1
    assert m["S1"]["Conversion_Rate__c"] == 25.0
    assert m["S2"]["Opportunities_Created__c"] == 1 and m["S2"]["Deals_Won__c"] == 0
    assert m["S1"]["Last_Evaluated__c"] == "2026-10-04T00:00:00Z"

from datetime import datetime, timezone

from runner.exclusion import build_account_records, build_lead_records


def _acc(id_, name, type_=None, parent=None, website=None, close=None, kvk=None):
    return {"Id": id_, "Name": name, "Type": type_, "ParentId": parent, "Website": website, "OwnerId": "005O",
            "Close_Date_first_Opportunity__c": close, "Chamber_of_Commerce_Number__c": kvk}


def test_customer_tree_types_and_close_date():
    accounts = [
        _acc("A1", "Moeder", "Prospect"),
        _acc("A2", "Klant-dochter", "Customer", parent="A1"),
        _acc("A3", "Zuster", "Suspect", parent="A1"),
        _acc("A4", "Kleindochter", None, parent="A3"),
        _acc("B1", "Losse prospect", "Prospect"),
        _acc("C1", "Concurrent", "Competitor"),
        _acc("D1", "Ooit gewonnen", "No prospect", close="2020-01-01"),
        _acc("E1", "Slapend", "Customer - sleeping"),
    ]
    recs = {r.id: r for r in build_account_records(accounts, [])}
    assert all(recs[i].excluded for i in ("A1", "A2", "A3", "A4", "C1", "D1", "E1"))
    assert not recs["B1"].excluded
    assert "boom" in recs["A4"].exclusion_reason


def test_parent_cycle_does_not_hang():
    accounts = [_acc("X", "X", "Prospect", parent="Y"), _acc("Y", "Y", "Customer", parent="X")]
    recs = build_account_records(accounts, [])
    assert all(r.excluded for r in recs)


def test_contact_email_domains_and_shared_domains():
    accounts = [_acc(f"A{i}", f"Org {i}") for i in range(6)] + [_acc("K", "Klant", "Customer", kvk="5047024")]
    contacts = [{"AccountId": "K", "Email": "a@klant.nl.invalid"}, {"AccountId": "K", "Email": "b@gmail.com"}]
    # een adviesbureau met contactpersonen bij 6 verschillende organisaties
    contacts += [{"AccountId": f"A{i}", "Email": f"x{i}@adviesbureau.nl"} for i in range(6)]
    recs = {r.id: r for r in build_account_records(accounts, contacts)}
    assert recs["K"].domains == {"klant.nl"}
    assert recs["K"].kvks == {"05047024"}
    assert all("adviesbureau.nl" not in recs[f"A{i}"].domains for i in range(6))


def test_lead_exclusions():
    now = datetime(2026, 10, 1, tzinfo=timezone.utc)
    leads = [
        {"Id": "L1", "Company": "Oud-klant", "Status": "Unqualified", "Reason_unqualified__c": "Former customer",
         "LastModifiedDate": "2019-01-01T00:00:00.000+0000"},
        {"Id": "L2", "Company": "Recent af", "Status": "Unqualified", "Reason_unqualified__c": "No Budget",
         "LastModifiedDate": "2026-06-01T00:00:00.000+0000"},
        {"Id": "L3", "Company": "Lang geleden af", "Status": "Unqualified", "Reason_unqualified__c": "No Budget",
         "LastModifiedDate": "2024-06-01T00:00:00.000+0000"},
        {"Id": "L4", "Company": "Open", "Status": "New", "Email": "x@open.nl.invalid", "Website": "www.open.nl"},
    ]
    recs = {r.id: r for r in build_lead_records(leads, now)}
    assert recs["L1"].excluded and recs["L2"].excluded
    assert not recs["L3"].excluded and not recs["L4"].excluded
    assert recs["L4"].domains == {"open.nl"}

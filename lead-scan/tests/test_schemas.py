from runner.schemas import (
    CANDIDATE_SCHEMA,
    ENRICHED_LEAD_SCHEMA,
    pii_violations,
    strict_schema,
    validate,
)


def enriched(**over):
    lead = {
        "company_name": "Voorbeeld Fonds", "domain": "voorbeeldfonds.nl", "kvk_number": "12345670",
        "industry": "Nonprofit", "sub_industry": "Fondsenwervers", "employees_estimate": 120,
        "city": "Utrecht", "country": "Nederland", "current_crm": "Overig", "current_sf_partner": None,
        "why_now": "Vacature voor CRM-functioneel beheerder geplaatst in september.",
        "project_estimate": "Vervanging van het huidige donateursysteem door Salesforce NPC.",
        "contact_role": "Manager Fondsenwerving",
        "opening_line": "Ik zag dat jullie een CRM-functioneel beheerder zoeken.",
        "score": 82, "score_rationale": "Kernbranche, passende grootte, recent CRM-signaal.",
        "claims": [{"claim": "Vacature CRM-beheerder", "source_url": "https://voorbeeldfonds.nl/vacatures/crm"}],
    }
    lead.update(over)
    return lead


def test_valid_enriched_lead():
    assert validate(enriched(), ENRICHED_LEAD_SCHEMA) == []


def test_rejects_out_of_bounds_values():
    assert validate(enriched(why_now="x" * 256), ENRICHED_LEAD_SCHEMA)
    assert validate(enriched(score=101), ENRICHED_LEAD_SCHEMA)
    assert validate(enriched(industry="HigherEducation"), ENRICHED_LEAD_SCHEMA)
    assert validate(enriched(kvk_number="123"), ENRICHED_LEAD_SCHEMA)
    assert validate(enriched(claims=[]), ENRICHED_LEAD_SCHEMA)
    assert validate(enriched(extra="nee"), ENRICHED_LEAD_SCHEMA)
    assert validate(enriched(current_crm="Dynamics"), ENRICHED_LEAD_SCHEMA)


def test_candidate_schema():
    cand = {"company_name": "Voorbeeld", "domain": "voorbeeld.nl", "signal_type": "Vacancy",
            "signal_summary": "Vacature CRM-beheerder", "source_urls": ["https://voorbeeld.nl/v"], "segment_id": "a0X"}
    assert validate(cand, CANDIDATE_SCHEMA) == []
    assert validate({**cand, "source_urls": ["ftp://x"]}, CANDIDATE_SCHEMA)
    assert validate({**cand, "signal_type": "Gossip"}, CANDIDATE_SCHEMA)


def test_strict_schema_removes_unsupported_keywords_only():
    strict = strict_schema(ENRICHED_LEAD_SCHEMA)
    text = str(strict)
    for kw in ("maxLength", "minLength", "minimum", "maximum", "pattern", "minItems", "maxItems"):
        assert kw not in text
    assert strict["additionalProperties"] is False
    assert strict["required"] == ENRICHED_LEAD_SCHEMA["required"]
    assert "maxLength" in str(ENRICHED_LEAD_SCHEMA)  # origineel onaangetast


def test_pii_violations():
    assert pii_violations(enriched()) == []
    assert pii_violations(enriched(contact_role="Jan, jan@voorbeeld.nl"))
    assert pii_violations(enriched(opening_line="Bel ons op 06-12345678 voor meer info graag"))
    bad = enriched(claims=[{"claim": "x", "source_url": "https://www.linkedin.com/in/jan"}])
    assert pii_violations(bad)
    assert pii_violations(enriched(kvk_number="01169476")) == []  # KvK is geen telefoonnummer

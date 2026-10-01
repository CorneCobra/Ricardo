"""JSON-schema's voor alles wat Claude teruggeeft, plus validatie.

Claude levert uitsluitend JSON via een strikte tool-aanroep. De API dwingt de
structuur af; deze module controleert daarnaast de grenzen die de API niet
afdwingt (lengtes, bereik, AVG) en verwerpt elke afwijking.
"""

from __future__ import annotations

import copy
import re

import jsonschema

# Actieve API-waarden van Lead.Industry in de testomgeving (geverifieerd 2026-10-01).
INDUSTRY_VALUES = [
    "Agriculture & Food",
    "Automotive",
    "Construction",
    "Consultancy & Professional Services",
    "Consumer Goods & Retail",
    "Culture, Sports & Recreation",
    "Education",
    "Energy & Utilities",
    "Financial Services",
    "Government & Public Sector",
    "Healthcare & Life Sciences",
    "Hospitality & Tourism",
    "Insurance & Pensions",
    "IT Services",
    "Logistics & Transportation",
    "Manufacturing",
    "Media & Communications",
    "Nonprofit",
    "Real Estate",
    "Recruitment & Staffing",
    "Social Housing",
    "Social Services & Welfare",
    "Software",
    "Telecommunications, Hardware & Electronics",
    "Wholesale & Trade",
    "_Other",
]

# Lead.Huidige_CRM__c (gelijk aan Account.Huidig_CRM__c), actieve waarden in de testomgeving.
CRM_VALUES = [
    "Afas", "Databalk - Iris", "Embrace", "Engage 365", "Fundmaster", "Geen", "Hubspot", "Intergrip",
    "Manyware", "MS CRM", "MS CRM + Summit", "MS Engage", "Nexios", "Overig", "Peoplesoft", "Pipedrive",
    "Pluriform", "Portal-plus", "Salesforce", "Salesforce + Converse", "Salesforce + Converse 1",
    "Salesforce + NPC", "Salesforce + NPSP", "Siebel", "Sugar CRM", "Summit", "Teamviewer", "Tobias",
    "ZIG", "ZOHO",
]

# Lead.Sub_Industry__c is afhankelijk van Industry. De koppeling van 'Sociaal Ontwikkelbedrijf'
# is nog niet in de data gezien: controleren in Setup (Field Dependencies).
SUB_INDUSTRY_BY_INDUSTRY = {
    "Nonprofit": ["Fondsenwervers", "Ledenverenigingen"],
    "Social Services & Welfare": ["Sociaal Ontwikkelbedrijf"],
}
SUB_INDUSTRY_VALUES = sorted({v for values in SUB_INDUSTRY_BY_INDUSTRY.values() for v in values})

SIGNAL_TYPES = ["Vacancy", "Merger", "Reorganisation", "Tender", "Growth", "Lookalike", "Other"]

TEXT_255 = 255


def _nullable(schema: dict) -> dict:
    return {"anyOf": [schema, {"type": "null"}]}


CANDIDATE_SCHEMA = {
    "type": "object",
    "properties": {
        "company_name": {"type": "string", "minLength": 2, "maxLength": TEXT_255},
        "domain": {"type": "string", "minLength": 3, "maxLength": TEXT_255},
        "signal_type": {"type": "string", "enum": SIGNAL_TYPES},
        "signal_summary": {"type": "string", "minLength": 10, "maxLength": 1000},
        "source_urls": {
            "type": "array",
            "items": {"type": "string", "pattern": "^https?://"},
            "minItems": 1,
            "maxItems": 10,
        },
        "segment_id": {"type": "string"},
    },
    "required": ["company_name", "domain", "signal_type", "signal_summary", "source_urls", "segment_id"],
    "additionalProperties": False,
}

CANDIDATES_TOOL_SCHEMA = {
    "type": "object",
    "properties": {"candidates": {"type": "array", "items": CANDIDATE_SCHEMA, "maxItems": 25}},
    "required": ["candidates"],
    "additionalProperties": False,
}

ENRICHED_LEAD_SCHEMA = {
    "type": "object",
    "properties": {
        "company_name": {"type": "string", "minLength": 2, "maxLength": TEXT_255},
        "domain": {"type": "string", "minLength": 3, "maxLength": TEXT_255},
        "kvk_number": _nullable({"type": "string", "pattern": "^[0-9]{8}$"}),
        "industry": {"type": "string", "enum": INDUSTRY_VALUES},
        "sub_industry": _nullable({"type": "string", "enum": SUB_INDUSTRY_VALUES}),
        "employees_estimate": _nullable({"type": "integer", "minimum": 1, "maximum": 10_000_000}),
        "city": {"type": "string", "maxLength": 40},
        "country": {"type": "string", "maxLength": 80},
        "current_crm": _nullable({"type": "string", "enum": CRM_VALUES}),
        "current_sf_partner": _nullable({"type": "string", "maxLength": TEXT_255}),
        "why_now": {"type": "string", "minLength": 10, "maxLength": TEXT_255},
        "project_estimate": {"type": "string", "minLength": 10, "maxLength": 2000},
        "contact_role": {"type": "string", "minLength": 2, "maxLength": 128},
        "opening_line": {"type": "string", "minLength": 10, "maxLength": TEXT_255},
        "score": {"type": "integer", "minimum": 0, "maximum": 100},
        "score_rationale": {"type": "string", "minLength": 10, "maxLength": 2000},
        "claims": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "claim": {"type": "string", "minLength": 3, "maxLength": 500},
                    "source_url": {"type": "string", "pattern": "^https?://"},
                },
                "required": ["claim", "source_url"],
                "additionalProperties": False,
            },
            "minItems": 1,
            "maxItems": 20,
        },
    },
    "required": [
        "company_name", "domain", "kvk_number", "industry", "sub_industry", "employees_estimate",
        "city", "country", "current_crm", "current_sf_partner", "why_now", "project_estimate",
        "contact_role", "opening_line", "score", "score_rationale", "claims",
    ],
    "additionalProperties": False,
}

DOUBT_VERDICTS = ["same_organisation", "parent_or_subsidiary", "merger_partner", "different", "unsure"]

DOUBT_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": DOUBT_VERDICTS},
        "rationale": {"type": "string", "minLength": 5, "maxLength": 1000},
    },
    "required": ["verdict", "rationale"],
    "additionalProperties": False,
}

# Sleutels die structured outputs / strict tools niet ondersteunen; die controleren we zelf.
_UNSUPPORTED = {"minLength", "maxLength", "minimum", "maximum", "minItems", "maxItems", "pattern"}


def strict_schema(schema: dict) -> dict:
    """Kopie van een schema zonder de sleutels die de API bij strict tools weigert."""

    def strip(node):
        if isinstance(node, dict):
            return {k: strip(v) for k, v in node.items() if k not in _UNSUPPORTED}
        if isinstance(node, list):
            return [strip(v) for v in node]
        return node

    return strip(copy.deepcopy(schema))


def validate(data, schema: dict) -> list[str]:
    """Lege lijst als data aan het volledige schema voldoet, anders de fouten."""
    validator = jsonschema.Draft202012Validator(schema)
    return [f"{'/'.join(map(str, e.absolute_path)) or '<root>'}: {e.message}" for e in validator.iter_errors(data)]


_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"(?:\+|00)\d[\d\s\-()]{7,}\d|\b0\d{1,3}[\s-]?\d{6,8}\b")
_LINKEDIN_PERSON_RE = re.compile(r"linkedin\.com/in/", re.IGNORECASE)


# Velden met URL's of nummers die geen persoonsgegevens zijn.
_PII_SKIP_KEYS = {"kvk_number", "domain", "source_url", "source_urls"}


def pii_violations(data) -> list[str]:
    """AVG-vangnet: geen e-mailadressen, telefoonnummers of LinkedIn-profielen van personen."""
    found: list[str] = []

    def walk(node, path):
        if isinstance(node, dict):
            for k, v in node.items():
                if k in _PII_SKIP_KEYS:
                    if _LINKEDIN_PERSON_RE.search(str(v)):
                        found.append(f"{path}/{k}: LinkedIn-profiel")
                    continue
                walk(v, f"{path}/{k}")
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, f"{path}/{i}")
        elif isinstance(node, str):
            if _EMAIL_RE.search(node):
                found.append(f"{path}: e-mailadres")
            if _PHONE_RE.search(node):
                found.append(f"{path}: telefoonnummer")
            if _LINKEDIN_PERSON_RE.search(node):
                found.append(f"{path}: LinkedIn-profiel")

    walk(data, "")
    return found

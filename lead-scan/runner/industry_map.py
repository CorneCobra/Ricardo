"""Vertaling van oude, inactieve Industry-waarden naar de huidige picklist.

Gebaseerd op de waarden die op 2026-10-01 in de testomgeving op Account en Lead
voorkomen. `None` betekent: geen eenduidige vertaling, beslissing nodig door
sales/beheer (zie AMBIGUOUS). Vóór productie opnieuw controleren.
"""

from __future__ import annotations

from .schemas import INDUSTRY_VALUES

INDUSTRY_MAP: dict[str, str | None] = {
    # Onderwijs
    "HigherEducation": "Education",
    "Higher Education": "Education",
    "Education Administration Programs": "Education",
    # Nonprofit
    "Nonprofit & NGO": "Nonprofit",
    "Non profit": "Nonprofit",
    # Consultancy
    "Consultancy": "Consultancy & Professional Services",
    "Business Consulting and Services": "Consultancy & Professional Services",
    "Accounting": "Consultancy & Professional Services",
    "Law Practice": "Consultancy & Professional Services",
    "Human Resources": "Consultancy & Professional Services",
    # IT
    "Information Technology and Services": "IT Services",
    "IT Services and IT Consulting": "IT Services",
    "Information Services": "IT Services",
    "Software Development": "Software",
    # Energie
    "Energy": "Energy & Utilities",
    "Utilities": "Energy & Utilities",
    "Renewable Energy": "Energy & Utilities",
    "Services for Renewable Energy": "Energy & Utilities",
    "Oil and Gas": "Energy & Utilities",
    # Overheid
    "Public Sector": "Government & Public Sector",
    # Groothandel
    "Wholesale": "Wholesale & Trade",
    "Wholesale Import and Export": "Wholesale & Trade",
    "Wholesale Building Materials": "Wholesale & Trade",
    "International Trade and Development": "Wholesale & Trade",
    # Werving
    "RecruitmentStaffing": "Recruitment & Staffing",
    "Staffing and Recruiting": "Recruitment & Staffing",
    # Retail
    "Retail": "Consumer Goods & Retail",
    "Luxury Goods": "Consumer Goods & Retail",
    "Retail Office Equipment": "Consumer Goods & Retail",
    # Zorg en welzijn
    "Healthcare": "Healthcare & Life Sciences",
    "Hospitals and Health Care": "Healthcare & Life Sciences",
    "Health and Human Services": "Social Services & Welfare",
    "Childcare": "Social Services & Welfare",
    # Financieel
    "Finance": "Financial Services",
    "Financiele Dienstverlening": "Financial Services",
    "Insurance": "Insurance & Pensions",
    # Telecom/hardware
    "Telecommunications": "Telecommunications, Hardware & Electronics",
    "Hardware & Electronics": "Telecommunications, Hardware & Electronics",
    # Logistiek
    "Logistics": "Logistics & Transportation",
    "Transportation": "Logistics & Transportation",
    "Transportation/Trucking/Railroad": "Logistics & Transportation",
    "Transportation, Logistics, Supply Chain and Storage": "Logistics & Transportation",
    "Maritime Transportation": "Logistics & Transportation",
    # Horeca
    "Hospitality": "Hospitality & Tourism",
    "Food and Beverage Services": "Hospitality & Tourism",
    # Agrifood
    "Food Production": "Agriculture & Food",
    "Farming": "Agriculture & Food",
    "Horticulture": "Agriculture & Food",
    # Industrie
    "Industrial": "Manufacturing",
    "Industrial Machinery Manufacturing": "Manufacturing",
    "Machinery Manufacturing": "Manufacturing",
    "Mechanical or Industrial Engineering": "Manufacturing",
    "Packaging and Containers Manufacturing": "Manufacturing",
    "Textile Manufacturing": "Manufacturing",
    "Plastics Manufacturing": "Manufacturing",
    "Chemical Manufacturing": "Manufacturing",
    "Appliances, Electrical, and Electronics Manufacturing": "Manufacturing",
    "Shipbuilding": "Manufacturing",
    "Motor Vehicle Manufacturing": "Automotive",
    # Bouw en vastgoed
    "Civil Engineering": "Construction",
    "Leasing Non-residential Real Estate": "Real Estate",
    # Media
    "Broadcast Media Production and Distribution": "Media & Communications",
    "Public Relations and Communications Services": "Media & Communications",
    # Sport/recreatie
    "Wellness and Fitness Services": "Culture, Sports & Recreation",
    # Geen eenduidige vertaling: beslissing nodig.
    "Travel, Transportation & Hospitality": None,
    "Food and Beverage Manufacturing": None,
    "Food & Beverages": None,
    "Security and Investigations": None,
    "Facilities Services": None,
    "Environmental Services": None,
    "Printing Services": None,
    "Sustainability": None,
    "OPTIE STAAT ER NIET BIJ": None,
}

AMBIGUOUS = sorted(k for k, v in INDUSTRY_MAP.items() if v is None)


def map_industry(value: str | None) -> str | None:
    """Huidige picklistwaarde, of None als er geen (eenduidige) waarde is."""
    if not value:
        return None
    if value in INDUSTRY_VALUES:
        return value
    return INDUSTRY_MAP.get(value)

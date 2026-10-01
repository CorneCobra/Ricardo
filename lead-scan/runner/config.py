"""Configuratie: vaste waarden in code, instelbare waarden uit Salesforce.

Lead_Scan_Setting__mdt (record Default) en de actieve Scan_Segment__c-records
zijn de bron van waarheid. Wat hier als constante staat, wijzigt alleen via een
code-review én een geslaagde run op de gouden testset.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# Modelversie vastgepind. Wisselen alleen na een geslaagde run op de gouden testset.
MODEL = "claude-opus-5-5"
EFFORT = "high"
MAX_TOKENS = 64000
# Server-side fallback bij een weigering door de veiligheidsclassifiers.
FALLBACK_BETA = "server-side-fallback-2026-07-01"
WEB_SEARCH_TOOL = "web_search_20260209"
WEB_FETCH_TOOL = "web_fetch_20260209"

TIMEZONE = ZoneInfo("Europe/Amsterdam")

LEAD_SOURCE = "Claude Weekly Scan"
LEAD_STATUS = "New"
PLACEHOLDER_LAST_NAME = "Onbekend"
QUEUE_DEVELOPER_NAME = "Claude_Leads"

# Zoekbudget voor de ontdekfase (aantal web searches over alle segmenten samen).
DISCOVERY_SEARCH_BUDGET = 60
# Hoeveel kandidaten Claude per segment maximaal teruggeeft.
MAX_CANDIDATES_PER_SEGMENT = 15

# Laag 2: vanaf deze gelijkenis (0-1) op genormaliseerde naam is het een twijfelgeval.
FUZZY_DOUBT_THRESHOLD = 0.82

# Eigen domeinen: komen voor in e-mailadressen bij veel records en zijn geen sleutel.
OWN_DOMAINS = {"cobracrm.nl", "cobra.nl"}

# Leads die korter dan dit geleden Unqualified zijn gezet, vallen af (laag 1).
UNQUALIFIED_LOOKBACK_MONTHS = 12

ACCOUNT_TYPES_EXCLUDED = [
    "Customer",
    "Customer - sleeping",
    "Partner",
    "Competitor",
    "Supplier",
    "Broker / Recruiter",
]
CUSTOMER_TYPES = ["Customer", "Customer - sleeping"]
UNQUALIFIED_REASONS_EXCLUDED = ["Former customer", "Competitor", "Wrong industry"]


@dataclass(frozen=True)
class Settings:
    """Lead_Scan_Setting__mdt.Default."""

    kill_switch: bool = False
    max_leads_per_run: int = 10
    minimum_score: int = 70
    max_searches_per_candidate: int = 15
    max_runtime_minutes: int = 240
    exploration_share: float = 30.0
    max_weight_change: float = 20.0
    learning_enabled: bool = False

    @classmethod
    def from_record(cls, rec: dict) -> "Settings":
        def num(key, default):
            value = rec.get(key)
            return default if value is None else value

        return cls(
            kill_switch=bool(rec.get("Kill_Switch__c")),
            max_leads_per_run=int(num("Max_Leads_Per_Run__c", 10)),
            minimum_score=int(num("Minimum_Score__c", 70)),
            max_searches_per_candidate=int(num("Max_Searches_Per_Candidate__c", 15)),
            max_runtime_minutes=int(num("Max_Runtime_Minutes__c", 240)),
            exploration_share=float(num("Exploration_Share__c", 30)),
            max_weight_change=float(num("Max_Weight_Change__c", 20)),
            learning_enabled=bool(rec.get("Learning_Enabled__c")),
        )


@dataclass
class Segment:
    """Scan_Segment__c."""

    id: str
    name: str
    target_industry: str | None
    signal_type: str | None
    search_strategy: str
    weight: float
    exploration: bool
    leads_created: int = 0
    leads_qualified: int = 0
    leads_unqualified: int = 0
    opportunities_created: int = 0
    deals_won: int = 0

    @classmethod
    def from_record(cls, rec: dict) -> "Segment":
        def n(key):
            return int(rec.get(key) or 0)

        return cls(
            id=rec["Id"],
            name=rec["Name"],
            target_industry=rec.get("Target_Industry__c"),
            signal_type=rec.get("Signal_Type__c"),
            search_strategy=rec.get("Search_Strategy__c") or "",
            weight=float(rec.get("Weight__c") or 0),
            exploration=bool(rec.get("Exploration__c")),
            leads_created=n("Leads_Created__c"),
            leads_qualified=n("Leads_Qualified__c"),
            leads_unqualified=n("Leads_Unqualified__c"),
            opportunities_created=n("Opportunities_Created__c"),
            deals_won=n("Deals_Won__c"),
        )


@dataclass(frozen=True)
class Env:
    """Secrets en omgevingsinstellingen; in GitHub Actions als secrets/variables gezet."""

    sf_username: str
    sf_consumer_key: str
    sf_private_key: str
    sf_domain: str
    slack_token: str | None
    slack_channel: str

    @classmethod
    def load(cls) -> "Env":
        missing = [k for k in ("SF_USERNAME", "SF_CONSUMER_KEY", "SF_PRIVATE_KEY") if not os.environ.get(k)]
        if missing:
            raise RuntimeError(f"Ontbrekende omgevingsvariabelen: {', '.join(missing)}")
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise RuntimeError("Ontbrekende omgevingsvariabele: ANTHROPIC_API_KEY")
        return cls(
            sf_username=os.environ["SF_USERNAME"],
            sf_consumer_key=os.environ["SF_CONSUMER_KEY"],
            sf_private_key=os.environ["SF_PRIVATE_KEY"],
            # 'test' = sandbox/testomgeving. Productie alleen na expliciet akkoord.
            sf_domain=os.environ.get("SF_DOMAIN", "test"),
            slack_token=os.environ.get("SLACK_BOT_TOKEN") or None,
            slack_channel=os.environ.get("SLACK_CHANNEL", "#claude-leads"),
        )


def run_key(now: datetime | None = None) -> str:
    """ISO-week van de maandag waarop de leads klaar moeten staan, bv. 2026-W41.

    De run start zondagavond; de leads horen bij de week die maandag begint.
    """
    now = (now or datetime.now(TIMEZONE)).astimezone(TIMEZONE)
    target = now + timedelta(days=1) if now.weekday() == 6 else now
    year, week, _ = target.isocalendar()
    return f"{year}-W{week:02d}"


@dataclass
class Deadline:
    """Harde looptijdgrens uit Max_Runtime_Minutes__c."""

    started: datetime
    minutes: int
    reserve_minutes: int = 10  # tijd om netjes weg te schrijven en te rapporteren
    clock: object = field(default=None, repr=False)

    def now(self) -> datetime:
        return self.clock() if self.clock else datetime.now(TIMEZONE)

    def expired(self) -> bool:
        limit = self.started + timedelta(minutes=max(self.minutes - self.reserve_minutes, 0))
        return self.now() >= limit

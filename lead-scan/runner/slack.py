"""Slack-berichten naar #claude-leads: weekupdate (maandag 08:00) en foutmeldingen."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from . import config

log = logging.getLogger(__name__)


def monday_0800(now: datetime) -> datetime | None:
    """Eerstvolgende maandag 08:00 (Europe/Amsterdam), of None als die al voorbij is (maandag na 08:00)."""
    now = now.astimezone(config.TIMEZONE)
    days = (7 - now.weekday()) % 7
    target = (now + timedelta(days=days)).replace(hour=8, minute=0, second=0, microsecond=0)
    return target if target > now else None


def weekly_text(stats: dict, top: list[dict], run_url: str | None, warnings: list[str]) -> str:
    blocked = sum(stats.get(f"Blocked_Layer_{i}__c", 0) for i in range(1, 5))
    lines = [
        f"*Leadscan {stats.get('run_key', '')}*: {stats.get('Leads_Created__c', 0)} nieuwe leads in de queue Claude Leads",
        f"Kandidaten {stats.get('Candidates_Found__c', 0)} · tegengehouden {blocked} "
        f"(L1 {stats.get('Blocked_Layer_1__c', 0)} / L2 {stats.get('Blocked_Layer_2__c', 0)} / "
        f"L3 {stats.get('Blocked_Layer_3__c', 0)} / L4 {stats.get('Blocked_Layer_4__c', 0)}) · "
        f"onder drempel {stats.get('Below_Threshold__c', 0)} · signalen naar bestaande eigenaren "
        f"{stats.get('Signals_To_Existing__c', 0)}",
    ]
    if top:
        lines.append("*Top 5*")
        for i, lead in enumerate(top[:5], 1):
            lines.append(f"{i}. {lead['company_name']} – score {lead['score']} – {lead['signal_type']}: {lead['why_now']}")
    if warnings:
        lines.append(":warning: " + " · ".join(warnings))
    if run_url:
        lines.append(f"<{run_url}|Bekijk de run in Salesforce>")
    return "\n".join(lines)


class Notifier:
    """Post naar Slack; zonder token (lokaal, dry-run) wordt alleen gelogd."""

    def __init__(self, token: str | None, channel: str, dry_run: bool = False, client=None):
        self.channel = channel
        self.dry_run = dry_run or not token
        self.client = client
        if not self.dry_run and client is None:
            from slack_sdk import WebClient

            self.client = WebClient(token=token)

    def _send(self, text: str, post_at: datetime | None = None) -> None:
        if self.dry_run:
            log.info("[slack%s] %s", f" @ {post_at:%Y-%m-%d %H:%M}" if post_at else "", text)
            return
        try:
            if post_at:
                self.client.chat_scheduleMessage(channel=self.channel, text=text, post_at=int(post_at.timestamp()))
            else:
                self.client.chat_postMessage(channel=self.channel, text=text)
        except Exception:  # Slack mag een run nooit laten mislukken
            log.exception("Slack-bericht versturen mislukt")

    def weekly(
        self, stats: dict, top: list[dict], run_url: str | None, warnings: list[str], now: datetime, schedule: bool
    ) -> None:
        """Geplande run: inplannen voor maandag 08:00. Handmatige run of te laat: direct posten."""
        text = weekly_text(stats, top, run_url, warnings)
        post_at = monday_0800(now) if schedule else None
        if post_at and post_at - now < timedelta(minutes=2):
            post_at = None  # Slack weigert berichten die (bijna) in het verleden liggen
        self._send(text, post_at)

    def error(self, run_key: str, message: str, run_url: str | None = None) -> None:
        link = f"\n<{run_url}|Bekijk de run in Salesforce>" if run_url else ""
        self._send(f":rotating_light: *Leadscan {run_key}*: {message}{link}")

    def info(self, run_key: str, message: str) -> None:
        self._send(f"*Leadscan {run_key}*: {message}")

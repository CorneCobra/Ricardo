"""Orkestratie van één wekelijkse run. Eén run = één Run_Key__c (ISO-week, bv. 2026-W41).

Volgorde: instellingen → uitsluitlijst/index → budget verdelen → ontdekken →
dubbelcheck laag 1-3 → diep onderzoek → opnieuw dubbelcheck (nu met KvK en
officiële naam) → bronnencontrole → drempel → wegschrijven (laag 4 = duplicate
rule) → segmentcijfers → Slack (weekupdate + runrapport).

Er wordt pas aan het eind iets naar Salesforce geschreven (leads én Tasks), zodat
een fout halverwege geen half weggeschreven run oplevert.

Gebruik:
    python -m runner.main                 # normale run
    python -m runner.main --scheduled     # vanuit de cron: alleen zondag 22:00-23:59
    python -m runner.main --dry-run       # niets naar Salesforce; rapport wel naar Slack
    python -m runner.main --dry-run --dedup-only   # fase 3: alleen ontdekken + dubbelcheck
    python -m runner.main --dry-run --no-slack     # lokaal: rapport alleen in out/

In GitHub Actions (publieke repository) staat LEADSCAN_QUIET_LOGS=1: de logs bevatten
dan alleen aantallen, nooit organisatienamen of match-redenen. Die staan in het
runrapport (Slack) en in Scan_Run__c.Errors__c.
"""

from __future__ import annotations

import argparse
import logging
import os
import random
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import anthropic

from . import allocate, config, discover, exclusion, learning, research, review_doubt, verify_sources
from .claude_agent import AgentError, DeadlineReached
from .icp import ICP_VERSION
from .lead_mapping import lead_record, task_record
from .matching import MatchIndex, MatchResult, RunDeduper
from .report import RunReport
from .salesforce import SalesforceClient
from .slack import Notifier

log = logging.getLogger("leadscan")
detail = logging.getLogger("leadscan.detail")  # namen en redenen; uit in publieke logs

ERRORS_MAX = 32000
REPORT_DIR = Path(os.environ.get("LEADSCAN_REPORT_DIR", "out"))


class KillSwitch(Exception):
    """Kill_Switch__c staat aan."""


@dataclass
class RunStats:
    run_key: str
    candidates_found: int = 0
    blocked: list[int] = field(default_factory=lambda: [0, 0, 0, 0])
    below_threshold: int = 0
    signals_to_existing: int = 0
    leads_created: int = 0
    notes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def fields(self) -> dict:
        return {
            "Candidates_Found__c": self.candidates_found,
            "Blocked_Layer_1__c": self.blocked[0],
            "Blocked_Layer_2__c": self.blocked[1],
            "Blocked_Layer_3__c": self.blocked[2],
            "Blocked_Layer_4__c": self.blocked[3],
            "Below_Threshold__c": self.below_threshold,
            "Signals_To_Existing__c": self.signals_to_existing,
            "Leads_Created__c": self.leads_created,
        }

    def errors_text(self) -> str:
        lines = [f"WAARSCHUWING: {w}" for w in self.warnings] + self.notes
        text = "\n".join(lines)
        return text if len(text) <= ERRORS_MAX else text[: ERRORS_MAX - 20] + "\n…(ingekort)"


def _utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Pipeline:
    def __init__(
        self,
        sf: SalesforceClient,
        claude,
        notifier: Notifier,
        *,
        run_key: str,
        dry_run: bool = False,
        dedup_only: bool = False,
        scheduled: bool = False,
        force: bool = False,
        clock=None,
        verifier=verify_sources.verify,
        rng: random.Random | None = None,
        report_dir: Path | None = REPORT_DIR,
    ):
        self.sf = sf
        self.claude = claude
        self.notifier = notifier
        self.run_key = run_key
        self.dry_run = dry_run
        self.dedup_only = dedup_only
        self.scheduled = scheduled
        self.force = force
        self.clock = clock or (lambda: datetime.now(config.TIMEZONE))
        self.verifier = verifier
        self.rng = rng
        self.report_dir = report_dir
        self.stats = RunStats(run_key)
        self.report = RunReport(run_key, dry_run, config.MODEL, ICP_VERSION)
        self.run_id: str | None = None
        self.pending_tasks: list[tuple[dict, dict]] = []  # (task, kandidaat)

    # ---- hulpfuncties -----------------------------------------------------

    @property
    def run_url(self) -> str | None:
        return f"{self.sf.instance_url}/lightning/r/Scan_Run__c/{self.run_id}/view" if self.run_id else None

    def _note(self, candidate: dict | None, text: str, result: str | None = None) -> None:
        """Eén regel voor Errors__c én het runrapport."""
        name = candidate.get("company_name") if candidate else None
        self.stats.notes.append(f"{name}: {text}" if name else text)
        if candidate:
            self.report.step(candidate, text, result)

    def _warn(self, text: str) -> None:
        self.stats.warnings.append(text)
        self.report.warnings.append(text)

    def _save_run(self, status: str, extra: dict | None = None) -> None:
        if self.dry_run:
            log.info("[dry-run] Scan_Run__c %s -> %s %s", self.run_key, status, self.stats.fields())
            return
        fields = {"Status__c": status, **(extra or {})}
        self.run_id = self.sf.upsert_run(self.run_key, fields)

    def _check_kill_switch(self, settings: config.Settings | None = None) -> config.Settings:
        settings = settings or self.sf.settings()
        if settings.kill_switch:
            raise KillSwitch()
        return settings

    def _handle_match(self, match: MatchResult, candidate: dict, deadline: config.Deadline) -> bool:
        """True als de kandidaat door laag 1-3 komt."""
        if match.outcome == "clear":
            return True
        if match.outcome == "blocked_l1":
            self.stats.blocked[0] += 1
            self._note(candidate, f"L1 tegengehouden: {match.reason}", "laag 1: uitgesloten")
            return False
        if match.outcome == "blocked_l2":
            self.stats.blocked[1] += 1
            self._note(candidate, f"L2 tegengehouden: {match.reason}", "laag 2: bestaand record")
            target = match.task_target()
            task = task_record(target, candidate) if target else None
            if task:
                self.pending_tasks.append((task, candidate))
            elif target:
                self._note(candidate, f"geen Task voor {target.name}: eigenaar is geen gebruiker")
            return False
        allowed, why = review_doubt.review(self.claude, candidate, match, deadline)
        if not allowed:
            self.stats.blocked[2] += 1
            self._note(candidate, f"L3 tegengehouden: {why} | {match.reason}", "laag 3: twijfelgeval")
        else:
            self._note(candidate, f"L3 doorgelaten: {why}")
        return allowed

    # ---- fasen ------------------------------------------------------------

    def _discover(self, settings, segments, deadline) -> list[dict]:
        budget = allocate.allocate(
            segments,
            config.DISCOVERY_SEARCH_BUDGET,
            settings.exploration_share,
            settings.learning_enabled,
            self.rng,
        )
        self.report.segment_budget = {s.name: budget[s.id] for s in segments}
        log.info("Zoekbudget per segment: %s", list(budget.values()))
        candidates: list[dict] = []
        examples = None
        if any(s.signal_type == "Lookalike" and budget[s.id] > 0 for s in segments):
            examples = self.sf.recent_won_customers()
            if not examples:
                self._warn("Lookalike-segment zonder recent gewonnen klanten")
        for seg in segments:
            if budget[seg.id] <= 0:
                continue
            try:
                found, notes = discover.discover(self.claude, seg, budget[seg.id], deadline, examples)
            except DeadlineReached:
                self._warn("Maximale looptijd bereikt tijdens ontdekken")
                break
            for n in notes:
                self._note(None, n)
            for cand in found:
                cand["_report"] = self.report.add(cand, seg.name)
            candidates += found
        self.stats.candidates_found = len(candidates)
        return candidates

    def _dedupe(self, index: MatchIndex, candidates: list[dict], deadline) -> list[dict]:
        deduper = RunDeduper()
        passed = []
        for cand in candidates:
            if deduper.seen(cand["company_name"], cand["domain"]):
                self._note(cand, "dubbel binnen de run, overgeslagen", "dubbel binnen de run")
                continue
            try:
                if self._handle_match(index.check(cand["company_name"], cand["domain"]), cand, deadline):
                    passed.append(cand)
            except DeadlineReached:
                self._warn("Maximale looptijd bereikt tijdens de dubbelcheck")
                break
        return passed

    def _research(self, settings, index, candidates, deadline) -> list[tuple[dict, dict]]:
        qualified: list[tuple[dict, dict]] = []
        deduper = RunDeduper()
        for cand in candidates:
            try:
                outcome = research.research(self.claude, cand, settings.max_searches_per_candidate, deadline)
                if outcome.lead is None:
                    self._note(cand, "onderzoek zonder geldig resultaat: " + "; ".join(outcome.errors),
                               "onderzoek mislukt")
                    continue
                lead = outcome.lead
                self.report.research(cand, lead)
                if deduper.seen(lead["company_name"], lead["domain"]):
                    self._note(cand, "dubbel na onderzoek, overgeslagen", "dubbel binnen de run")
                    continue
                # Opnieuw door laag 1-3, nu met officiële naam, eigen domein en KvK.
                recheck = index.check(lead["company_name"], lead["domain"], lead.get("kvk_number"))
                merged = {**cand, **{k: lead[k] for k in ("company_name", "domain", "kvk_number", "city")}}
                if not self._handle_match(recheck, merged, deadline):
                    continue
            except DeadlineReached:
                self._warn("Maximale looptijd bereikt tijdens onderzoek")
                break

            check = self.verifier(lead, cand, outcome.seen_urls)
            if not check.ok:
                self._note(cand, "bronnen afgekeurd: " + "; ".join(check.problems), "bronnen afgekeurd")
                continue
            if check.unseen_urls:
                self._note(cand, "let op, bron niet in zoekresultaten gezien: " + ", ".join(check.unseen_urls))
            if lead["score"] < settings.minimum_score:
                self.stats.below_threshold += 1
                self._note(cand, f"onder drempel: score {lead['score']} < {settings.minimum_score}", "onder drempel")
                continue
            qualified.append((lead, cand))
        return qualified

    def _write(self, settings, qualified, already_created: int) -> list[dict]:
        slots = max(settings.max_leads_per_run - already_created, 0)
        qualified.sort(key=lambda pair: pair[0]["score"], reverse=True)
        selected, overflow = qualified[:slots], qualified[slots:]
        for lead, cand in overflow:
            self._note(cand, f"gekwalificeerd (score {lead['score']}), maar maximum {settings.max_leads_per_run} "
                             "leads per run bereikt", "boven het maximum per run")

        if self.dry_run:
            for lead, cand in selected:
                self.report.created(cand, None)
                detail.info("[dry-run] Lead: %s score %s", lead["company_name"], lead["score"])
            for task, cand in self.pending_tasks:
                self._note(cand, f"Task zou worden aangemaakt: {task['Subject']}")
            return [{**lead, "signal_type": cand["signal_type"]} for lead, cand in selected]

        queue_id = self.sf.queue_id()
        records = [
            lead_record(
                lead, cand,
                run_key=self.run_key,
                queue_id=queue_id,
                partner_account_id=self.sf.partner_account_id(lead.get("current_sf_partner")),
            )
            for lead, cand in selected
        ]
        created = []
        for res in self.sf.insert_leads(records) if records else []:
            lead, cand = selected[res.index]
            if res.id:
                self.stats.leads_created += 1
                self.report.created(cand, res.id)
                created.append({**lead, "signal_type": cand["signal_type"]})
            elif res.duplicate:
                self.stats.blocked[3] += 1
                self._note(cand, "L4 tegengehouden door de duplicate rule", "laag 4: duplicate rule")
            else:
                self._note(cand, "lead niet aangemaakt: " + "; ".join(res.errors), "fout bij aanmaken")

        for task, cand in self.pending_tasks:
            try:
                self.sf.create_task(task)
                self.stats.signals_to_existing += 1
                self._note(cand, f"Task aangemaakt voor de eigenaar: {task['Subject']}")
            except Exception as exc:  # een mislukte Task mag de run niet laten falen
                self._note(cand, f"Task niet aangemaakt: {exc}")
        return created

    def _publish_report(self, finished: datetime) -> None:
        """Runrapport naar out/ (lokaal) en als bestand naar het private Slack-kanaal."""
        self.report.finished = finished
        self.report.stats = self.stats.fields()
        markdown = self.report.to_markdown()
        if self.report_dir:
            self.report_dir.mkdir(parents=True, exist_ok=True)
            (self.report_dir / f"leadscan-{self.run_key}.md").write_text(markdown, encoding="utf-8")
            (self.report_dir / f"leadscan-{self.run_key}.json").write_text(self.report.to_json(), encoding="utf-8")
        label = "Proefrun" if self.dry_run else "Runrapport"
        self.notifier.upload(
            f"leadscan-{self.run_key}.md",
            markdown,
            f"{label} leadscan {self.run_key}",
            f"{label} {self.run_key}: details per kandidaat (dubbelcheck, onderzoek, bronnen).",
        )

    # ---- run --------------------------------------------------------------

    def run(self) -> int:
        started = self.clock()
        self.report.started = started
        try:
            settings = self.sf.settings()
            try:
                self._check_kill_switch(settings)
            except KillSwitch:
                return self._stopped("uitschakelknop (Kill_Switch__c) staat aan; run niet gestart")

            existing = self.sf.get_run(self.run_key)
            if existing and existing.get("Status__c") == "Completed" and not self.force:
                log.info("Run %s is al voltooid; niets te doen (gebruik --force om opnieuw te draaien)", self.run_key)
                return 0
            # Een hervatte run houdt zijn oorspronkelijke starttijd: daarmee vinden we de
            # leads die deze run al heeft aangemaakt (er is geen lookup naar de run op Lead).
            run_started = (existing or {}).get("Started__c") or _utc(started)
            already_created = 0
            if existing and not self.dry_run:
                already_created = len(self.sf.scan_leads_between(run_started))
            self.stats.leads_created = already_created

            self._save_run("Running", {
                "Started__c": run_started,
                "Finished__c": None,
                "Model_Version__c": config.MODEL,
                "ICP_Version__c": ICP_VERSION,
                **self.stats.fields(),
            })
            deadline = config.Deadline(started=started, minutes=settings.max_runtime_minutes, clock=self.clock)

            index = exclusion.build_index(self.sf)
            segments = self.sf.active_segments()
            if not segments:
                raise RuntimeError("Geen actieve Scan_Segment__c-records")

            candidates = self._discover(settings, segments, deadline)
            passed = self._dedupe(index, candidates, deadline)
            log.info("Kandidaten %d, door laag 1-3: %d", len(candidates), len(passed))

            created: list[dict] = []
            if not self.dedup_only:
                settings = self._check_kill_switch()
                qualified = self._research(settings, index, passed, deadline)
                settings = self._check_kill_switch()
                created = self._write(settings, qualified, already_created)
                if not self.dry_run:
                    try:
                        learning.update_segment_metrics(self.sf)
                    except Exception as exc:
                        self._warn(f"Segmentcijfers niet bijgewerkt: {exc}")
            else:
                for cand in passed:
                    self.report.step(cand, "door laag 1-3 (proefrun dubbelcheck: geen onderzoek)", "door de dubbelcheck")
                if self.dry_run:
                    self._write(settings, [], already_created)  # toont de Tasks die zouden ontstaan

            finished = self.clock()
            self._save_run("Completed", {"Finished__c": _utc(finished), "Errors__c": self.stats.errors_text(),
                                         **self.stats.fields()})
            log.info("Run %s voltooid: %s", self.run_key, self.stats.fields())
            try:
                self._publish_report(finished)
            except Exception:  # het rapport mag een geslaagde run nooit laten mislukken
                log.exception("Runrapport maken mislukt")
            warnings = list(self.stats.warnings)
            if len(created) < 3 and not self.dedup_only:
                warnings.append("weinig leads deze week")
            self.notifier.weekly(
                {"run_key": self.run_key + (" (proefrun)" if self.dry_run else ""), **self.stats.fields()},
                sorted(created, key=lambda lead: lead["score"], reverse=True),
                self.run_url,
                warnings,
                finished,
                schedule=self.scheduled and not self.dry_run,
            )
            return 0
        except KillSwitch:
            return self._stopped("uitschakelknop aangezet tijdens de run; niets weggeschreven")
        except Exception as exc:
            log.exception("Run %s mislukt", self.run_key)
            kind = "Claude API" if isinstance(exc, (AgentError, anthropic.APIError)) else "Run"
            self.stats.notes.insert(0, f"FOUT: {exc}")
            try:
                self._save_run("Failed", {"Finished__c": _utc(self.clock()), "Errors__c": self.stats.errors_text(),
                                          **self.stats.fields()})
            except Exception:
                log.exception("Scan_Run__c kon niet op Failed worden gezet")
            self.notifier.error(self.run_key, f"{kind} mislukt: {exc}. Er zijn geen leads weggeschreven.", self.run_url)
            return 1

    def _stopped(self, message: str) -> int:
        self._warn(message)
        try:
            self._save_run("Stopped", {"Finished__c": _utc(self.clock()), "Errors__c": self.stats.errors_text(),
                                       "Model_Version__c": config.MODEL, "ICP_Version__c": ICP_VERSION})
        except Exception:
            log.exception("Scan_Run__c kon niet op Stopped worden gezet")
        self.notifier.error(self.run_key, f"Gestopt: {message}", self.run_url)
        return 0


def is_scheduled_window(now: datetime) -> bool:
    """De cron draait op twee UTC-tijden (zomer/winter); alleen zondag 22:00-23:59 lokale tijd telt."""
    local = now.astimezone(config.TIMEZONE)
    return local.weekday() == 6 and local.hour in (22, 23)


def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if os.environ.get("LEADSCAN_QUIET_LOGS") == "1":
        detail.setLevel(logging.WARNING)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Wekelijkse leadscan")
    parser.add_argument("--dry-run", action="store_true", help="niets naar Salesforce schrijven")
    parser.add_argument("--no-slack", action="store_true", help="niets naar Slack sturen")
    parser.add_argument("--dedup-only", action="store_true", help="alleen ontdekken en dubbelcheck (fase 3)")
    parser.add_argument("--scheduled", action="store_true", help="aangeroepen door de cron")
    parser.add_argument("--run-key", help="afwijkende Run_Key__c, bv. 2026-W41-test")
    parser.add_argument("--force", action="store_true", help="ook draaien als deze run al voltooid is")
    args = parser.parse_args(argv)

    configure_logging()
    now = datetime.now(config.TIMEZONE)
    if args.scheduled and not is_scheduled_window(now):
        log.info("Buiten het geplande venster (zondag 22:00-23:59 Europe/Amsterdam); niets te doen")
        return 0

    env = config.Env.load()
    key = args.run_key or config.run_key(now)
    notifier = Notifier(env.slack_token, env.slack_channel, dry_run=args.no_slack)
    try:
        sf = SalesforceClient.login(env)
    except Exception as exc:
        log.exception("Inloggen bij Salesforce mislukt")
        notifier.error(key, f"Salesforce onbereikbaar of inloggen mislukt: {exc}. Er is niets weggeschreven.")
        return 1
    claude = anthropic.Anthropic(max_retries=4)
    pipeline = Pipeline(
        sf, claude, notifier,
        run_key=key, dry_run=args.dry_run, dedup_only=args.dedup_only,
        scheduled=args.scheduled, force=args.force,
    )
    return pipeline.run()


if __name__ == "__main__":
    sys.exit(main())

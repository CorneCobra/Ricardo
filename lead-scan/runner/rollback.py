"""Terugdraaien per run: welke leads heeft één run aangemaakt?

Er staat bewust geen lookup naar Scan_Run__c op Lead. De leads van een run zijn
die met LeadSource 'Claude Weekly Scan', aangemaakt door de integratiegebruiker
tussen Started__c en Finished__c van de run.

    python -m runner.rollback --run-key 2026-W41

Schrijft out/rollback-<run>.csv met de Lead-Id's. Verwijderen doet een beheerder
(Data Loader > Delete, of Setup > Mass Delete Records): de integratiegebruiker heeft
bewust geen verwijderrechten.
"""

from __future__ import annotations

import argparse
import csv
import logging
import sys

from . import config
from .main import REPORT_DIR, configure_logging
from .salesforce import SalesforceClient

log = logging.getLogger("leadscan.rollback")


def run_lead_ids(sf: SalesforceClient, run_key: str) -> list[str]:
    run = sf.get_run(run_key)
    if not run or not run.get("Started__c"):
        raise RuntimeError(f"Scan_Run__c {run_key} niet gevonden of zonder starttijd")
    return [lead["Id"] for lead in sf.scan_leads_between(run["Started__c"], run.get("Finished__c"))]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Lead-Id's van één run, om terug te draaien")
    parser.add_argument("--run-key", required=True)
    args = parser.parse_args(argv)
    configure_logging()

    sf = SalesforceClient.login(config.Env.load())
    ids = run_lead_ids(sf, args.run_key)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORT_DIR / f"rollback-{args.run_key}.csv"
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["Id"])
        writer.writerows([i] for i in ids)
    log.info("%d leads van run %s in %s", len(ids), args.run_key, path)
    return 0


if __name__ == "__main__":
    sys.exit(main())

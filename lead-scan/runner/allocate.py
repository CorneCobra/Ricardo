"""Verdeling van het zoekbudget over de segmenten (bandit, ca. 70/30).

- Verkenning (Exploration_Share__c, start 30%): gelijk verdeeld over segmenten
  met Exploration__c; zijn die er niet, dan over alle segmenten.
- Benutting (de rest): naar verhouding van Weight__c. Zodra Learning_Enabled__c
  aan staat, wordt het gewicht vermenigvuldigd met een Thompson-steekproef van
  de conversiekans per segment (gewonnen deals wegen het zwaarst).
"""

from __future__ import annotations

import random

from .config import Segment


def conversion_sample(seg: Segment, rng: random.Random) -> float:
    """Steekproef uit Beta(1 + succes, 1 + mislukt) met gewogen succes."""
    success = seg.leads_qualified + 2 * seg.opportunities_created + 4 * seg.deals_won
    trials = max(seg.leads_created, seg.leads_qualified + seg.leads_unqualified)
    failures = max(trials - seg.leads_qualified, 0)
    return rng.betavariate(1 + success, 1 + failures)


def _largest_remainder(shares: dict[str, float], total: int) -> dict[str, int]:
    if total <= 0 or not shares:
        return {k: 0 for k in shares}
    s = sum(shares.values())
    if s <= 0:
        shares = {k: 1.0 for k in shares}
        s = float(len(shares))
    exact = {k: total * v / s for k, v in shares.items()}
    alloc = {k: int(v) for k, v in exact.items()}
    rest = total - sum(alloc.values())
    for k in sorted(exact, key=lambda k: (exact[k] - alloc[k], k), reverse=True)[:rest]:
        alloc[k] += 1
    return alloc


def allocate(
    segments: list[Segment],
    total_searches: int,
    exploration_share: float,
    learning_enabled: bool,
    rng: random.Random | None = None,
) -> dict[str, int]:
    """Segment-Id -> aantal zoekacties. Som is precies total_searches."""
    if not segments:
        return {}
    rng = rng or random.Random()
    explore_total = round(total_searches * max(0.0, min(exploration_share, 100.0)) / 100)
    exploit_total = total_searches - explore_total

    explorers = [s for s in segments if s.exploration] or segments
    exploiters = [s for s in segments if not s.exploration]
    if not exploiters:
        explore_total, exploit_total = total_searches, 0

    exploit_shares = {}
    for seg in exploiters:
        weight = max(seg.weight, 0.0)
        exploit_shares[seg.id] = weight * conversion_sample(seg, rng) if learning_enabled else weight

    result = {s.id: 0 for s in segments}
    for k, v in _largest_remainder(exploit_shares, exploit_total).items():
        result[k] += v
    for k, v in _largest_remainder({s.id: 1.0 for s in explorers}, explore_total).items():
        result[k] += v
    return result

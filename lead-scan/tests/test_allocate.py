import random

from runner.allocate import allocate
from runner.config import Segment


def seg(id_, weight, exploration=False, **metrics):
    return Segment(id=id_, name=id_, target_industry=None, signal_type=None, search_strategy="",
                   weight=weight, exploration=exploration, **metrics)


def test_cold_start_follows_weights_and_exploration_share():
    segments = [seg("np", 50), seg("edu", 30), seg("mfg", 20), seg("new", 0, exploration=True)]
    alloc = allocate(segments, 60, 30, learning_enabled=False)
    assert sum(alloc.values()) == 60
    assert alloc["new"] == 18  # 30% verkennen
    assert alloc["np"] == 21 and alloc["edu"] == 13 and alloc["mfg"] == 8


def test_without_exploration_segments_everyone_explores():
    segments = [seg("a", 80), seg("b", 20)]
    alloc = allocate(segments, 10, 30, learning_enabled=False)
    assert sum(alloc.values()) == 10
    assert alloc["a"] > alloc["b"] > 0


def test_all_exploration_segments():
    alloc = allocate([seg("a", 0, True), seg("b", 0, True)], 9, 30, learning_enabled=False)
    assert sum(alloc.values()) == 9


def test_learning_favours_converting_segment():
    good = seg("good", 50, leads_created=40, leads_qualified=20, opportunities_created=10, deals_won=5)
    bad = seg("bad", 50, leads_created=40, leads_qualified=1)
    rng = random.Random(42)
    totals = {"good": 0, "bad": 0}
    for _ in range(50):
        for k, v in allocate([good, bad], 20, 0, learning_enabled=True, rng=rng).items():
            totals[k] += v
    assert totals["good"] > 2 * totals["bad"]


def test_empty():
    assert allocate([], 10, 30, False) == {}

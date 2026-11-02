"""One conviction ranking, read by both the live loop and the backtest engine.

Until 2026-11-02 there were three copies of this rule: one in the live order
flow (ranking a strategy removed on 2026-10-30, and giving the two newest legs
no rank), and two in the engine, both naming sixteen V5 strategies that no
longer exist and none of the four legs that trade. They happened to agree for
the current portfolio. Nothing made them agree, and the config fingerprint did
not cover them, so the integrity gate could not have caught a divergence.

These tests are about that: that there is one table, that both sides read it,
and that today's winner is the one the old tables picked.
"""
from types import SimpleNamespace

import pytest

from src.core import conviction
from src.strategies.portfolio_atlas import PORTFOLIO

LIVE_NAMES = [c().name for c in PORTFOLIO]

# The two tables as they stood before this change, so "behaviour is unchanged"
# is checked against them rather than asserted.
OLD_LIVE = {"DONCHIAN_TREND_V6": 7, "ASIAN_RANGE_FILTERED_V6": 6, "ASIAN_BREAKOUT_V6": 6}
OLD_ENGINE = {
    "NVMR_TARGET_10_V5": 6, "NVMR_TARGET_10": 6, "BB_MEAN_REVERSION_V5": 5,
    "BB_MEAN_REVERSION": 5, "FVG_NY_SWEEP_OR_VOID": 5, "FVG_NY_SWEEP": 4,
    "FVG_NY_VOID": 3, "FVG_NY_TIGHT_V5": 2, "FVG_NY_TIGHT": 2,
    "TREND_PULLBACK_V5": 2, "TREND_PULLBACK": 2, "FVG_ASIA_SWEEP": 1,
    "NY_LIQUIDITY_EXPANSION_V5": 1, "NY_LIQUIDITY_EXPANSION": 1,
    "PDHLR_STRATEGY_V5": 1, "PDHLR_STRATEGY": 1,
}


def leg(name):
    return (SimpleNamespace(name=name), SimpleNamespace(strategy_name=name))


def winner_under(table, names):
    """Who the given table would pick, with the portfolio's stable tie-break."""
    return sorted(names, key=lambda n: table.get(n.upper(), 0), reverse=True)[0]


# ---------------------------------------------------------------------------
# the ranking itself
# ---------------------------------------------------------------------------


def test_every_live_leg_is_ranked():
    assert conviction.unranked_in([c() for c in PORTFOLIO]) == []


def test_the_order_is_the_one_the_evidence_gives():
    r = conviction.rank
    assert (r("ASIAN_RANGE_FILTERED_V6") > r("ASIAN_BREAKOUT_V6")
            > r("LONDON_MOMENTUM_TIGHT_V6") > r("NY_SESSION_REVERSAL_V6"))


def test_an_unknown_strategy_is_unranked_rather_than_crashing():
    assert conviction.rank("SOMETHING_NEW") == conviction.UNRANKED
    assert conviction.rank("") == conviction.UNRANKED
    assert conviction.rank(None) == conviction.UNRANKED


def test_a_retired_leg_keeps_the_rank_it_had_when_it_was_live():
    # so re-running an old backtest that still includes it behaves as it did
    assert conviction.rank("DONCHIAN_TREND_V6") > conviction.rank("ASIAN_RANGE_FILTERED_V6")


def test_ranks_leave_room_to_slot_a_new_leg_between_two_existing_ones():
    ranks = sorted(conviction.RANK.values())
    assert all(b - a > 1 for a, b in zip(ranks, ranks[1:]))


# ---------------------------------------------------------------------------
# picking
# ---------------------------------------------------------------------------


def test_pick_returns_the_highest_rank_and_the_losers():
    best, losers = conviction.pick([leg("NY_SESSION_REVERSAL_V6"),
                                    leg("ASIAN_RANGE_FILTERED_V6"),
                                    leg("LONDON_MOMENTUM_TIGHT_V6")])
    assert best[0].name == "ASIAN_RANGE_FILTERED_V6"
    assert [s.name for s, _ in losers] == ["LONDON_MOMENTUM_TIGHT_V6", "NY_SESSION_REVERSAL_V6"]


def test_pick_keeps_portfolio_order_between_equal_ranks():
    # a stable sort is what reproduced the old tables' behaviour for the legs
    # neither of them ranked, so it must stay stable
    best, losers = conviction.pick([leg("NEW_A"), leg("NEW_B")])
    assert best[0].name == "NEW_A"
    assert [s.name for s, _ in losers] == ["NEW_B"]


def test_pick_on_a_single_signal_has_no_losers():
    best, losers = conviction.pick([leg("ASIAN_BREAKOUT_V6")])
    assert best[0].name == "ASIAN_BREAKOUT_V6"
    assert losers == []


def test_pick_refuses_an_empty_list_rather_than_returning_nothing():
    with pytest.raises(ValueError):
        conviction.pick([])


# ---------------------------------------------------------------------------
# behaviour is unchanged
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("pair", [
    ("ASIAN_RANGE_FILTERED_V6", "ASIAN_BREAKOUT_V6"),        # the 07:00 UTC candle
    ("LONDON_MOMENTUM_TIGHT_V6", "NY_SESSION_REVERSAL_V6"),  # the 12:00 UTC candle
])
def test_the_two_reachable_collisions_pick_what_they_always_picked(pair):
    """Each leg fires in its own slot, so only these two pairs can collide
    (measured over 338 fills in DEV, TEST and RECENT)."""
    now = conviction.pick([leg(pair[0]), leg(pair[1])])[0][0].name
    assert now == winner_under(OLD_LIVE, list(pair))
    assert now == winner_under(OLD_ENGINE, list(pair))


def test_no_combination_of_live_legs_changes_winner():
    import itertools

    for r in range(2, len(LIVE_NAMES) + 1):
        for combo in itertools.combinations(LIVE_NAMES, r):
            now = conviction.pick([leg(n) for n in combo])[0][0].name
            assert now == winner_under(OLD_LIVE, list(combo)), combo
            assert now == winner_under(OLD_ENGINE, list(combo)), combo


# ---------------------------------------------------------------------------
# both sides really do read it
# ---------------------------------------------------------------------------


def test_neither_the_live_loop_nor_the_engine_keeps_its_own_copy():
    import inspect

    from src.backtesting import engine
    from src.core import order_flow

    for mod in (order_flow, engine):
        src = inspect.getsource(mod)
        assert "rank_order" not in src, f"{mod.__name__} has its own ranking table again"
        assert "_RANK_ORDER" not in src, f"{mod.__name__} has its own ranking table again"
        assert "conviction" in src, f"{mod.__name__} no longer reads the shared ranking"


def test_the_ranking_is_in_the_config_fingerprint():
    """The gate has to be able to see a change here. It could not before."""
    from src.core.system_config import SystemConfig

    cfg = SystemConfig.from_live()
    ranks = {s.name: s.conviction for s in cfg.strategies}
    assert ranks == {n: conviction.rank(n) for n in LIVE_NAMES}

    before = cfg.fingerprint()
    moved = tuple(
        type(s)(**{**{f: getattr(s, f) for f in s.__dataclass_fields__},
                   "conviction": s.conviction + 1})
        for s in cfg.strategies
    )
    after = type(cfg)(**{**{f: getattr(cfg, f) for f in cfg.__dataclass_fields__},
                         "strategies": moved}).fingerprint()
    assert before != after, "changing a conviction rank must change the fingerprint"


def test_a_ledger_entry_recorded_before_this_field_existed_still_loads():
    from src.core.system_config import SystemConfig

    d = SystemConfig.from_live().to_dict()
    for s in d["strategies"]:
        s.pop("conviction")
    assert all(s.conviction == 0 for s in SystemConfig.from_dict(d).strategies)

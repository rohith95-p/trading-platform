"""Which leg wins when two fire on the same candle (the "Highlander" rule).

Only one order goes out per scan. Until 2026-11-02 the ranking that decided
which one existed twice, in two different versions: the live table ranked
`DONCHIAN_TREND_V6`, removed from the portfolio on 2026-10-30, and gave the two
newest legs no rank at all, while the backtest engine's table named sixteen V5
strategies that no longer exist and none of the four that do. Both happened to
pick the same winner for the current portfolio -- that was luck, not design, and
`SystemConfig` did not fingerprint either of them, so the integrity gate could
not have caught a divergence. Adding or renaming a leg would have made live and
backtest disagree quietly.

There is now one table, read by `src/core/order_flow.py` and
`src/backtesting/engine.py` through `pick()`.

Only two collisions are reachable, because each leg only fires in its own slot
(measured over DEV, TEST and RECENT -- 338 fills):

    07:00 UTC candle   Asian Range Filtered  vs  Asian Breakout
    12:00 UTC candle   London Momentum       vs  NY Session Reversal

The ranks below keep exactly the winner both old tables picked, and the order
they imply is also the order the evidence gives
(`research/results/audit_stats.json`):

    Asian Range Filtered  136 fills, PF 1.87 TEST / 1.72 RECENT
    Asian Breakout         20 fills, PF 0.93 TEST / profitable on 1 trade RECENT
    London Momentum       182 fills, PF 1.29 TEST / 2.15 RECENT
    NY Session Reversal    far more fills, PF 1.24 TEST / 1.47 RECENT

Changing a rank changes what trades. It is a live trading decision: pre-register
it, test it, and record it in research/DECISIONS.md.
"""
from __future__ import annotations

from typing import Any, List, Sequence, Tuple

# Higher wins. Gaps are deliberate, so a new leg can be slotted between two
# existing ones without renumbering the others.
RANK = {
    "ASIAN_RANGE_FILTERED_V6": 40,
    "ASIAN_BREAKOUT_V6": 30,
    "LONDON_MOMENTUM_TIGHT_V6": 20,
    "NY_SESSION_REVERSAL_V6": 10,
}

# Retired legs, kept so an old backtest or an archived strategy still ranks the
# way it did when it was live rather than silently dropping to unranked.
RETIRED_RANK = {
    "DONCHIAN_TREND_V6": 70,
}

UNRANKED = 0


def rank(name: str) -> int:
    """This strategy's conviction rank. 0 for anything not listed.

    An unranked leg loses every collision it is in, and keeps its position
    relative to other unranked legs, because `pick()` sorts stably.
    """
    key = (name or "").upper()
    return RANK.get(key, RETIRED_RANK.get(key, UNRANKED))


def pick(actionable: Sequence[Tuple[Any, Any]]) -> Tuple[Tuple[Any, Any], List[Tuple[Any, Any]]]:
    """Split (strategy, signal) pairs into the one that trades and the losers.

    The sort is stable, so legs of equal rank keep the order the portfolio lists
    them in -- which is what both old tables did for the unranked legs, and is
    why this change leaves today's behaviour untouched.
    """
    if not actionable:
        raise ValueError("pick() needs at least one actionable signal")
    ordered = sorted(actionable, key=lambda pair: rank(getattr(pair[0], "name", "")), reverse=True)
    return ordered[0], list(ordered[1:])


def unranked_in(strategies: Sequence[Any]) -> List[str]:
    """Names in this portfolio that nothing ranks -- they lose every collision."""
    return [n for n in (getattr(s, "name", "") for s in strategies) if rank(n) == UNRANKED]

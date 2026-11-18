"""Every robustness metric in this repo, run on the real trade records.

Owner's list, 2026-11-09: Monte Carlo, deflated Sharpe (Bailey & Lopez de Prado),
Sortino, Omega, Calmar, recovery factor, ablation. All were already implemented
here; none had ever been run on the out-of-sample record.

Two records are measured side by side:
  IN-SAMPLE   2024-06..2026-01  -- the window that produced the famous PF 1.41
  OUT-OF-SAMPLE 2004-07..2022-08 -- 2,556 trades that never chose these legs

The deflated Sharpe is the one with teeth: it asks whether an observed Sharpe
survives the number of configurations that were tried to find it. Applied to the
1.41, it is a direct test of the selection explanation.

    python -I scripts/validation/full_metric_suite.py
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np
from scipy import stats as sps

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

OUT = os.path.join("research", "registry", "full_metric_suite_2026-11-09.json")


def utc(*a):
    return int(dt.datetime(*a, tzinfo=dt.timezone.utc).timestamp())


RECORDS = {
    "IN-SAMPLE 2024-06..2026-01": [("t", utc(2024, 6, 1), utc(2026, 1, 1))],
    "OUT-OF-SAMPLE 2004..2022": [
        ("e1", utc(2004, 7, 1), utc(2008, 1, 1)),
        ("e2", utc(2008, 1, 1), utc(2012, 1, 1)),
        ("e3", utc(2012, 1, 1), utc(2016, 1, 1)),
        ("e4", utc(2016, 1, 1), utc(2020, 1, 1)),
        ("e5", utc(2020, 1, 1), utc(2022, 8, 1))],
}

START_BALANCE = 5000.0


def job(tag, a, b):
    from src.backtesting.costs import SCENARIOS
    from src.backtesting.engine import BacktestEngine, EngineConfig
    from src.backtesting.master import load_master
    from src.strategies.portfolio_atlas import PORTFOLIO

    bars = load_master(("M15", "M1", "D1"), start=a, end=b)
    cfg = EngineConfig.live_parity_preset(
        sizing_mode="fixed", fixed_lots=0.02, starting_balance=START_BALANCE,
        max_concurrent=3, max_same_direction=3, history_bars=7500,
        protect_profit=False, m1_policy="skip")
    eng = BacktestEngine(bars=bars, cost=SCENARIOS["realistic_ecn"], config=cfg)
    res = eng.run([c() for c in PORTFOLIO], a, b)
    return tag, [(int(t.entry_time), float(t.net_pl), float(t.r_multiple))
                 for t in res.trades]


class T:
    """Minimal stand-in so the repo's own metric helpers can be reused."""

    __slots__ = ("net_pl", "r_multiple")

    def __init__(self, net_pl, r_multiple):
        self.net_pl = net_pl
        self.r_multiple = r_multiple


def ratios(pls, years):
    a = np.asarray(pls, dtype=float)
    wins, losses = a[a > 0], a[a < 0]
    gl = float(-losses.sum())
    eq = START_BALANCE + np.cumsum(a)
    eq = np.concatenate([[START_BALANCE], eq])
    peak = np.maximum.accumulate(eq)
    dd_abs = float(np.max(peak - eq))
    dd_pct = float(np.max((peak - eq) / peak) * 100.0)

    downside_std = float(np.sqrt(np.mean(np.minimum(a, 0.0) ** 2))) if len(a) else 0.0
    nonpositive = np.flatnonzero(eq <= 0)
    ann_ret_pct = ((eq[-1] / START_BALANCE) ** (1.0 / years) - 1.0) * 100.0 if years > 0 and not len(nonpositive) else None

    # Omega at threshold 0: sum of gains / sum of losses above/below 0
    out = dict(
        trades=int(len(a)),
        net=round(float(a.sum()), 2),
        profit_factor=round(float(wins.sum() / gl), 3) if gl > 0 else None,
        win_pct=round(100 * float((a > 0).mean()), 1) if len(a) else None,
        expectancy=round(float(a.mean()), 4) if len(a) else None,
        max_dd_usd=round(dd_abs, 2),
        max_dd_pct=round(dd_pct, 2),
        recovery_factor=round(float(a.sum() / dd_abs), 3) if dd_abs > 0 else None,
        closed_balance_nonpositive=bool(len(nonpositive)),
        first_nonpositive_after_trade=int(nonpositive[0]) if len(nonpositive) else None,
        annualised_return_pct=round(ann_ret_pct, 2) if ann_ret_pct is not None else None,
        calmar_ratio=round(ann_ret_pct / dd_pct, 3) if dd_pct > 0 and ann_ret_pct is not None else None,
        omega_ratio=round(float(wins.sum() / gl), 3) if gl > 0 else None,
        sortino_ratio=round(float(a.mean() / downside_std), 4) if downside_std > 0 else None,
        sharpe_per_trade=round(float(a.mean() / a.std()), 4) if len(a)>1 and a.std() > 0 else None,
        skew=round(float(sps.skew(a)), 3) if len(a)>2 and a.std()>0 else None,
        kurtosis=round(float(sps.kurtosis(a, fisher=False)), 3) if len(a)>3 and a.std()>0 else None,
    )
    return out


def in_sample_sr_variance():
    """Variance of in-sample per-trade Sharpes across the 21 search candidates.

    The DSR docstring in src/research/metrics.py warns that leaving sr_variance
    at 1.0 severely underestimates DSR for per-trade returns. The honest input is
    the spread of Sharpes actually observed across configurations that were tried.
    These 21 came from the 2026-11-07 search; using them as a proxy for the
    original 48-strategy screen is an approximation, and is labelled as one.
    """
    p = os.path.join("research", "registry", "entry_search_select_2026-11-07.json")
    if not os.path.exists(p):
        return None, 0
    real = json.load(open(p))["real"]
    srs = []
    for v in real.values():
        w, l, pw = v["avg_win"], v["avg_loss"], v["win"] / 100.0
        if v["n"] < 20 or w <= 0 or l >= 0:
            continue
        mean = pw * w + (1 - pw) * l
        var = pw * w * w + (1 - pw) * l * l - mean * mean
        if var > 0:
            srs.append(mean / np.sqrt(var))
    return (float(np.var(srs, ddof=1)) if len(srs) > 2 else None), len(srs)


def main():
    from src.backtesting.metrics import drop_best_worst, monte_carlo_paths
    from src.research.metrics import deflated_sharpe_ratio, expected_max_sr

    specs = [(tag + "|" + w[0], w[1], w[2])
             for tag, ws in RECORDS.items() for w in ws]
    got = {}
    with ProcessPoolExecutor(3) as ex:
        for key, rows in ex.map(job, *zip(*specs)):
            got[key] = rows
            print("  done %-34s %5d trades" % (key, len(rows)), flush=True)

    sr_var, n_sr = in_sample_sr_variance()
    print("\nsr_variance from %d in-sample candidate Sharpes: %s"
          % (n_sr, "n/a" if sr_var is None else "%.5f" % sr_var))

    report = {"sr_variance": sr_var, "n_candidates_for_sr_variance": n_sr}

    for tag, ws in RECORDS.items():
        rows = []
        for w in ws:
            rows += got[tag + "|" + w[0]]
        rows.sort(key=lambda r: r[0])
        pls = [r[1] for r in rows]
        years = sum((w[2] - w[1]) for w in ws) / (365.25 * 86400)
        trades = [T(r[1], r[2]) for r in rows]

        print("\n" + "=" * 78)
        print("%s   (%d trades, %.1f years)" % (tag, len(pls), years))
        print("=" * 78)

        r = ratios(pls, years)
        for k in ("trades", "net", "profit_factor", "win_pct", "expectancy",
                  "max_dd_usd", "max_dd_pct", "recovery_factor",
                  "annualised_return_pct", "calmar_ratio", "omega_ratio",
                  "sortino_ratio", "sharpe_per_trade", "skew", "kurtosis"):
            print("  %-24s %s" % (k, r[k]))

        mc = monte_carlo_paths(trades, START_BALANCE)
        print("  -- Monte Carlo (5,000 reshuffles of trade order) --")
        for k in sorted(mc):
            print("  %-24s %s" % (k, mc[k]))

        ab = drop_best_worst(trades)
        print("  -- ablation: how much rides on a few trades --")
        for k in sorted(ab):
            print("  %-24s %s" % (k, ab[k]))

        print("  -- deflated Sharpe ratio (Bailey & Lopez de Prado 2014) --")
        dsr = {}
        arr = np.asarray(pls, dtype=float)
        for trials in (1, 21, 48, 140):
            for sv, svl in ((sr_var, "measured"), (1.0, "legacy 1.0")):
                if sv is None:
                    continue
                d = deflated_sharpe_ratio(arr, num_trials=trials, sr_variance=sv)
                e = expected_max_sr(trials, sv)
                dsr["%d_%s" % (trials, svl)] = dict(dsr=round(d, 4),
                                                    expected_max_sr=round(e, 4))
                print("  trials=%-4d sr_var=%-11s  expected max SR %7.4f   DSR %.4f"
                      % (trials, svl, e, d))

        report[tag] = dict(ratios=r, monte_carlo=mc, ablation=ab, dsr=dsr,
                           years=round(years, 2))

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(report, open(OUT, "w"), indent=1, default=str)
    print("\nwritten to %s" % OUT)
    return 0


if __name__ == "__main__":
    os.environ["ULTRA_TRADE_24H"] = "1"
    sys.path.insert(0, ROOT)
    os.chdir(ROOT)
    raise SystemExit(main())

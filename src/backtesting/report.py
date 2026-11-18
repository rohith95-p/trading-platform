"""One call that emits every robustness statistic this repo can compute.

Owner's request, 2026-11-09: the Calmar / Omega / Sortino / recovery-factor /
Monte-Carlo / deflated-Sharpe family must be part of EVERY backtest result, not a
separate script somebody remembers to run.

Before this module, `metrics.summarize` was called by seven research scripts and
`research.metrics.deflated_sharpe_ratio` by **nothing at all** -- it was not even
importable, because scipy was missing from the venv until 2026-11-09.

The deflated Sharpe is the reason this module exists. Bailey & Lopez de Prado
(2014), "The Deflated Sharpe Ratio", Eq.2, needs five things beyond the Sharpe
itself: skewness, kurtosis, sample length, the variance of the Sharpes across
the configurations tried, and the number of INDEPENDENT trials. The last two are
the ones nobody can supply from memory, so `full_report` takes the per-variant
return series and derives both -- including the correlation-aware effective trial
count via `metrics.k_eff_correction`.
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, Optional, Sequence

import numpy as np

from src.backtesting.metrics import (
    bootstrap_ci_metrics,
    drop_best_worst,
    k_eff_correction,
    monte_carlo_paths,
    summarize,
)


def _skew(a: np.ndarray) -> float:
    m, s = a.mean(), a.std()
    return float(((a - m) ** 3).mean() / s ** 3) if s > 0 else 0.0


def _kurtosis(a: np.ndarray) -> float:
    """Pearson (non-excess) kurtosis, which is what the DSR formula expects."""
    m, s = a.mean(), a.std()
    return float(((a - m) ** 4).mean() / s ** 4) if s > 0 else 0.0


def sharpe_variance_across(
        variant_series: Optional[Sequence[Sequence[float]]]) -> Optional[float]:
    """V[{SR_n}] -- the spread of per-trade Sharpes across the trials.

    Eq.2 needs this measured, not assumed. The DSR function's own docstring warns
    that leaving it at 1.0 makes the penalty far too harsh for per-trade returns.
    """
    srs = []
    for s in variant_series or ():
        a = np.asarray(list(s), dtype=float)
        if len(a) < 20:
            continue
        sd = float(a.std())
        if sd > 0:
            srs.append(float(a.mean()) / sd)
    if len(srs) < 3:
        return None
    return float(np.var(srs, ddof=1))


def full_report(trades: Sequence[Any], equity: Sequence[Any],
                start_balance: float, num_trials: int = 1,
                sr_variance: Optional[float] = None,
                variant_series: Optional[Sequence[Sequence[float]]] = None,
                years: Optional[float] = None, *, start_ts=None, end_ts=None) -> Dict[str, Any]:
    """Every metric, one call. Safe to attach to any backtest result.

    Args:
        trades, equity, start_balance: as `metrics.summarize` takes them.
        num_trials: how many configurations were tried to arrive at THIS one.
            A value of 1 claims it is the only thing ever tested, which is almost
            always false and is flagged in the output when passed.
        sr_variance: V[{SR_n}]. Derived from `variant_series` when omitted.
        variant_series: per-trade P&L of every configuration tried, one series
            each. Supplying it is what makes the DSR honest: it yields both the
            measured sr_variance and the correlation-aware effective trial count.
        years: explicit calendar span, never inferred from holding duration.
            Prefer exact start_ts/end_ts; otherwise available equity/trade
            timestamp bounds are disclosed as inferred.

    Every sub-report is individually guarded, so a metric that cannot be computed
    records its reason instead of breaking the backtest that asked for it.
    """
    out: Dict[str, Any] = {}
    pls = [float(t.net_pl) for t in trades]
    if not np.isfinite(pls).all():
        raise ValueError("Report requires finite per-trade net P&L")

    try:
        out["stats"] = asdict(summarize(trades, equity, start_balance,
                                       start_ts=start_ts, end_ts=end_ts, years=years))
    except Exception as exc:
        out["stats"] = {"error": "%s: %s" % (type(exc).__name__, exc)}

    out["years"] = out["stats"].get("years")
    out["metric_definitions"] = {
        "profit_factor": "positive_net_trade_PnL / abs(negative_net_trade_PnL), unrounded inputs",
        "sortino_ratio": "unannualized mean_net_trade_PnL / zero_target_downside_RMS_all_trades",
        "sharpe_per_trade": "unannualized mean_net_trade_PnL / population_std_net_trade_PnL",
        "calmar_ratio": "calendar_CAGR_pct / max_closed_balance_drawdown_pct; no holding_time_extrapolation",
        "drawdown": "closed_balance_observations_not_floating_equity",
        "monte_carlo": "fixed_trade_order_permutations; terminal_PnL_invariant; prob_50pct_drawdown_tests_half_initial_balance_not_peak_DD",
        "nonfinite_ratios": "JSON null with status; no observed losses/downside is not estimated zero risk",
    }

    try:
        a = np.asarray(pls, dtype=float)
        summary = out["stats"]
        out["ratios"] = {
            "omega_ratio": summary["omega_ratio"],
            "profit_factor_status": summary["profit_factor_status"],
            "sortino_ratio": summary["sortino_ratio"],
            "sortino_status": summary["sortino_status"],
            "sharpe_per_trade": (round(float(a.mean() / a.std()), 4)
                                 if len(a) > 1 and a.std() > 0 else None),
            "annualised_return_pct": summary["annualised_return_pct"],
            "calmar_ratio": summary["calmar_ratio"],
            "recovery_factor": summary["recovery_factor"],
            "skew": round(_skew(a), 4) if len(a) > 2 and a.std() > 0 else None,
            "kurtosis": round(_kurtosis(a), 4) if len(a) > 3 and a.std() > 0 else None,
        }
    except Exception as exc:
        out["ratios"] = {"error": "%s: %s" % (type(exc).__name__, exc)}

    for key, fn in (("monte_carlo", lambda: monte_carlo_paths(trades, start_balance)),
                    ("ablation", lambda: drop_best_worst(trades)),
                    ("bootstrap", lambda: bootstrap_ci_metrics(trades))):
        try:
            out[key] = fn()
        except Exception as exc:
            out[key] = {"error": "%s: %s" % (type(exc).__name__, exc)}

    # -- the multiple-testing correction, which is the point of all this ------
    if sr_variance is None and variant_series:
        sr_variance = sharpe_variance_across(variant_series)
    out["sr_variance"] = sr_variance

    # K_eff is the entropy of a correlation matrix built from the series you
    # supply, so it can NEVER exceed len(variant_series). Passing 3 series while
    # claiming num_trials=48 therefore yields k_eff <= 3, a 94% "reduction" that
    # is pure artefact -- and because a smaller N means a smaller SR_0, it
    # inflates the DSR. That is a flattering bias, which is the direction that
    # gets people funded on nothing. Found by smoke-testing this module on
    # 2026-11-09: 3 leg series + num_trials=48 reported k_eff 2.9 and turned a
    # DSR of 0.034 into 0.794.
    k_eff = None
    if variant_series and num_trials >= 2:
        try:
            n_series = len(variant_series)
            if n_series < num_trials:
                out["k_eff"] = {
                    "k_raw": num_trials,
                    "k_eff": None,
                    "refused": True,
                    "note": ("need one return series per trial to estimate "
                             "effective independence: got %d series for %d "
                             "claimed trials. K_eff <= %d by construction, which "
                             "would understate N and inflate the DSR."
                             % (n_series, num_trials, n_series)),
                }
            else:
                out["k_eff"] = k_eff_correction(variant_series, num_trials)
                k_eff = out["k_eff"].get("k_eff")
        except Exception as exc:
            out["k_eff"] = {"error": "%s: %s" % (type(exc).__name__, exc)}

    out["deflated_sharpe"] = {}
    try:
        from src.research.metrics import deflated_sharpe_ratio, expected_max_sr
        arr = np.asarray(pls, dtype=float)
        v = sr_variance if sr_variance is not None else 1.0
        pairs = [("raw_trials", num_trials)]
        if k_eff:
            pairs.append(("effective_trials", int(round(k_eff))))
        for label, n in pairs:
            if not n or n < 1:
                continue
            out["deflated_sharpe"][label] = {
                "num_trials": int(n),
                "expected_max_sr": round(float(expected_max_sr(int(n), v)), 5),
                "dsr": round(float(deflated_sharpe_ratio(arr, int(n), v)), 5),
            }
        if sr_variance is None:
            out["deflated_sharpe"]["warning"] = (
                "sr_variance defaulted to 1.0; pass variant_series for the "
                "measured value, or this DSR is far harsher than it should be")
        if num_trials <= 1:
            out["deflated_sharpe"]["warning_trials"] = (
                "num_trials=1 claims this is the only configuration ever tried. "
                "If that is not literally true, this DSR means nothing.")
    except Exception as exc:
        out["deflated_sharpe"] = {"error": "%s: %s" % (type(exc).__name__, exc)}

    return out


def format_report(rep: Dict[str, Any]) -> str:
    """Printable block, so any script can emit the whole suite in one call."""
    lines = []
    st = rep.get("stats", {}) or {}
    rt = rep.get("ratios", {}) or {}

    def row(k, v):
        lines.append("  %-28s %s" % (k, "n/a" if v is None else v))

    lines.append("-- performance --")
    for k in ("trades", "net_pl", "profit_factor", "win_rate", "expectancy",
              "payoff_ratio", "breakeven_win_rate", "win_rate_margin",
              "max_drawdown", "max_drawdown_pct", "max_drawdown_duration_days"):
        if k in st:
            row(k, st[k])

    lines.append("-- risk-adjusted --")
    row("drawdown_basis", st.get("drawdown_basis"))
    row("sortino_basis", st.get("sortino_basis"))
    for k in ("sortino_ratio", "omega_ratio", "calmar_ratio", "recovery_factor",
              "sharpe_per_trade", "annualised_return_pct", "skew", "kurtosis"):
        row(k, rt.get(k))

    mc = rep.get("monte_carlo") or {}
    if mc and "error" not in mc:
        lines.append("-- monte carlo (reshuffled trade order) --")
        for k in sorted(mc):
            row(k, mc[k])

    ab = rep.get("ablation") or {}
    if ab and "error" not in ab:
        lines.append("-- ablation (how much rides on a few trades) --")
        for k in sorted(ab):
            row(k, ab[k])

    ke = rep.get("k_eff") or {}
    if ke and "error" not in ke:
        lines.append("-- effective independent trials --")
        for k in ("k_raw", "k_eff", "reduction_pct", "bonferroni_keff"):
            row(k, ke.get(k))

    ds = rep.get("deflated_sharpe") or {}
    if ds:
        lines.append("-- deflated sharpe (Bailey & Lopez de Prado 2014) --")
        for label in ("raw_trials", "effective_trials"):
            d = ds.get(label)
            if d:
                lines.append("  %-28s N=%-5d SR0=%.4f  DSR=%.5f"
                             % (label, d["num_trials"], d["expected_max_sr"],
                                d["dsr"]))
        for w in ("warning", "warning_trials", "error"):
            if ds.get(w):
                lines.append("  ! " + str(ds[w]))
    return "\n".join(lines)

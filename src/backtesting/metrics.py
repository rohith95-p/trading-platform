"""Trade statistics.

The previous engine reported win rate, net profit and max drawdown -- all three
computed from a fixed +/-$5 payoff, which made them functions of the win count
alone. These metrics are computed from realised exit prices, and include the
excursion and duration measures needed to tell a strategy with an edge apart
from one whose exits happen to be lucky.

Added 2026-09-28 (rohith research note):
  - calmar_ratio: annualised return / max drawdown.  No normality assumption.
  - omega_ratio:  integral of P(R>r) / P(R<r) above a threshold (default 0).
    Captures the full return distribution without assuming Gaussian tails.
  - sortino_ratio: mean return / downside deviation.  Penalises only losing
    volatility, unlike Sharpe which penalises upside volatility equally.
  - k_eff_correction(): standalone function.  Computes the Vertox/eigenspectrum
    effective number of tested strategies (K_eff) from the correlation matrix
    of variant return series.  Use this instead of the raw strategy count when
    applying a Bonferroni / Deflated-Sharpe multiple-testing penalty -- DePrado
    assumes independence between trials, which massively overstates the penalty
    when parameter variants are correlated.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

IST = timezone(timedelta(hours=5, minutes=30))


@dataclass
class TradeStats:
    trades: int = 0
    wins: int = 0
    losses: int = 0
    scratches: int = 0
    win_rate: float = 0.0

    gross_profit: float = 0.0
    gross_loss: float = 0.0
    net_pl: float = 0.0
    profit_factor: Optional[float] = None
    expectancy: float = 0.0

    avg_win: float = 0.0
    avg_loss: float = 0.0
    median_win: float = 0.0
    median_loss: float = 0.0
    payoff_ratio: Optional[float] = None
    breakeven_win_rate: Optional[float] = None
    win_rate_margin: Optional[float] = None

    total_r: float = 0.0
    expectancy_r: float = 0.0
    avg_win_r: float = 0.0
    avg_loss_r: float = 0.0

    max_drawdown: float = 0.0
    max_drawdown_pct: float = 0.0
    max_drawdown_duration_days: float = 0.0
    recovery_factor: Optional[float] = None

    max_consec_wins: int = 0
    max_consec_losses: int = 0

    avg_mae_r: float = 0.0
    avg_mfe_r: float = 0.0
    mfe_capture: float = 0.0

    avg_minutes_open: float = 0.0
    median_minutes_open: float = 0.0
    avg_minutes_to_mfe: float = 0.0

    duplicate_trades: int = 0
    duplicate_pl: float = 0.0
    pyramid_trades: int = 0
    pyramid_pl: float = 0.0
    ambiguous_trades: int = 0

    exit_reasons: Dict[str, int] = field(default_factory=dict)
    by_session: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    by_month: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    by_strategy: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    start_balance: float = 0.0
    end_balance: float = 0.0
    return_pct: float = 0.0

    # --- Distribution-agnostic risk-adjusted return metrics ---
    # These are descriptive estimators, not assurances of stable tail risk.
    calmar_ratio: Optional[float] = None
    omega_ratio: Optional[float] = None
    sortino_ratio: Optional[float] = None
    annualised_return_pct: Optional[float] = None
    years: Optional[float] = None
    annualization_basis: str = "calendar_cagr_closed_balance"
    drawdown_basis: str = "closed_balance_observations_not_floating_equity"
    sortino_basis: str = "unannualized_per_trade_net_pnl_zero_target_downside_rms_all_trades"
    profit_factor_status: str = "undefined_no_trades"
    sortino_status: str = "undefined_no_trades"
    closed_balance_nonpositive: bool = False
    metric_notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _safe_div(a: float, b: float, default: float = 0.0) -> float:
    return a / b if b else default


def pnl_ratios(pls) -> Dict[str, Any]:
    """Unrounded zero-target ratios, null when no finite estimate is defined."""
    a = np.asarray(pls, dtype=float)
    if not np.isfinite(a).all():
        raise ValueError("Trade P&L must be finite")
    gains, losses = float(np.maximum(a, 0.).sum()), float(np.maximum(-a, 0.).sum())
    downside = float(np.sqrt(np.mean(np.minimum(a, 0.)**2))) if len(a) else 0.
    return {"profit_factor": gains/losses if losses > 0 else None,
            "profit_factor_status": ("finite" if losses > 0 else
                                     "unbounded_no_observed_losses" if gains > 0 else
                                     "undefined_no_gains_or_losses"),
            "sortino_ratio": float(a.mean())/downside if downside > 0 else None,
            "sortino_status": ("finite" if downside > 0 else
                               "unbounded_no_observed_downside" if gains > 0 else
                               "undefined_no_downside_or_mean"),
            "gross_profit_unrounded": gains, "gross_loss_unrounded": losses}


def closed_balance_metrics(trades, equity, start_balance, *, start_ts=None, end_ts=None, years=None):
    """Calendar return and observed balance drawdowns; no continuous-equity claim.

    Explicit boundaries are preferred. Otherwise use the full supplied timeline
    including idle endpoints, or trade timestamps when no timeline is supplied.
    Cashflows/inconsistent ending balances invalidate CAGR rather than masquerade
    as investment returns. Input observations remain in their original order.
    """
    if not math.isfinite(start_balance) or start_balance <= 0:
        raise ValueError("Positive finite starting balance required")
    pls = np.array([float(t.net_pl) for t in trades], dtype=float)
    if not np.isfinite(pls).all():
        raise ValueError("Trade P&L must be finite")
    entries = [int(t.entry_time) for t in trades]
    exits = [int(t.exit_time) for t in trades]
    if any(b < a for a, b in zip(exits, exits[1:])):
        raise ValueError("Trades must be in chronological exit order")
    points = [(int(row[0]), float(row[1])) for row in equity]
    if any(not math.isfinite(value) for _, value in points):
        raise ValueError("Equity observations must be finite")
    if any(b[0] < a[0] for a, b in zip(points, points[1:])):
        raise ValueError("Equity observations must be chronological")
    notes = []
    if not points:
        points = list(zip(exits, start_balance+np.cumsum(pls)))
        notes.append("closed_balance_reconstructed_from_net_trades_no_cashflows_assumed")
    available = entries + exits + [ts for ts, _ in points]
    lo = int(start_ts) if start_ts is not None else (min(available) if available else None)
    hi = int(end_ts) if end_ts is not None else (max(available) if available else None)
    if lo is not None and hi is not None and hi < lo:
        raise ValueError("Observation end precedes its start")
    if entries and ((start_ts is not None and min(entries) < lo) or
                    (end_ts is not None and max(exits) > hi)):
        raise ValueError("Trades fall outside the declared observation window")
    if start_ts is None or end_ts is None:
        notes.append("calendar_bounds_inferred_from_available_timestamps_may_include_warmup_or_miss_idle_tail")
    points = [(ts, value) for ts, value in points
              if (lo is None or ts >= lo) and (hi is None or ts <= hi)]
    timeline = ([(lo, start_balance)] if lo is not None else []) + points
    if hi is not None:
        timeline.append((hi, timeline[-1][1] if timeline else start_balance))
    end_balance = timeline[-1][1] if timeline else start_balance
    peak, last_peak = start_balance, lo
    max_dd, max_pct, max_duration = 0., 0., 0.
    underwater = False
    for ts, value in timeline:
        if value >= peak:
            if underwater and last_peak is not None:
                max_duration = max(max_duration, (ts-last_peak)/86400.)
            peak, last_peak, underwater = value, ts, False
        else:
            underwater = True
            max_dd = max(max_dd, peak-value)
            if peak > 0:
                max_pct = max(max_pct, (peak-value)/peak*100.)
            if last_peak is not None:
                max_duration = max(max_duration, (ts-last_peak)/86400.)
    if years is not None and (not math.isfinite(years) or years <= 0):
        raise ValueError("Explicit annualization years must be positive and finite")
    span = (hi-lo)/(365.25*86400.) if lo is not None and hi is not None and hi > lo else None
    if years is not None and start_ts is not None and end_ts is not None and not math.isclose(years, span or 0., rel_tol=1e-8):
        raise ValueError("Explicit years conflict with the declared calendar window")
    observed_years = float(years) if years is not None else span
    if observed_years is not None and observed_years < 1:
        notes.append("CAGR_extrapolates_less_than_one_calendar_year_not_evidence_of_annual_performance")
    # Sparse balance observations cannot erase a known bankruptcy in the
    # no-cashflow realized trade path merely by omitting its intermediate point.
    nonpositive = (any(value <= 0 for _, value in timeline) or
                   bool(np.any(start_balance+np.cumsum(pls) <= 0)))
    cash_consistent = math.isclose(end_balance, start_balance+float(pls.sum()), rel_tol=1e-10, abs_tol=1e-6)
    annual = None
    if not cash_consistent:
        notes.append("equity_end_disagrees_with_net_trades_cashflows_or_inconsistent_path_CAGR_unavailable")
    if nonpositive:
        notes.append("nonpositive_closed_balance_CAGR_not_financeable")
    if observed_years and cash_consistent and not nonpositive:
        try:
            annual = math.expm1(math.log(end_balance/start_balance)/observed_years)*100.
            if not math.isfinite(annual):
                annual = None
        except OverflowError:
            notes.append("calendar_CAGR_overflow_unavailable")
    return {"years": observed_years, "annualised_return_pct": annual,
            "max_drawdown": max_dd, "max_drawdown_pct": max_pct,
            "max_drawdown_duration_days": max_duration, "end_balance": end_balance,
            "closed_balance_nonpositive": nonpositive,
            "calmar_ratio": annual/max_pct if annual is not None and max_pct > 0 else None,
            "recovery_factor": float(pls.sum())/max_dd if max_dd > 0 else None,
            "metric_notes": notes}


def _bucket(trades: Sequence[Any], key) -> Dict[str, Dict[str, Any]]:
    """Group trades and report the few numbers that matter per group."""
    out: Dict[str, Dict[str, Any]] = {}
    for t in trades:
        k = key(t)
        b = out.setdefault(k, {"trades": 0, "wins": 0, "net_pl": 0.0,
                               "gross_profit": 0.0, "gross_loss": 0.0})
        b["trades"] += 1
        b["net_pl"] += t.net_pl
        if t.net_pl > 0:
            b["wins"] += 1
            b["gross_profit"] += t.net_pl
        else:
            b["gross_loss"] += abs(t.net_pl)
    for b in out.values():
        b["win_rate"] = round(_safe_div(b["wins"], b["trades"]) * 100, 1)
        b["profit_factor"] = (round(b["gross_profit"]/b["gross_loss"], 6)
                              if b["gross_loss"] > 0 else None)
        b["profit_factor_status"] = ("finite" if b["gross_loss"] > 0 else
                                     "unbounded_no_observed_losses" if b["gross_profit"] > 0 else
                                     "undefined_no_gains_or_losses")
        b["net_pl"] = round(b["net_pl"], 2)
        b["gross_profit"] = round(b["gross_profit"], 2)
        b["gross_loss"] = round(b["gross_loss"], 2)
    return out


def summarize(trades: Sequence[Any], equity: Sequence[Any],
              start_balance: float, *, start_ts=None, end_ts=None, years=None) -> TradeStats:
    s = TradeStats(start_balance=round(start_balance, 2))
    path = closed_balance_metrics(trades, equity, start_balance,
                                  start_ts=start_ts, end_ts=end_ts, years=years)
    for key in ("max_drawdown", "max_drawdown_pct", "max_drawdown_duration_days",
                "end_balance", "annualised_return_pct", "calmar_ratio", "recovery_factor"):
        value = path[key]
        setattr(s, key, round(value, 6) if value is not None else None)
    s.years = path["years"]
    s.metric_notes = path["metric_notes"]
    s.closed_balance_nonpositive = path["closed_balance_nonpositive"]
    s.trades = len(trades)
    if not trades:
        return s

    pls = np.array([t.net_pl for t in trades], dtype=float)
    rs = np.array([t.r_multiple for t in trades], dtype=float)

    wins = pls[pls > 0]
    losses = pls[pls < 0]
    s.wins, s.losses = int(len(wins)), int(len(losses))
    s.scratches = int((pls == 0).sum())
    s.win_rate = round(_safe_div(s.wins, s.trades) * 100, 2)

    s.gross_profit = round(float(wins.sum()), 6)
    s.gross_loss = round(float(abs(losses.sum())), 6)
    s.net_pl = round(float(pls.sum()), 6)
    ratios = pnl_ratios(pls)
    s.profit_factor = round(ratios["profit_factor"], 6) if ratios["profit_factor"] is not None else None
    s.profit_factor_status = ratios["profit_factor_status"]
    s.sortino_status = ratios["sortino_status"]
    s.expectancy = round(float(pls.mean()), 4)

    s.avg_win = round(float(wins.mean()), 6) if len(wins) else 0.0
    s.avg_loss = round(float(abs(losses.mean())), 6) if len(losses) else 0.0
    s.median_win = round(float(np.median(wins)), 6) if len(wins) else 0.0
    s.median_loss = round(float(abs(np.median(losses))), 6) if len(losses) else 0.0
    s.payoff_ratio = round(float(wins.mean())/float(abs(losses.mean())), 6) if len(wins) and len(losses) else None
    if len(wins) and len(losses):
        s.breakeven_win_rate = round(float(abs(losses.mean())) / (float(wins.mean()) + float(abs(losses.mean()))) * 100, 6)
        s.win_rate_margin = round(s.win_rate - s.breakeven_win_rate, 2)

    s.total_r = round(float(rs.sum()), 3)
    s.expectancy_r = round(float(rs.mean()), 4)
    win_r, loss_r = rs[rs > 0], rs[rs < 0]
    s.avg_win_r = round(float(win_r.mean()), 3) if len(win_r) else 0.0
    s.avg_loss_r = round(float(abs(loss_r.mean())), 3) if len(loss_r) else 0.0

    # --- streaks ---
    cw = cl = 0
    for p in pls:
        if p > 0:
            cw += 1
            cl = 0
        elif p < 0:
            cl += 1
            cw = 0
        s.max_consec_wins = max(s.max_consec_wins, cw)
        s.max_consec_losses = max(s.max_consec_losses, cl)

    # --- excursions ---
    mae = np.array([t.mae_r for t in trades], dtype=float)
    mfe = np.array([t.mfe_r for t in trades], dtype=float)
    s.avg_mae_r = round(float(mae.mean()), 3)
    s.avg_mfe_r = round(float(mfe.mean()), 3)
    # How much of the favourable excursion the exit actually banked. A low number
    # against a positive MFE is the signature of an exit clipping its winners.
    s.mfe_capture = round(_safe_div(float(rs.mean()), float(mfe.mean())), 3)

    mins = np.array([t.minutes_open for t in trades], dtype=float)
    s.avg_minutes_open = round(float(mins.mean()), 1)
    s.median_minutes_open = round(float(np.median(mins)), 1)
    s.avg_minutes_to_mfe = round(float(np.mean([t.minutes_to_mfe for t in trades])), 1)

    dupes = [t for t in trades if t.duplicate_of is not None]
    s.duplicate_trades = len(dupes)
    s.duplicate_pl = round(sum(t.net_pl for t in dupes), 2)
    pyr = [t for t in trades if t.is_pyramid]
    s.pyramid_trades = len(pyr)
    s.pyramid_pl = round(sum(t.net_pl for t in pyr), 2)
    s.ambiguous_trades = sum(1 for t in trades if t.intrabar_ambiguous)

    for t in trades:
        s.exit_reasons[t.exit_reason] = s.exit_reasons.get(t.exit_reason, 0) + 1

    s.by_session = _bucket(trades, lambda t: t.session)
    s.by_strategy = _bucket(trades, lambda t: t.strategy)
    s.by_month = _bucket(
        trades,
        lambda t: datetime.fromtimestamp(t.exit_time, tz=timezone.utc)
        .astimezone(IST).strftime("%Y-%m"),
    )

    s.return_pct = round(float(pls.sum()) / start_balance * 100, 6)

    # Zero-dollar target Omega equals after-cost trade-P&L profit factor.
    s.omega_ratio = s.profit_factor

    # --- Sortino Ratio ---
    # Uses only the *downside* semi-deviation, so large winners don't inflate
    # the denominator the way they would in Sharpe.  Threshold = 0.
    s.sortino_ratio = round(ratios["sortino_ratio"], 6) if ratios["sortino_ratio"] is not None else None

    return s


# ---------------------------------------------------------------------------
# Statistical confidence
# ---------------------------------------------------------------------------


def bootstrap_expectancy(trades: Sequence[Any], n: int = 5000,
                         seed: int = 7) -> Dict[str, float]:
    """Bootstrap CI for per-trade expectancy.

    A backtest reports one path. This asks how much of that path is sampling
    noise: if the 5th percentile of resampled expectancy is negative, the sample
    does not establish a positive edge regardless of the headline profit factor.
    """
    if len(trades) < 5:
        return {}
    rng = np.random.default_rng(seed)
    pls = np.array([t.net_pl for t in trades], dtype=float)
    draws = rng.choice(pls, size=(n, len(pls)), replace=True).mean(axis=1)
    return {
        "mean": round(float(draws.mean()), 4),
        "p05": round(float(np.percentile(draws, 5)), 4),
        "p50": round(float(np.percentile(draws, 50)), 4),
        "p95": round(float(np.percentile(draws, 95)), 4),
        "prob_negative": round(float((draws < 0).mean()), 4),
    }


def bootstrap_ci_metrics(
    trades: Sequence[Any],
    n_resamples: int = 1000,
    confidence_level: float = 0.95,
    seed: int = 42,
) -> Dict[str, Any]:
    """Bootstrap confidence intervals for Profit Factor and Sortino Ratio (1000 resamples, 95% CI).

    Resamples trade outcomes with replacement to construct empirical non-parametric
    confidence intervals for Profit Factor and Sortino Ratio.
    """
    if len(trades) < 5:
        return {}
    if not isinstance(n_resamples, int) or n_resamples <= 0 or not 0 < confidence_level < 1:
        raise ValueError("Positive resample count and confidence level in (0, 1) required")
    rng = np.random.default_rng(seed)
    pls = np.array([t.net_pl if hasattr(t, "net_pl") else float(t) for t in trades], dtype=float)
    if not np.isfinite(pls).all():
        raise ValueError("Finite net P&L required")
    n = len(pls)
    resampled = pls[rng.integers(0, n, size=(n_resamples, n))]
    wins = np.maximum(resampled, 0.).sum(axis=1)
    losses = np.maximum(-resampled, 0.).sum(axis=1)
    pfs = np.divide(wins, losses, out=np.full(n_resamples, np.inf), where=losses > 0)
    pfs[(wins == 0) & (losses == 0)] = np.nan
    means = resampled.mean(axis=1)
    downside = np.sqrt(np.mean(np.minimum(resampled, 0.) ** 2, axis=1))
    sortinos = np.divide(means, downside, out=np.full(n_resamples, np.inf), where=downside > 0)
    sortinos[(means == 0) & (downside == 0)] = np.nan
    observed = pnl_ratios(pls)
    tail = (1.-confidence_level)/2.

    def interval(values, key, status_key):
        # Keep infinite empirical outcomes in rank order; interpolation between
        # finite/inf values produces NaNs. Undefined 0/0 mass is disclosed.
        defined = np.sort(values[~np.isnan(values)])
        report = {"observed": (round(observed[key], 6) if observed[key] is not None else None),
                  "observed_status": observed[status_key],
                  "unbounded_fraction": float(np.isinf(values).mean()),
                  "undefined_fraction": float(np.isnan(values).mean())}
        for name, q in (("ci_lower", tail), ("median", .5), ("ci_upper", 1.-tail)):
            value = defined[max(0, math.ceil(q*len(defined))-1)] if len(defined) else None
            report[name] = round(float(value), 6) if value is not None and np.isfinite(value) else None
            report[name+"_status"] = ("undefined" if value is None else
                                      "unbounded" if np.isinf(value) else "finite")
        return report

    return {"n_trades": n, "n_resamples": n_resamples, "confidence_level": confidence_level,
            "quantile_method": "empirical_inverse_cdf_includes_unbounded_mass; undefined_0_over_0_mass_disclosed",
            "interval_scope": "conditional_on_defined_ratio; unbounded_mass_retained; undefined_mass_reported",
            "interval_scope": "conditional_on_defined_ratio; unbounded_outcomes_retained; undefined_mass_reported_separately",
            "basis": "IID_trade_PnL_bootstrap_not_serial_dependence_or_annualized_return_inference",
            "profit_factor": interval(pfs, "profit_factor", "profit_factor_status"),
            "sortino_ratio": interval(sortinos, "sortino_ratio", "sortino_status")}



def monte_carlo_paths(trades: Sequence[Any], start_balance: float,
                      n: int = 5000, seed: int = 7) -> Dict[str, float]:
    """Reshuffle trade order to get a drawdown distribution.

    The realised sequence is one ordering out of many. Reshuffling holds the
    trade population fixed and asks what drawdown the same edge could have
    produced in a less kind order.
    """
    if len(trades) < 5:
        return {}
    rng = np.random.default_rng(seed)
    pls = np.array([t.net_pl for t in trades], dtype=float)
    dds, finals, ruins = [], [], 0
    for _ in range(n):
        path = rng.permutation(pls)
        eq = start_balance + np.cumsum(path)
        eq = np.concatenate([[start_balance], eq])
        peak = np.maximum.accumulate(eq)
        dd = (peak - eq)
        dds.append(float(dd.max()))
        finals.append(float(eq[-1]))
        if eq.min() <= start_balance * 0.5:
            ruins += 1
    dds_a, fin_a = np.array(dds), np.array(finals)
    return {
        "median_max_dd": round(float(np.percentile(dds_a, 50)), 2),
        "p95_max_dd": round(float(np.percentile(dds_a, 95)), 2),
        "worst_max_dd": round(float(dds_a.max()), 2),
        "median_final": round(float(np.percentile(fin_a, 50)), 2),
        "p05_final": round(float(np.percentile(fin_a, 5)), 2),
        "prob_50pct_drawdown": round(ruins / n, 4),
        "prob_final_below_start": round(float((fin_a < start_balance).mean()), 4),
    }


def drop_best_worst(trades: Sequence[Any]) -> Dict[str, Any]:
    """How dependent is the result on a handful of trades?

    If removing the three best trades flips the strategy negative, the edge lives
    in outliers rather than in the rule.
    """
    if len(trades) < 10:
        return {}
    pls = sorted(t.net_pl for t in trades)
    total = sum(pls)
    out: Dict[str, Any] = {"net_pl": round(total, 2)}
    for k in (1, 3, 5):
        out[f"drop_best_{k}"] = round(total - sum(pls[-k:]), 2)
        out[f"drop_worst_{k}"] = round(total - sum(pls[:k]), 2)
    top3 = sum(pls[-3:])
    out["top3_share_of_gross_profit"] = round(
        _safe_div(top3, sum(p for p in pls if p > 0)) * 100, 1
    )
    return out


# ---------------------------------------------------------------------------
# Correlation-aware multiple-testing correction  (Vertox K_eff, 2026-05-14)
# ---------------------------------------------------------------------------


def k_eff_correction(
    return_series: Sequence[Sequence[float]],
    n_tested_raw: int,
) -> Dict[str, Any]:
    """Compute the effective number of independent strategies (K_eff).

    DePrado's Deflated Sharpe Ratio corrects for multiple testing by applying
    a Bonferroni penalty scaled by the *raw* number of trials (n_tested_raw).
    This dramatically overstates the penalty when parameter variants are
    correlated -- testing SL=0.4 vs SL=0.5 is not two independent experiments.

    Vertox (2026-05-14) defines K_eff via the eigenspectrum of the return
    correlation matrix Sigma:

        p_i   = lambda_i / sum(lambda)          # normalised eigenvalues
        H     = -sum(p_i * log(p_i))            # Shannon entropy of spectrum
        K_eff = exp(H)                           # effective count in [1, K]

    Intuition:
      - All strategies identical  -> one dominant eigenvalue -> H=0 -> K_eff=1
      - All strategies independent -> flat eigenspectrum   -> H=log(K) -> K_eff=K
      - Real portfolios land somewhere in between.

    The Bonferroni p-value threshold to use is alpha / K_eff rather than
    alpha / K, making the multiple-testing correction correlation-aware.

    Args:
        return_series: list/array of per-trade P&L series, one per strategy
                       variant.  Series need not be the same length -- shorter
                       ones are aligned to the overlapping window.
        n_tested_raw:  raw number of strategy configurations tested (K).

    Returns dict with keys:
        k_raw          -- the raw count you passed in
        k_eff          -- correlation-aware effective count
        reduction_pct  -- how much smaller K_eff is vs K (pct)
        eigenvalues    -- sorted eigenvalues of the correlation matrix
        bonferroni_raw -- alpha=0.05 / K
        bonferroni_keff-- alpha=0.05 / K_eff  (the honest threshold)
    """
    if not return_series or n_tested_raw < 2:
        return {
            "k_raw": n_tested_raw,
            "k_eff": float(n_tested_raw),
            "reduction_pct": 0.0,
            "eigenvalues": [],
            "bonferroni_raw": round(0.05 / max(n_tested_raw, 1), 6),
            "bonferroni_keff": round(0.05 / max(n_tested_raw, 1), 6),
            "note": "Need >= 2 series to compute correlation structure.",
        }

    # Align series lengths to the minimum common length (latest window).
    min_len = min(len(s) for s in return_series)
    if min_len < 5:
        return {
            "k_raw": n_tested_raw,
            "k_eff": float(n_tested_raw),
            "reduction_pct": 0.0,
            "eigenvalues": [],
            "bonferroni_raw": round(0.05 / n_tested_raw, 6),
            "bonferroni_keff": round(0.05 / n_tested_raw, 6),
            "note": "Too few overlapping trades to estimate correlation.",
        }

    mat = np.array([list(s)[-min_len:] for s in return_series], dtype=float)

    # Correlation matrix (use numpy corrcoef; handles constant series gracefully).
    corr = np.corrcoef(mat)                    # shape (K, K)
    # Clip to [-1, 1] to handle floating-point edge cases.
    corr = np.clip(corr, -1.0, 1.0)

    # Eigenvalue decomposition.  corrcoef is symmetric so eigvalsh is stable.
    eigenvalues = np.linalg.eigvalsh(corr)     # ascending order
    eigenvalues = np.maximum(eigenvalues, 0)   # numerical noise -> tiny negatives

    total = eigenvalues.sum()
    if total == 0:
        k_eff = float(n_tested_raw)
    else:
        p = eigenvalues / total                # normalised (sums to 1)
        # Shannon entropy of eigenspectrum.
        # Filter to strictly positive entries before log to avoid divide-by-zero
        # warnings (numpy evaluates both branches of np.where before masking).
        p_nz = p[p > 0]
        h = -float(np.sum(p_nz * np.log(p_nz)))
        k_eff = math.exp(h)                    # in [1, K] by construction

    k_eff = min(k_eff, float(n_tested_raw))    # cap at K (numerical safety)
    reduction_pct = round((1.0 - k_eff / n_tested_raw) * 100, 1)

    return {
        "k_raw": n_tested_raw,
        "k_eff": round(k_eff, 2),
        "reduction_pct": reduction_pct,
        "eigenvalues": [round(float(e), 4) for e in sorted(eigenvalues, reverse=True)],
        "bonferroni_raw": round(0.05 / n_tested_raw, 6),
        "bonferroni_keff": round(0.05 / k_eff, 6),
        "interpretation": (
            f"Your {n_tested_raw} tested configs are effectively {k_eff:.1f} "
            f"independent experiments ({reduction_pct:.0f}% correlation overlap). "
            f"Use p < {0.05/k_eff:.4f} as your significance threshold, "
            f"not p < {0.05/n_tested_raw:.4f}."
        ),
    }

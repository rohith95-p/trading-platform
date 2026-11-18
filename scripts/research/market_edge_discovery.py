"""Economic hurdle screen of atlas effects, NOT a strategy backtest.

Close-to-close conditional movement is not an executable return. No entries,
exits, accounts, PFs or hypothetical payout results are manufactured here.
"""
import json
from pathlib import Path

import numpy as np

from scripts.research.market_atlas import return_features, sha
from src.backtesting.master import load_master, HOLDOUT_FROM
from src.backtesting.costs import SCENARIOS

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "research/results/finalization_2026-11-18"


def main():
    results = {}
    cost = SCENARIOS["realistic_ecn"]
    for tf, step in (("M1", 60), ("M15", 900)):
        b = load_master((tf,), end=HOLDOUT_FROM, use_cache=False)
        a = getattr(b, tf.lower())
        r, scale = return_features(a, step)
        eligible = (np.abs(r[:-1]) > 2*scale[:-1]) & np.isfinite(r[1:])
        direction = -np.sign(r[:-1])
        gross = direction * (a["close"][1:] - a["close"][:-1])
        spread = np.array([cost.spread_price(b.spec.point, float(p)) for p in a["spread"][1:]])
        friction = spread + 2*cost.slip(b.spec.point) + cost.commission(.02)/(.02*b.spec.contract_size)
        assert np.all(a["time"] < HOLDOUT_FROM)
        results[tf] = {"n_extreme":int(eligible.sum()), "conditional_reference_move_usd_per_oz":float(gross[eligible].mean()),
                       "modeled_round_trip_hurdle_usd_per_oz":float(friction[eligible].mean()),
                       "difference_not_trade_expectancy":float((gross-friction)[eligible].mean()),
                       "cost_model":cost.descriptor(), "point":b.spec.point, "contract_size":b.spec.contract_size,
                       "caveat":"Previous close reference is not a fill; short/long spread timing and slippage approximate. No financing, stops, sizing, paths, positions or account results evaluated.",
                       "provenance": b.provenance}
        print(tf, results[tf]["conditional_reference_move_usd_per_oz"], results[tf]["modeled_round_trip_hurdle_usd_per_oz"], flush=True)
    payload = {"script_sha256":sha(Path(__file__)), "classification":"exploratory_economic_hurdle_not_backtest", "effects":results}
    (OUT / "economic_hurdle.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    lines = ["# Market edge discovery — 2026-11-18", "", "No qualified positive-expectancy strategy was established. This study distinguishes a detectable conditional effect from an executable trading advantage.", "",
             "## Fixed atlas findings", "", "The18 fixed exploratory comparisons use monthly bootstrap uncertainty and Bonferroni correction within this family. They do not erase prior searches or establish independence. November holdout remains untouched.", "",
             "- Volatility clusters across intraday resolutions. This supports conditional risk forecasting, not a direction to buy or sell.",
             "- Extreme M1 and M15 moves exhibit small next-bar reversal in each of the three historical era groups. M15 mean signed continuation is−0.359bps (reversal+0.359bps),95% interval[−0.556,−0.173]bps; adjusted centered-bootstrap p=.018, limited by999 draws. This may include bid bounce and source artifacts.",
             "- H1 extreme continuation changes sign in the most recent era; H4 has only433 extreme observations, D1 only174. No dependable cross-regime directional conclusion follows.",
             "- Macro same-row correlations are much stronger than most lagged correlations and lack certified information-availability timestamps. They do not authorize same-day forecast features.", "",
             "## Economic hurdle", "", "The same predetermined extreme thresholds were used for an approximate cost comparison. This is a descriptive reference-price movement, never an execution/backtest substitute.", "",
             "| Resolution | Events | Mean reversal reference move $/oz | Mean modeled round-trip hurdle $/oz |", "|---|---:|---:|---:|"]
    for tf, d in results.items():
        lines.append(f"| {tf} | {d['n_extreme']:,} | {d['conditional_reference_move_usd_per_oz']:.5f} | {d['modeled_round_trip_hurdle_usd_per_oz']:.5f} |")
    lines += ["", "Hurdle uses historical spread field or its explicit fallback, two assumed adverse slips and commission converted to price units. Zero archive spreads mean unavailable. Fees are repository ECN scenarios, not intended Atlas contract verification. Full candidate evaluation must additionally include fills, gap risk, ambiguity, financing, risk, account constraints and broker checks.", "",
              "## Promotion decision", "", "Neither fixed directional lead clears the reasonable-cost-margin gate in the atlas preregistration. They are not promoted into a newly fitted strategy. Volatility forecasting alone also fails the directional-alpha gate. No profitable strategy, Sharpe, DSR, PBO or payout rate is invented for a non-existent candidate.", "",
              "## Falsifiable next directions", "", "1. Publication-timed macro surprises with a causal post-release entry delay. Requires actual/revised release values and pre-release consensus with availability timestamps, not merely dates. Test matched event-time controls and exact bid/ask execution.",
              "2. Volatility-aware abstention evaluated against an already positive independently confirmed signal. It must improve risk-adjusted net outcomes against matched exposure; it cannot create direction from a failed portfolio.",
              "3. Cross-source replication of intraday reversal using synchronized observed bid/ask and noise-aware outcomes. If the effect disappears after using executable sides, reject it as nontradeable microstructure.", "",
              "Each needs a separate committed candidate protocol before evaluation. Reusing examined2004–2026 data remains development; only prospectively frozen data can provide fresh confirmation. Reproduce with `venv/Scripts/python.exe -m scripts.research.market_edge_discovery`."]
    (ROOT / "research/MARKET_EDGE_DISCOVERY.md").write_text("\n".join(lines)+"\n", encoding="utf-8")


if __name__ == "__main__":
    main()

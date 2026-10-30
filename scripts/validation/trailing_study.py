"""Does trailing the profit beat the fixed target? (owner 2026-10-30)

Live 4-leg setup (gate on, protector off, 24h, 0.02 lots, Atlas guard, realistic ECN costs), M1 bars,
DEV / TEST / RECENT. Variants:
  fixed       fixed stop and target (live today)
  trail_tight engine trail: starts at 0.7 ATR profit, 0.3 ATR behind price, target kept
  ride_1.5    no target; trail starts at 1.0 ATR profit, 1.5 ATR behind price (rides until stopped / Friday close)
  ride_2.5    same, 2.5 ATR behind price
  breakeven   stop moved to entry +0.1 ATR once the trade is 2 ATR in profit, target kept

    python scripts/validation/trailing_study.py
"""
import os
import sys
import json
import dataclasses
from concurrent.futures import ProcessPoolExecutor

os.environ["ULTRA_TRADE_24H"] = "1"
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from scripts.validation import independent_audit_run as base   # noqa: E402

VARIANTS = {
    "fixed": dict(),
    "trail_tight": dict(enable_trailing=True, trail_activation_atr=0.7, trail_distance_atr=0.3),
    "ride_1.5": dict(enable_trailing=True, trail_activation_atr=1.0, trail_distance_atr=1.5, _no_tp=True),
    "ride_2.5": dict(enable_trailing=True, trail_activation_atr=1.0, trail_distance_atr=2.5, _no_tp=True),
    "breakeven": dict(be_trigger_atr=2.0, be_offset_atr=0.1),
}
OUT = os.path.join("research", "results", "trailing_study_2026-10-30.json")


def job(variant, name, a, b):
    from src.backtesting import engine as E
    from src.core import risk_manager as rm_mod
    kw = dict(VARIANTS[variant])
    no_tp = kw.pop("_no_tp", False)
    rm_mod.TRAIL_ACTIVATION_ATR, rm_mod.TRAIL_DISTANCE_ATR = 0.7, 0.3   # reset per job (module globals)
    orig_preset = E.EngineConfig.live_parity_preset

    def preset(**o):
        return orig_preset(**{**o, **kw})
    E.EngineConfig.live_parity_preset = classmethod(lambda cls, **o: preset(**o))
    if no_tp:
        orig_open = E.BacktestEngine._open

        def _open(self, *x, **k):
            pos = orig_open(self, *x, **k)
            if pos is not None:
                pos.tp = 1e9 if pos.is_buy else -1e9
            return pos
        E.BacktestEngine._open = _open
    _, tr, halts = base.job(name, a, b)
    return variant, name, tr, halts


if __name__ == "__main__":
    from scripts.research.atlas_filter_study import utc, KAGGLE_END
    W = [("DEV", utc(2022, 8, 1), utc(2024, 6, 1)), ("TEST", utc(2024, 6, 1), KAGGLE_END),
         ("RECENT", utc(2026, 7, 6), utc(2026, 10, 30))]
    jobs = [(v, *w) for v in VARIANTS for w in W]
    out = {}
    with ProcessPoolExecutor(6, max_tasks_per_child=1) as ex:
        for v, name, tr, halts in ex.map(job, *zip(*jobs)):
            out.setdefault(v, {})[name] = dict(trades=tr, halts=halts)
            print("done", v, name, len(tr), flush=True)
    json.dump(out, open(OUT, "w"))

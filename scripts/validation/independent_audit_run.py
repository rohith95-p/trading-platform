"""Step 1 of the independent audit of the live 4-leg backtest (protector OFF, 24h, Atlas guard, realistic_ecn costs).

Runs the engine (live settings: 3 positions, 3 per direction, 0.02 lots); step 2 re-derives every trade from raw M1 bars with numpy, without engine code:
  P&L identity, commission, swap/nights, exit bar + exit price for SL/TP, no missed earlier hit,
  gap-through-stop optimism, balance chain. Plus a truncation (look-ahead) test.
"""
import sys, os, json, dataclasses, datetime as dt
os.environ["ULTRA_TRADE_24H"] = "1"
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT); os.chdir(ROOT)
from concurrent.futures import ProcessPoolExecutor
import numpy as np

OUT = os.path.join("research", "results", "audit_2026-11-01")
utc = lambda *a: int(dt.datetime(*a, tzinfo=dt.timezone.utc).timestamp())



def bars(a=None, b=None):
    """The one master series (src/backtesting/master.py), not a local merge.

    Narrowed to the window being run: four parallel workers cannot each hold the
    whole 6.8-million-bar minute series.
    """
    from src.backtesting.master import load_master
    return load_master(("M15", "M1", "D1"), start=a, end=b)


def job(name, a, b, protect=False):
    from src.backtesting.engine import BacktestEngine, EngineConfig
    from src.backtesting.costs import SCENARIOS
    from src.strategies.portfolio_atlas import PORTFOLIO
    from src.atlas.rules import AtlasRuleEngine, AtlasState, AccountInfo, load_rules
    # load_master caches per window inside the worker process, so this is cheap
    # on a repeat and correct when one worker handles two different windows
    _B = bars(a, b)

    class AtlasGuarded(BacktestEngine):
        def run(self, *x, **k):
            self._ae = AtlasRuleEngine(load_rules(allow_unverified=["daily_loss_eod_computation", "ea_approval_required"]))
            self._st, self._block, self._halt_day, self.halts = None, False, None, []
            return super().run(*x, **k)

        def _manage(self, rm, m15_view, bar, point, spread_pts):
            ts = int(bar["time"])
            fl = sum((p.price_current - p.entry_price) * (1 if p.is_buy else -1) * self._value_per_price(p.lots)
                     for p in self.positions)
            now = dt.datetime.fromtimestamp(ts, dt.timezone.utc)
            acct = AccountInfo(balance=self.balance, equity=self.balance + fl, margin=0.0,
                               free_margin=self.balance, ts_utc=now, floating_pnl=fl)
            if self._st is None:
                self._st = AtlasState.new(initial_balance=5000.0, now_utc=now, phase="evaluation", equity=acct.equity)
            self._ae.update_state(acct, self._st, now)
            if self._halt_day is not None and now.date() > self._halt_day:
                self._halt_day = None
            res = self._ae.monitor_detail(acct, self._st, now)
            self._block = res.action != "OK" or self._halt_day is not None
            if res.action == "FLATTEN":
                for pos in list(self.positions):
                    base = float(bar["close"])
                    self._close(pos, base if pos.is_buy else self.cost.ask(base, point, spread_pts), ts, "ATLAS_FLATTEN")
                self._halt_day = now.date()
                self.halts.append(now.strftime("%Y-%m-%d %H:%M"))
            super()._manage(rm, m15_view, bar, point, spread_pts)

        def _parity_entries(self, *x, **k):
            return None if self._block else super()._parity_entries(*x, **k)

    cfg = EngineConfig.live_parity_preset(sizing_mode="fixed", fixed_lots=0.02, starting_balance=5000.0,
                                          max_concurrent=3, max_same_direction=3, history_bars=7500,
                                          protect_profit=protect, m1_policy="skip")
    eng = AtlasGuarded(bars=_B, cost=SCENARIOS["realistic_ecn"], config=cfg)
    res = eng.run([c() for c in PORTFOLIO], a, b)
    keep = ("ticket strategy is_buy lots entry_time exit_time entry_price exit_price sl tp initial_sl exit_reason "
            "gross_pl commission net_pl swap nights_held balance_after r_multiple").split()
    tr = [{k: (v.item() if hasattr(v, "item") else v) for k, v in dataclasses.asdict(t).items() if k in keep}
          for t in res.trades]
    d = res.diagnostics
    m1 = dict(bars_skipped_no_m1=d["bars_skipped_no_m1"],
              exits_unchecked_no_m1=d["exits_unchecked_no_m1"],
              bars_without_m1=d["bars_without_m1"],
              partial_m1_candles=d["partial_m1_candles"],
              partial_m1_minutes_missing=d["partial_m1_minutes_missing"])
    return name, tr, eng.halts, m1


if __name__ == "__main__":
    from src.backtesting.master import WINDOWS, window

    # the live 4-leg portfolio; RECENT_CUT re-runs RECENT short to probe look-ahead
    W = list(WINDOWS) + [("RECENT_CUT", window("RECENT")[0], utc(2026, 9, 15))]
    out = {}
    with ProcessPoolExecutor(4) as ex:
        for name, tr, halts, m1 in ex.map(job, *zip(*W)):
            out[name] = dict(trades=tr, halts=halts, m1=m1)
            print(f"done {name} {len(tr)} trades  halts {halts}  "
                  f"candles with no M1 {m1['bars_skipped_no_m1']} "
                  f"(exits unchecked {m1['exits_unchecked_no_m1']}), "
                  f"partly covered {m1['partial_m1_candles']} "
                  f"({m1['partial_m1_minutes_missing']} minutes missing)", flush=True)
    os.makedirs(OUT, exist_ok=True)
    json.dump(out, open(os.path.join(OUT, "trades.json"), "w"))

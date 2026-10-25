"""Parametric sweep for Donchian breakout with trend filter.

Key insight from initial backtest: Donchian PF 2.0+ on trending OOS periods
but PF 0.35 on ranging DEV. Adding a trend filter (price > N-day MA for longs,
< N-day MA for shorts) should eliminate whipsaw losses in consolidation.

Run: python -I scripts/research/donchian_sweep_2026_10_25.py
"""
import sys, os, datetime as dt, dataclasses
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from src.backtesting.engine import BacktestEngine, EngineConfig
from src.backtesting.data import load_bars
from src.backtesting.costs import SCENARIOS
from src.backtesting.metrics import summarize
from src.strategies.base_strategy import BaseStrategy, Signal, mt5
from src.strategies.momentum_strategies import _build_d1_from_m15, _ema


class DonchianFiltered(BaseStrategy):
    """Donchian breakout with configurable trend filter."""
    execute_immediately = True
    edge_trigger = True
    session = (0.0, 24.0)

    def __init__(self, channel=20, trend_ma=0, sl_atr_mult=2.0, tp_atr_mult=6.0, magic=7300):
        self.channel = channel
        self.trend_ma = trend_ma
        self.sl_atr_mult = sl_atr_mult
        self.tp_atr_mult = tp_atr_mult
        self.magic = magic
        needed = max(channel, trend_ma) + 5
        self.name = "DONCHIAN_D1_%d_MA%d" % (channel, trend_ma)
        self._min_bars = (needed) * 96 + 200

    def evaluate(self, m15_rates, m5_rates=None):
        if m15_rates is None or len(m15_rates) < self._min_bars:
            return None
        bar_time = int(m15_rates["time"][-2])
        if bar_time % 86400 != 1800:
            return None

        needed = max(self.channel, self.trend_ma) + 3
        d1 = _build_d1_from_m15(m15_rates, needed)
        if d1 is None:
            return None
        _, _, d_high, d_low, d_close = d1
        if len(d_close) < max(self.channel, self.trend_ma) + 2:
            return None

        prev_high = d_high[-1 - self.channel:-1].max()
        prev_low = d_low[-1 - self.channel:-1].min()
        p_high = d_high[-2 - self.channel:-2].max()
        p_low = d_low[-2 - self.channel:-2].min()

        # Trend filter: price must be on the right side of the MA
        if self.trend_ma > 0:
            ma = _ema(d_close, self.trend_ma)
            if np.isnan(ma[-1]):
                return None
            above_ma = d_close[-1] > ma[-1]
        else:
            above_ma = None

        if d_close[-1] > prev_high and not d_close[-2] > p_high:
            if above_ma is not None and not above_ma:
                return None
            return Signal(direction=mt5.ORDER_TYPE_BUY,
                          strategy_name=self.name, magic=self.magic, is_buy=True)
        if d_close[-1] < prev_low and not d_close[-2] < p_low:
            if above_ma is not None and above_ma:
                return None
            return Signal(direction=mt5.ORDER_TYPE_SELL,
                          strategy_name=self.name, magic=self.magic, is_buy=False)
        return None

    def check_pending_confirmation(self, m15_rates):
        return None
    def set_pending(self, signal, candle_time):
        pass


ts = lambda y, m, d: int(dt.datetime(y, m, d, tzinfo=dt.timezone.utc).timestamp())

SPLITS = [
    ("DEV",      ts(2022, 8, 1),  ts(2024, 2, 1)),
    ("VALIDATE", ts(2024, 2, 1),  ts(2025, 6, 1)),
    ("HOLDOUT",  ts(2025, 6, 1),  ts(2026, 10, 13)),
]

VARIANTS = [
    # (channel, trend_ma, sl_atr, tp_atr)
    (20, 0,   2.0, 6.0),   # baseline (no filter)
    (20, 50,  2.0, 6.0),   # 50-day EMA filter
    (20, 100, 2.0, 6.0),   # 100-day EMA filter
    (20, 200, 2.0, 6.0),   # 200-day EMA filter
    (10, 50,  2.0, 4.0),   # shorter channel, tighter TP
    (55, 50,  2.0, 8.0),   # Turtle System 1 channel
    (20, 50,  1.5, 4.0),   # tighter stops
    (20, 50,  3.0, 9.0),   # wider stops
]

print("Loading data...", flush=True)
bars = load_bars("XAUUSDm", timeframes=("M15", "M5", "M1", "D1"))
coarse = dataclasses.replace(bars, m1=None)

print("\n%-35s | %-32s | %-32s | %-32s" % ("VARIANT", "DEV", "VALIDATE", "HOLDOUT"))
print("-" * 140)

for ch, ma, sl, tp in VARIANTS:
    label = "Ch%d_MA%d_SL%.1f_TP%.1f" % (ch, ma, sl, tp)
    row = label.ljust(35) + " |"
    for split_name, start, end in SPLITS:
        strat = DonchianFiltered(ch, ma, sl, tp)
        hist = max(ch, ma, 50) * 96 + 300
        cfg = EngineConfig(
            sizing_mode="fixed", fixed_lots=0.01, starting_balance=105.74,
            history_bars=max(7500, hist),
            enable_d1_bias_gate=False, dedup_per_candle=True,
            max_concurrent=2, max_same_direction=2,
        )
        b = bars if split_name == "HOLDOUT" else coarse
        engine = BacktestEngine(bars=b, cost=SCENARIOS["realistic_ecn"], config=cfg)
        res = engine.run([strat], start, end)
        d = summarize(res.trades, res.equity, 105.74).to_dict()
        bal = np.array([105.74] + [t.balance_after for t in res.trades])
        peak = np.maximum.accumulate(bal)
        max_dd = (peak - bal).max()
        dd_pct = max_dd / peak[np.argmax(peak - bal)] * 100 if len(peak) > 0 and peak.max() > 0 else 0
        pf = d.get("profit_factor", 0)
        n = d.get("trades", 0)
        wr = d.get("win_rate", 0)
        net = d.get("net_pl", 0)
        row += " n=%2d PF=%.2f wr=%.0f%% $%+.0f DD%.0f%% |" % (n, pf, wr, net, dd_pct)
    print(row, flush=True)

print("\nDone.", flush=True)

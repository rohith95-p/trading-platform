"""Asset-agnostic backtesting: instrument registry, cost models, sizing, and the
gold-unchanged regression.

The engine regression numbers below were recorded from the engine BEFORE the
asset-agnostic change (git HEAD 8c0e982 + working tree, 2026-10-16), running
TrendPullbackV5 at a fixed 0.01 lot over two weeks of real XAUUSDm data. They
must never move because of instrument work.
"""
import hashlib
import json
import os
from dataclasses import replace
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from src.backtesting.costs import SCENARIOS, CostModel
from src.instruments import (REGISTRY, UnknownInstrumentError, cost_model_for,
                             get_meta, risk_lots, value_per_price_per_lot)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_ROOT = os.path.join(ROOT, "research", "data")


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

def test_registry_has_expected_symbols_and_fields():
    assert set(REGISTRY) == {"XAUUSDm", "EURUSDm", "GBPUSDm", "USDJPYm", "BTCUSDm", "ETHUSDm"}
    x = get_meta("XAUUSDm")
    assert (x.digits, x.contract_size, x.swap_long_points, x.swap_short_points) == (3, 100.0, -500.0, 0.0)
    assert get_meta("BTCUSDm").weekend_trading is True
    assert get_meta("EURUSDm").weekend_trading is False
    assert get_meta("USDJPYm").swap_short_points == -13.9
    assert get_meta("USDJPYm").volume_max == 300.0
    for m in REGISTRY.values():
        assert m.source and m.retrieved == "2026-10-16"
        assert m.asset_class in ("gold", "forex", "crypto")
        assert m.commission_per_lot_roundtrip == 0.0
        assert not m.is_verified("swap_units")        # swap_mode still to be confirmed


def test_eth_unknowns_are_none_and_flagged():
    e = get_meta("ETHUSDm")
    assert e.swap_short_points is None and e.typical_spread_points is None
    assert not e.is_verified("swap_short_points")
    assert e.volume_min == 0.1 and e.volume_max == 2000.0


@pytest.mark.parametrize("bad", ["XAUUSD", "xauusdm", "AAPL", "", None, "EURJPYm"])
def test_unknown_symbol_raises_never_gold(bad):
    with pytest.raises(UnknownInstrumentError):
        get_meta(bad)
    with pytest.raises(UnknownInstrumentError):
        cost_model_for(bad, "realistic")


# ---------------------------------------------------------------------------
# Lot sizing
# ---------------------------------------------------------------------------

def test_eurusd_half_percent_20_pips():
    # $10k * 0.5% = $50; 20 pips = 0.0020 -> $200/lot -> 0.25 lots
    lots, risk, ok = risk_lots(10_000, 0.005, 0.0020, get_meta("EURUSDm"))
    assert ok and lots == pytest.approx(0.25)
    assert risk == pytest.approx(0.005)


def test_btc_500_dollar_stop():
    # $10k * 1% = $100; $500 stop on 1 BTC/lot -> 0.2 lots
    lots, risk, ok = risk_lots(10_000, 0.01, 500.0, get_meta("BTCUSDm"))
    assert ok and lots == pytest.approx(0.20) and risk == pytest.approx(0.01)


def test_gold_sizing():
    # $10k * 0.5% = $50; $5 stop * 100 oz = $500/lot -> 0.10 lots
    lots, risk, ok = risk_lots(10_000, 0.005, 5.0, get_meta("XAUUSDm"))
    assert ok and lots == pytest.approx(0.10)


def test_rounds_down_to_step_never_over_budget():
    # raw = 50 / (0.0017*100000) = 0.2941 -> 0.29
    lots, risk, ok = risk_lots(10_000, 0.005, 0.0017, get_meta("EURUSDm"))
    assert lots == pytest.approx(0.29) and risk <= 0.005 and ok


def test_min_lot_over_budget_is_flagged_not_ok():
    # $100 account, 1% = $1, gold $5 stop => 0.002 lots raw. Min lot risks $5.
    lots, risk, ok = risk_lots(100.0, 0.01, 5.0, get_meta("XAUUSDm"))
    assert lots == 0.01 and ok is False and risk == pytest.approx(0.05)


def test_min_lot_within_budget_is_ok_and_max_clamped():
    m = get_meta("ETHUSDm")                       # min lot 0.1
    lots, _, ok = risk_lots(10_000, 0.01, 10.0, m)     # raw 10 lots
    assert ok and lots == pytest.approx(10.0)
    lots, _, ok = risk_lots(10_000_000, 0.5, 1.0, m)   # raw 5e6 -> clamp 2000
    assert lots == 2000.0


def test_usdjpy_needs_price_and_converts():
    m = get_meta("USDJPYm")
    with pytest.raises(ValueError):
        risk_lots(10_000, 0.005, 0.20, m)         # quote JPY, no price
    # $50 budget; 20 pips = 0.20 JPY; per lot = 0.20 * 100000/150 = $133.33 -> 0.37
    lots, risk, ok = risk_lots(10_000, 0.005, 0.20, m, price=150.0)
    assert ok and lots == pytest.approx(0.37) and risk <= 0.005
    assert value_per_price_per_lot(m, 150.0) == pytest.approx(100000 / 150.0)


def test_explicit_value_per_price_override():
    lots, _, ok = risk_lots(10_000, 0.005, 0.0020, get_meta("EURUSDm"), value_per_price=50_000)
    assert ok and lots == pytest.approx(0.5)


@pytest.mark.parametrize("args", [(0, 0.01, 1.0), (100, 0, 1.0), (100, 0.01, 0)])
def test_degenerate_inputs(args):
    assert risk_lots(*args, get_meta("XAUUSDm")) == (0.0, 0.0, False)


# ---------------------------------------------------------------------------
# Cost-model selection
# ---------------------------------------------------------------------------

def test_cost_model_per_instrument():
    g = cost_model_for("XAUUSDm", "realistic")
    assert (g.swap_long_points, g.swap_short_points) == (-500.0, 0.0)
    assert g.fixed_spread_points == 240.0 and g.slippage_points == pytest.approx(20.0)
    assert g.calibrated_for == "XAUUSDm"

    e = cost_model_for("EURUSDm", "realistic")
    assert e.swap_long_points == -5.5 and e.fixed_spread_points == 8.0
    assert e.slippage_points == pytest.approx(8.0 / 12.0)      # scaled to the instrument

    u = cost_model_for("USDJPYm", "observed")
    assert (u.swap_long_points, u.swap_short_points) == (0.0, -13.9)
    assert u.slippage_points == 0.0

    b = cost_model_for("BTCUSDm", "stressed")
    assert b.swap_long_points == -1910.2 and b.spread_multiplier == 2.0
    assert b.slippage_points == pytest.approx(160.0)


def test_cost_model_none_of_gold_leaks_into_other_symbols():
    for sym in ("EURUSDm", "GBPUSDm", "USDJPYm", "BTCUSDm"):
        c = cost_model_for(sym, "realistic")
        assert c.swap_long_points != -515.5 and c.fixed_spread_points != 260.0


def test_scenarios_frictionless_ecn_and_commission_param():
    f = cost_model_for("EURUSDm", "frictionless")
    assert f.enable_swap is False and f.fixed_spread_points == 0.0 and f.slippage_points == 0.0
    assert cost_model_for("EURUSDm", "realistic_ecn").commission_per_lot_roundtrip == 3.50
    assert cost_model_for("EURUSDm", "realistic").commission_per_lot_roundtrip == 0.0
    assert cost_model_for("EURUSDm", "realistic", commission_per_lot_roundtrip=7.0
                          ).commission_per_lot_roundtrip == 7.0
    assert cost_model_for("EURUSDm", "observed_no_swap").enable_swap is False
    with pytest.raises(ValueError):
        cost_model_for("EURUSDm", "nonsense")


def test_unknown_swap_and_spread_are_explicit_for_eth():
    with pytest.raises(ValueError):
        cost_model_for("ETHUSDm", "realistic")                 # spread unknown
    c = cost_model_for("ETHUSDm", "observed", fixed_spread_points=300.0)
    assert c.swap_long_points == -57.1 and c.swap_short_points == -57.1   # pessimistic
    z = cost_model_for("ETHUSDm", "observed", fixed_spread_points=300.0, unknown_swap="zero")
    assert z.swap_short_points == 0.0
    with pytest.raises(ValueError):
        cost_model_for("ETHUSDm", "observed", fixed_spread_points=300.0, unknown_swap="error")


def test_gold_swap_math_unchanged():
    # Legacy CostModel defaults are untouched: 0.01 lot long pays $0.5155/night.
    c = CostModel()
    assert (c.swap_long_points, c.fixed_spread_points) == (-515.5, 260.0)
    day = 86400
    assert c.swap(0.01, True, 0, day, 0.001, 100.0) == pytest.approx(-0.5155)
    assert c.swap(0.01, False, 0, day, 0.001, 100.0) == 0.0
    assert all(v.calibrated_for == "XAUUSDm" for v in SCENARIOS.values())


# ---------------------------------------------------------------------------
# Engine: gold regression + asset-agnostic switches
# ---------------------------------------------------------------------------

def _ts(d):
    return int(datetime.strptime(d, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())


needs_data = pytest.mark.skipif(
    not os.path.exists(os.path.join(DATA_ROOT, "XAUUSDm_M1.npy")),
    reason="cached XAUUSDm research data not present")


@pytest.fixture(scope="module")
def xau_bars():
    from src.backtesting.data import load_bars
    return load_bars("XAUUSDm", timeframes=("M15", "M5", "M1", "D1"), data_root=DATA_ROOT)


def _run(bars, scenario, a, b, **cfg_kw):
    from src.backtesting.engine import BacktestEngine, EngineConfig
    from src.strategies.portfolio_v4 import TrendPullbackV5
    kw = dict(symbol="XAUUSDm", starting_balance=105.74, sizing_mode="fixed", fixed_lots=0.01)
    kw.update(cfg_kw)
    res = BacktestEngine(bars=bars, cost=SCENARIOS[scenario], config=EngineConfig(**kw)).run(
        [TrendPullbackV5()], start_ts=_ts(a), end_ts=_ts(b))
    rows = [(t.entry_time, t.exit_time, t.is_buy, round(t.entry_price, 5), round(t.exit_price, 5),
             t.lots, round(t.net_pl, 6), round(t.swap, 6), t.exit_reason) for t in res.trades]
    digest = hashlib.sha256(json.dumps(rows).encode()).hexdigest()
    return len(res.trades), round(sum(t.net_pl for t in res.trades), 6), digest


@needs_data
@pytest.mark.parametrize("scenario,window,n,net,digest", [
    # M1-walked, realistic costs
    ("realistic", ("2026-08-03", "2026-08-17"), 22, -13.297,
     "03ea22f4a44f6ac31b2e50ca50ca96da74032bfdbf5ec8dfdc5ea50badfde2a3"),
    ("observed", ("2026-08-03", "2026-08-17"), 22, -12.977,
     "3140077436037e3cbec253ee134625ef5fe8bdec9a859898b0b5becdc8563ac5"),
])
def test_gold_engine_regression_m1(xau_bars, scenario, window, n, net, digest):
    assert _run(xau_bars, scenario, *window) == (n, net, digest)


@needs_data
def test_gold_engine_regression_coarse_no_m1(xau_bars):
    # Before M1 history begins (2026-07-02): the coarse-bar path.
    got = _run(xau_bars, "realistic", "2026-05-04", "2026-05-18")
    assert got[0] == 24 and got[1] == -40.259
    assert got[2].startswith("f5a709feadc4496a")


@needs_data
def test_engine_defaults_and_gold_flags_unchanged(xau_bars):
    from src.backtesting.engine import BacktestEngine, EngineConfig
    cfg = EngineConfig()
    assert (cfg.symbol, cfg.leverage, cfg.spread_gate_points) == ("XAUUSDm", 200.0, 350.0)
    assert cfg.weekend_trading is False and cfg.strict_instrument is False
    eng = BacktestEngine(bars=xau_bars, cost=SCENARIOS["realistic"], config=cfg)
    assert eng.diag["cost_symbol_mismatch"] is None
    assert eng._spread_gate == 350.0
    # gold margin: 100 oz * 4428 * 0.01 / 200
    assert eng.margin_required(0.01, 4428.0) == pytest.approx(22.14)
    # gold P&L per $ per lot is the untouched spec snapshot
    assert eng._value_per_price(0.01, 4428.0) == xau_bars.spec.value_per_price_unit_per_lot * 0.01


@needs_data
def test_cost_symbol_mismatch_is_loud_and_overridable(xau_bars):
    from src.backtesting.engine import BacktestEngine, EngineConfig
    eur_bars = replace(xau_bars, spec=replace(xau_bars.spec, symbol="EURUSDm"))
    eng = BacktestEngine(bars=eur_bars, cost=SCENARIOS["realistic"], config=EngineConfig())
    assert eng.diag["cost_symbol_mismatch"]
    with pytest.raises(ValueError):
        BacktestEngine(bars=eur_bars, cost=SCENARIOS["realistic"],
                       config=EngineConfig(strict_instrument=True))
    with pytest.raises(ValueError):                # untagged gold defaults on EURUSD
        BacktestEngine(bars=eur_bars, cost=CostModel(),
                       config=EngineConfig(strict_instrument=True))
    ok = BacktestEngine(bars=eur_bars, cost=cost_model_for("EURUSDm", "realistic"),
                        config=EngineConfig(strict_instrument=True))
    assert ok.diag["cost_symbol_mismatch"] is None
    assert ok._spread_gate == 40.0                 # registry gate, not gold's 350
    # an explicit caller-supplied gate is honoured
    keep = BacktestEngine(bars=eur_bars, cost=cost_model_for("EURUSDm", "realistic"),
                          config=EngineConfig(spread_gate_points=123.0))
    assert keep._spread_gate == 123.0


@needs_data
def test_weekend_trading_flag(xau_bars):
    from src.backtesting.engine import BacktestEngine, EngineConfig
    from src.core.market_hours import IST as IST_TZ
    sat_noon = datetime(2026, 8, 8, 12, 0, tzinfo=IST_TZ)       # Saturday
    fri_late = datetime(2026, 8, 7, 22, 0, tzinfo=IST_TZ)       # Friday after cutoff
    sat_night = datetime(2026, 8, 8, 2, 0, tzinfo=IST_TZ)       # outside 06:00-21:30 IST
    gold = BacktestEngine(bars=xau_bars, cost=SCENARIOS["realistic"], config=EngineConfig())
    assert gold._allow_new_entry(sat_noon)[0] is False
    assert gold._allow_new_entry(fri_late)[0] is False

    btc_bars = replace(xau_bars, spec=replace(xau_bars.spec, symbol="BTCUSDm"))
    cm = cost_model_for("BTCUSDm", "observed")
    crypto = BacktestEngine(bars=btc_bars, cost=cm, config=EngineConfig(weekend_trading=True))
    assert crypto._allow_new_entry(sat_noon)[0] is True
    assert crypto._allow_new_entry(fri_late)[0] is False        # window still applies
    assert crypto._allow_new_entry(sat_night)[0] is False
    around = BacktestEngine(bars=btc_bars, cost=cm, config=EngineConfig(
        weekend_trading=True, enforce_trading_window=False))
    assert around._allow_new_entry(sat_night)[0] is True


@needs_data
def test_usdjpy_margin_and_pnl_conversion(xau_bars):
    from src.backtesting.engine import BacktestEngine, EngineConfig
    jpy_spec = replace(xau_bars.spec, symbol="USDJPYm", contract_size=100000.0,
                       trade_tick_size=0.001, trade_tick_value=0.667)    # snapshot at ~150
    bars = replace(xau_bars, spec=jpy_spec)
    eng = BacktestEngine(bars=bars, cost=cost_model_for("USDJPYm", "observed"),
                         config=EngineConfig(leverage=200.0))
    # USD-base: 0.01 lot = $1000 notional -> $5 margin at 1:200, independent of price
    assert eng.margin_required(0.01, 150.0) == pytest.approx(5.0)
    assert eng.margin_required(0.01, 110.0) == pytest.approx(5.0)
    # P&L converts at the exit price, not the fetch-time tick_value
    assert eng._value_per_price(1.0, 150.0) == pytest.approx(100000 / 150.0)
    assert eng._value_per_price(1.0, 110.0) == pytest.approx(100000 / 110.0)
    off = BacktestEngine(bars=bars, cost=cost_model_for("USDJPYm", "observed"),
                         config=EngineConfig(dynamic_quote_conversion=False))
    assert off._value_per_price(1.0, 110.0) == pytest.approx(0.667 / 0.001)


@needs_data
def test_xxxusd_margin_formula(xau_bars):
    from src.backtesting.engine import BacktestEngine, EngineConfig
    for sym, contract, price, lots, expect in (("EURUSDm", 100000.0, 1.10, 0.01, 5.5),
                                               ("BTCUSDm", 1.0, 100000.0, 0.01, 5.0)):
        bars = replace(xau_bars, spec=replace(xau_bars.spec, symbol=sym, contract_size=contract))
        eng = BacktestEngine(bars=bars, cost=cost_model_for(sym, "observed"),
                             config=EngineConfig(leverage=200.0))
        assert eng.margin_required(lots, price) == pytest.approx(expect)

"""Portfolio risk layer: sizing per asset, exposure maths, fail-closed behaviour,
kill-switch thresholds. Deterministic, no network, no MT5."""
import math
import random
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from src.instruments import get_meta, risk_lots
from src.portfolio import (AccountSnapshot, Decision, OrderProposal, PortfolioLimits,
                           PortfolioRiskEngine, Position, groups_for, kill_switch_state)
from src.portfolio.risk import RiskInputError, notional_usd, sl_risk_usd

NOW = datetime(2026, 10, 16, 12, 0, 0, tzinfo=timezone.utc)
PRICES = {"XAUUSDm": 2000.0, "EURUSDm": 1.10, "GBPUSDm": 1.30, "USDJPYm": 150.0,
          "BTCUSDm": 60000.0, "ETHUSDm": 3000.0}
SPREADS = {"XAUUSDm": 240.0, "EURUSDm": 8.0, "GBPUSDm": 10.0, "USDJPYm": 10.0,
           "BTCUSDm": 640.0, "ETHUSDm": 50.0}
# relaxed so a single concern can be isolated
WIDE = dict(max_net_usd_exposure_x_equity=1000.0, max_gross_notional_x_equity=1000.0,
            max_margin_utilisation_pct=1000.0)

ENG = PortfolioRiskEngine()


def acct(equity=100_000.0, **kw):
    base = dict(equity=equity, balance=equity, free_margin=equity * 0.9 if isinstance(equity, float) else 0.0, margin_used=0.0,
                timestamp_utc=NOW - timedelta(seconds=5),
                price_ts={s: NOW - timedelta(seconds=10) for s in PRICES},
                prices=dict(PRICES), spread_points=dict(SPREADS))
    base.update(kw)
    return AccountSnapshot(**base)


def prop(symbol="EURUSDm", side="BUY", lots=1.0, entry=None, sl=None, strategy="t"):
    entry = PRICES[symbol] if entry is None else entry
    if sl is None:
        sl = entry - 0.0010 if symbol == "EURUSDm" and side == "BUY" else None
    return OrderProposal(symbol, side, lots, entry, sl, strategy)


def pos(symbol, side, lots, entry, sl, strategy="t"):
    return Position(symbol, side, lots, entry, sl, None, strategy)


def reasons_with(d: Decision, prefix: str):
    return [r for r in d.reasons if r.startswith(prefix)]


def check(proposal, positions=(), account=None, limits=None, **kw):
    return ENG.check(proposal, list(positions), account or acct(), NOW, limits, **kw)


# ---------------------------------------------------------------------------
# baseline + sizing per asset
# ---------------------------------------------------------------------------


def test_baseline_allows_clean_trade():
    d = check(prop())
    assert d.allow is True and d.reasons == []
    assert d.computed["proposal_risk_usd"] == pytest.approx(100.0)


@pytest.mark.parametrize("symbol,side,lots,entry,sl,expected", [
    ("XAUUSDm", "BUY", 0.5, 2000.0, 1996.0, 4.0 * 100 * 0.5),        # 100 oz
    ("EURUSDm", "SELL", 2.0, 1.10, 1.1015, 0.0015 * 100000 * 2.0),
    ("GBPUSDm", "BUY", 1.0, 1.30, 1.2980, 0.0020 * 100000),
    ("BTCUSDm", "BUY", 0.1, 60000.0, 59000.0, 1000.0 * 1.0 * 0.1),   # 1 coin contract
    ("ETHUSDm", "SELL", 1.0, 3000.0, 3100.0, 100.0 * 1.0 * 1.0),
])
def test_sl_risk_per_asset(symbol, side, lots, entry, sl, expected):
    assert sl_risk_usd(symbol, side, entry, sl, lots, PRICES[symbol]) == pytest.approx(expected)


def test_jpy_pnl_converted_at_current_price():
    # 1 lot, 0.5 yen stop: 0.5 * 100000 = 50 000 JPY; / 150 = 333.33 USD
    r = sl_risk_usd("USDJPYm", "BUY", 150.0, 149.5, 1.0, 150.0)
    assert r == pytest.approx(50_000 / 150.0)
    # a different current price changes the conversion
    assert sl_risk_usd("USDJPYm", "BUY", 150.0, 149.5, 1.0, 100.0) == pytest.approx(500.0)


def test_jpy_through_engine_matches_hand_number():
    d = check(OrderProposal("USDJPYm", "SELL", 0.3, 150.0, 150.4, "t"))
    assert d.computed["proposal_risk_usd"] == pytest.approx(0.4 * 100000 * 0.3 / 150.0)


@pytest.mark.parametrize("symbol,stop", [
    ("XAUUSDm", 5.0), ("EURUSDm", 0.0030), ("GBPUSDm", 0.0030), ("USDJPYm", 0.6),
    ("BTCUSDm", 900.0), ("ETHUSDm", 40.0),
])
def test_registry_risk_lots_agree_with_portfolio_risk(symbol, stop):
    meta = get_meta(symbol)
    price = PRICES[symbol]
    lots, actual, ok = risk_lots(100_000.0, 0.0030, stop, meta, price)
    assert ok
    r = sl_risk_usd(symbol, "BUY", price, price - stop, lots, price)
    assert r / 100_000.0 == pytest.approx(actual)
    assert r <= 100_000.0 * 0.0030 * (1 + 1e-9)


def test_notional_usd():
    assert notional_usd(get_meta("EURUSDm"), 1.0, 1.10) == pytest.approx(110_000)
    assert notional_usd(get_meta("USDJPYm"), 0.5, 150.0) == pytest.approx(50_000)
    assert notional_usd(get_meta("BTCUSDm"), 0.1, 60000.0) == pytest.approx(6_000)


# ---------------------------------------------------------------------------
# stop-loss validity
# ---------------------------------------------------------------------------


def test_missing_sl_denied():
    d = check(OrderProposal("EURUSDm", "BUY", 1.0, 1.10, None, "t"))
    assert not d.allow and reasons_with(d, "SL_MISSING")


def test_wrong_side_sl_buy_denied():
    d = check(OrderProposal("EURUSDm", "BUY", 1.0, 1.10, 1.1010, "t"))
    assert not d.allow and reasons_with(d, "SL_WRONG_SIDE")


def test_wrong_side_sl_sell_denied():
    d = check(OrderProposal("XAUUSDm", "SELL", 0.1, 2000.0, 1995.0, "t"))
    assert not d.allow and reasons_with(d, "SL_WRONG_SIDE")


def test_sl_equal_entry_denied():
    d = check(OrderProposal("EURUSDm", "BUY", 1.0, 1.10, 1.10, "t"))
    assert reasons_with(d, "SL_WRONG_SIDE")


def test_nan_sl_denied():
    d = check(OrderProposal("EURUSDm", "BUY", 1.0, 1.10, float("nan"), "t"))
    assert not d.allow and reasons_with(d, "SL_MISSING")


def test_existing_position_without_sl_denies_new_entry():
    d = check(prop(), [pos("GBPUSDm", "BUY", 0.1, 1.30, None)])
    assert not d.allow and reasons_with(d, "INVALID_POSITION")


def test_existing_position_trailed_past_entry_has_zero_risk():
    p = pos("EURUSDm", "BUY", 1.0, 1.10, 1.1050)       # SL above entry = locked profit
    assert ENG.position_risk_usd(p, PRICES) == 0.0
    assert check(prop(), [p]).allow


# ---------------------------------------------------------------------------
# fail closed: unknown symbol, prices, staleness, NaN, exceptions
# ---------------------------------------------------------------------------


def test_unknown_symbol_denied():
    d = check(OrderProposal("DOGEUSDm", "BUY", 1.0, 1.0, 0.9, "t"))
    assert not d.allow and reasons_with(d, "UNKNOWN_SYMBOL")


def test_unknown_symbol_in_open_positions_denied():
    d = check(prop(), [pos("DOGEUSDm", "BUY", 1.0, 1.0, 0.9)])
    assert not d.allow and any("DOGEUSDm" in r for r in d.reasons)


def test_missing_price_denied():
    a = acct()
    del a.prices["EURUSDm"]
    d = check(prop(), account=a)
    assert not d.allow and reasons_with(d, "NO_PRICE")


def test_nan_price_denied():
    a = acct()
    a.prices["EURUSDm"] = float("nan")
    d = check(prop(), account=a)
    assert not d.allow and reasons_with(d, "NO_PRICE")


def test_missing_price_for_open_position_symbol_denied():
    a = acct()
    del a.prices["GBPUSDm"]
    d = check(prop(), [pos("GBPUSDm", "BUY", 0.1, 1.30, 1.29)], account=a)
    assert not d.allow


def test_stale_price_denied():
    a = acct()
    a.price_ts["EURUSDm"] = NOW - timedelta(seconds=121)
    d = check(prop(), account=a)
    assert not d.allow and reasons_with(d, "STALE_PRICE")


def test_price_age_boundary_exact_limit_allowed():
    a = acct()
    a.price_ts["EURUSDm"] = NOW - timedelta(seconds=120)
    assert check(prop(), account=a).allow


def test_missing_price_timestamp_denied():
    a = acct()
    del a.price_ts["EURUSDm"]
    d = check(prop(), account=a)
    assert not d.allow and reasons_with(d, "STALE_PRICE")


def test_stale_price_of_open_position_symbol_denied():
    a = acct()
    a.price_ts["XAUUSDm"] = NOW - timedelta(minutes=10)
    d = check(prop(), [pos("XAUUSDm", "BUY", 0.1, 2000.0, 1990.0)], account=a)
    assert not d.allow and any("XAUUSDm" in r for r in reasons_with(d, "STALE_PRICE"))


def test_future_price_timestamp_denied():
    a = acct()
    a.price_ts["EURUSDm"] = NOW + timedelta(minutes=5)
    assert not check(prop(), account=a).allow


def test_stale_account_denied():
    a = acct(timestamp_utc=NOW - timedelta(seconds=61))
    d = check(prop(), account=a)
    assert not d.allow and reasons_with(d, "STALE_ACCOUNT")


def test_missing_account_timestamp_denied():
    d = check(prop(), account=acct(timestamp_utc=None))
    assert not d.allow


def test_naive_now_denied():
    d = ENG.check(prop(), [], acct(), datetime(2026, 10, 16, 12, 0, 0))
    assert not d.allow and reasons_with(d, "INVALID_INPUT")


@pytest.mark.parametrize("field_name", ["equity", "balance", "free_margin", "margin_used"])
def test_nan_account_field_denied(field_name):
    a = acct()
    setattr(a, field_name, float("nan"))
    d = check(prop(), account=a)
    assert not d.allow and reasons_with(d, "INVALID_ACCOUNT")


def test_none_equity_and_zero_equity_denied():
    assert not check(prop(), account=acct(equity=None)).allow
    assert not check(prop(), account=acct(equity=0.0)).allow


def test_exception_inside_check_is_fail_closed(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("kaboom")
    monkeypatch.setattr(PortfolioRiskEngine, "exposure_report", boom)
    d = check(prop())
    assert not d.allow and reasons_with(d, "CHECK_ERROR[exposure]")


def test_exception_outside_checks_is_fail_closed(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("kaboom")
    monkeypatch.setattr(PortfolioRiskEngine, "_check", boom)
    d = check(prop())
    assert d.allow is False and reasons_with(d, "ENGINE_ERROR")


def test_garbage_inputs_never_raise():
    d = ENG.check(None, None, None, None, None)
    assert isinstance(d, Decision) and d.allow is False
    d = ENG.check(prop(), [object()], acct(), NOW)
    assert d.allow is False


def test_invalid_limits_denied():
    d = check(prop(), limits=PortfolioLimits(max_risk_per_trade_pct=float("nan")))
    assert not d.allow and reasons_with(d, "INVALID_LIMITS")


# ---------------------------------------------------------------------------
# budget caps
# ---------------------------------------------------------------------------


def test_per_trade_cap():
    # XAU 1 lot, $5 stop => $500 = 0.5 % > 0.35 %
    d = check(OrderProposal("XAUUSDm", "BUY", 1.0, 2000.0, 1995.0, "t"),
              limits=PortfolioLimits(**WIDE))
    assert not d.allow and reasons_with(d, "RISK_PER_TRADE")
    assert d.computed["risk_per_trade_pct"] == pytest.approx(0.5)


def test_per_trade_cap_boundary_inclusive():
    # EUR 1 lot, 0.0035 stop = $350 = exactly 0.35 %
    d = check(OrderProposal("EURUSDm", "BUY", 1.0, 1.10, 1.10 - 0.0035, "t"))
    assert not reasons_with(d, "RISK_PER_TRADE")


def test_open_risk_cap_with_existing_positions():
    existing = [pos("EURUSDm", "SELL", 1.0, 1.10, 1.103),     # 300
                pos("GBPUSDm", "SELL", 1.0, 1.30, 1.303),     # 300
                pos("XAUUSDm", "SELL", 0.5, 2000.0, 2006.0)]  # 300
    p = OrderProposal("BTCUSDm", "SELL", 0.1, 60000.0, 61500.0, "t")   # 150
    d = check(p, existing)
    assert d.computed["open_risk_usd_existing"] == pytest.approx(900.0)
    assert d.computed["open_risk_usd_total"] == pytest.approx(1050.0)
    assert not d.allow
    assert [r.split(":")[0] for r in d.reasons] == ["OPEN_RISK"]


def test_open_risk_just_under_cap_allowed():
    existing = [pos("EURUSDm", "SELL", 1.0, 1.10, 1.103),
                pos("GBPUSDm", "SELL", 1.0, 1.30, 1.303),
                pos("XAUUSDm", "SELL", 0.5, 2000.0, 2006.0)]
    p = OrderProposal("BTCUSDm", "SELL", 0.1, 60000.0, 61000.0, "t")   # 100 -> 1.0 % exact
    d = check(p, existing)
    assert d.allow, d.reasons


def test_max_positions():
    existing = [pos("EURUSDm", "SELL", 0.1, 1.10, 1.101), pos("GBPUSDm", "SELL", 0.1, 1.30, 1.301),
                pos("XAUUSDm", "SELL", 0.1, 2000.0, 2001.0), pos("BTCUSDm", "SELL", 0.1, 60000.0, 60100.0)]
    d = check(prop(), existing)
    assert not d.allow and reasons_with(d, "MAX_POSITIONS")


def test_per_instrument_cap():
    existing = [pos("EURUSDm", "BUY", 1.0, 1.10, 1.0970)]     # 300 = 0.3 %
    d = check(OrderProposal("EURUSDm", "BUY", 1.0, 1.10, 1.0990, "t"), existing,
              limits=PortfolioLimits(max_group_risk_pct=10.0))   # +100 => 0.4 % ok
    assert d.allow, d.reasons
    d = check(OrderProposal("EURUSDm", "BUY", 1.0, 1.10, 1.0970, "t"), existing,
              limits=PortfolioLimits(max_group_risk_pct=10.0, max_risk_per_instrument_pct=0.5))
    assert reasons_with(d, "INSTRUMENT_RISK") and not d.allow


def test_correlated_group_cap_usd_short():
    existing = [pos("EURUSDm", "BUY", 1.0, 1.10, 1.097),      # 300
                pos("GBPUSDm", "BUY", 1.0, 1.30, 1.297)]      # 300
    p = OrderProposal("XAUUSDm", "BUY", 0.5, 2000.0, 1996.0, "t")   # 200 -> 800 > 700
    d = check(p, existing)
    assert not d.allow
    g = reasons_with(d, "GROUP_RISK")
    assert g and "usd_short" in g[0] and "risk_on" not in g[0]
    assert d.computed["group_risk_pct"]["usd_short"] == pytest.approx(0.8)
    assert d.computed["group_risk_pct"]["risk_on"] == pytest.approx(0.2)
    assert d.computed["open_risk_pct_total"] < 1.0       # only the group cap trips


def test_group_cap_not_applied_to_opposite_direction():
    existing = [pos("EURUSDm", "BUY", 1.0, 1.10, 1.097), pos("GBPUSDm", "BUY", 1.0, 1.30, 1.297)]
    # short XAU is not usd_short and not risk_on
    d = check(OrderProposal("XAUUSDm", "SELL", 0.5, 2000.0, 2004.0, "t"), existing)
    assert not reasons_with(d, "GROUP_RISK")


def test_risk_on_group_cap():
    existing = [pos("XAUUSDm", "BUY", 0.5, 2000.0, 1994.0),          # 300
                pos("BTCUSDm", "BUY", 0.1, 60000.0, 57000.0)]        # 300
    p = OrderProposal("ETHUSDm", "BUY", 1.0, 3000.0, 2900.0, "t")    # 100 -> 700 + .. (exact cap)
    assert not reasons_with(check(p, existing), "GROUP_RISK")
    p2 = OrderProposal("ETHUSDm", "BUY", 1.0, 3000.0, 2890.0, "t")   # 110 -> 710 > 700
    d = check(p2, existing)
    assert reasons_with(d, "GROUP_RISK") and "risk_on" in reasons_with(d, "GROUP_RISK")[0]


def test_groups_for_membership():
    m = get_meta
    assert groups_for(m("EURUSDm"), "BUY") == ["usd_short"]
    assert groups_for(m("EURUSDm"), "SELL") == []
    assert groups_for(m("USDJPYm"), "SELL") == ["usd_short"]
    assert groups_for(m("USDJPYm"), "BUY") == []
    assert groups_for(m("XAUUSDm"), "BUY") == ["usd_short", "risk_on"]
    assert groups_for(m("BTCUSDm"), "BUY") == ["usd_short", "risk_on"]
    assert groups_for(m("ETHUSDm"), "SELL") == []


# ---------------------------------------------------------------------------
# exposure aggregation (numbers by hand)
# ---------------------------------------------------------------------------


def test_exposure_report_hand_numbers():
    positions = [pos("EURUSDm", "BUY", 1.0, 1.10, 1.09),       # +110000 EUR, -110000 USD
                 pos("XAUUSDm", "BUY", 0.5, 2000.0, 1990.0),   # +100000 XAU, -100000 USD
                 pos("USDJPYm", "SELL", 0.5, 150.0, 151.0)]    # -50000 USD, +50000 JPY
    r = ENG.exposure_report(positions, PRICES)
    c = r["per_currency_net_usd"]
    assert c["EUR"] == pytest.approx(110_000)
    assert c["XAU"] == pytest.approx(100_000)
    assert c["JPY"] == pytest.approx(50_000)
    assert c["USD"] == pytest.approx(-260_000)
    assert r["net_usd_exposure"] == pytest.approx(-260_000)
    assert r["gross_notional"] == pytest.approx(260_000)
    # usd_short: all three (long EUR, long XAU, short USDJPY); risk_on: XAU only
    assert r["groups"]["usd_short"]["positions"] == 3
    assert r["groups"]["usd_short"]["notional_usd"] == pytest.approx(260_000)
    assert r["groups"]["risk_on"]["positions"] == 1
    assert r["groups"]["risk_on"]["notional_usd"] == pytest.approx(100_000)


def test_exposure_report_crypto_and_netting():
    positions = [pos("BTCUSDm", "BUY", 0.1, 60000.0, 59000.0),    # +6000 BTC, -6000 USD
                 pos("ETHUSDm", "BUY", 1.0, 3000.0, 2900.0),       # +3000 ETH, -3000 USD
                 pos("EURUSDm", "SELL", 0.1, 1.10, 1.11)]          # -11000 EUR, +11000 USD
    r = ENG.exposure_report(positions, PRICES)
    assert r["per_currency_net_usd"]["BTC"] == pytest.approx(6000)
    assert r["per_currency_net_usd"]["ETH"] == pytest.approx(3000)
    assert r["per_currency_net_usd"]["EUR"] == pytest.approx(-11000)
    assert r["net_usd_exposure"] == pytest.approx(-6000 - 3000 + 11000)
    assert r["gross_notional"] == pytest.approx(20_000)


def test_exposure_report_unknown_symbol_and_missing_price_raise():
    with pytest.raises(RiskInputError):
        ENG.exposure_report([pos("FOOm", "BUY", 1, 1, 0.5)], PRICES)
    with pytest.raises(RiskInputError):
        ENG.exposure_report([pos("EURUSDm", "BUY", 1, 1.1, 1.0)], {})


def test_net_usd_exposure_cap_denies():
    # equity 10000; 1 lot EUR = 110000 notional = 11x equity > 5x
    a = acct(equity=10_000.0)
    d = check(OrderProposal("EURUSDm", "BUY", 1.0, 1.10, 1.0997, "t"), account=a,
              limits=PortfolioLimits(max_margin_utilisation_pct=1000.0))
    assert reasons_with(d, "NET_USD_EXPOSURE") and reasons_with(d, "GROSS_NOTIONAL")
    assert d.computed["net_usd_exposure_x_equity"] == pytest.approx(-11.0)


def test_net_exposure_hedge_nets_out():
    # long EUR + short GBP cancel on the USD leg partially: -110000 + 130000 = +20000
    existing = [pos("EURUSDm", "BUY", 1.0, 1.10, 1.097)]
    p = OrderProposal("GBPUSDm", "SELL", 1.0, 1.30, 1.303, "t")
    d = check(p, existing)
    assert d.computed["net_usd_exposure"] == pytest.approx(20_000)
    assert d.computed["gross_notional"] == pytest.approx(240_000)


def test_gross_cap_denies_while_net_ok():
    # 9 lots long EUR + 9 lots short GBP style: net small, gross big
    a = acct(equity=20_000.0)
    existing = [pos("EURUSDm", "BUY", 1.0, 1.10, 1.0999)]           # 110k
    p = OrderProposal("GBPUSDm", "SELL", 0.85, 1.30, 1.3001, "t")    # 110.5k => gross 220.5k = 11x
    d = check(p, existing, account=a, limits=PortfolioLimits(max_margin_utilisation_pct=1000.0))
    assert reasons_with(d, "GROSS_NOTIONAL")
    assert not reasons_with(d, "NET_USD_EXPOSURE")


# ---------------------------------------------------------------------------
# margin, spread, volume
# ---------------------------------------------------------------------------


def test_margin_cap():
    a = acct(equity=10_000.0, margin_used=4_800.0, free_margin=5_200.0)
    p = OrderProposal("EURUSDm", "BUY", 1.0, 1.10, 1.0997, "t")      # need 110000/200 = 550
    d = check(p, account=a, limits=PortfolioLimits(max_net_usd_exposure_x_equity=100,
                                                   max_gross_notional_x_equity=100))
    assert d.computed["margin_required"] == pytest.approx(550.0)
    assert d.computed["margin_utilisation_pct"] == pytest.approx(53.5)
    assert reasons_with(d, "MARGIN") and not d.allow


def test_margin_exceeds_free_margin():
    a = acct(equity=10_000.0, margin_used=0.0, free_margin=100.0)
    p = OrderProposal("EURUSDm", "BUY", 1.0, 1.10, 1.0997, "t")
    d = check(p, account=a, limits=PortfolioLimits(max_net_usd_exposure_x_equity=100,
                                                   max_gross_notional_x_equity=100))
    assert reasons_with(d, "MARGIN") and "free_margin" in reasons_with(d, "MARGIN")[0]


def test_margin_within_cap_allowed():
    a = acct(equity=100_000.0, margin_used=10_000.0)
    assert check(prop(), account=a).allow


def test_spread_too_wide_denied():
    a = acct()
    a.spread_points["EURUSDm"] = 41.0                 # registry gate is 40
    d = check(prop(), account=a)
    assert reasons_with(d, "SPREAD") and not d.allow


def test_spread_override_and_missing():
    a = acct()
    a.spread_points["EURUSDm"] = 41.0
    assert check(prop(), account=a, limits=PortfolioLimits(max_spread_points={"EURUSDm": 50.0})).allow
    del a.spread_points["EURUSDm"]
    assert reasons_with(check(prop(), account=a), "SPREAD")


def test_eth_has_no_registry_spread_gate_so_denied_until_configured():
    p = OrderProposal("ETHUSDm", "BUY", 0.1, 3000.0, 2990.0, "t")     # $1 risk
    d = check(p)
    assert reasons_with(d, "SPREAD") and "no spread limit" in reasons_with(d, "SPREAD")[0]
    assert check(p, limits=PortfolioLimits(max_spread_points={"ETHUSDm": 200.0})).allow


def test_lots_validation():
    assert reasons_with(check(prop(lots=0.0)), "INVALID_LOTS")
    assert reasons_with(check(prop(lots=-1.0)), "INVALID_LOTS")
    assert reasons_with(check(prop(lots=float("nan"))), "INVALID_LOTS")
    assert reasons_with(check(prop(lots=0.005)), "INVALID_LOTS")          # below min
    assert reasons_with(check(prop(lots=0.015)), "INVALID_LOTS")          # off-step
    eth = OrderProposal("ETHUSDm", "BUY", 0.05, 3000.0, 2990.0, "t")      # registry min is 0.1
    assert reasons_with(check(eth), "INVALID_LOTS")


def test_invalid_side_denied():
    d = check(OrderProposal("EURUSDm", "LONG", 1.0, 1.10, 1.09, "t"))
    assert reasons_with(d, "INVALID_SIDE")


# ---------------------------------------------------------------------------
# all reasons are returned
# ---------------------------------------------------------------------------


def test_all_failing_reasons_returned_not_just_first():
    a = acct(equity=10_000.0, margin_used=6_000.0, free_margin=100.0,
             timestamp_utc=NOW - timedelta(minutes=5))
    a.price_ts["EURUSDm"] = NOW - timedelta(minutes=5)
    a.spread_points["EURUSDm"] = 500.0
    p = OrderProposal("EURUSDm", "BUY", 1.0, 1.10, 1.0900, "t")      # $1000 = 10 % of equity
    d = check(p, [pos("XAUUSDm", "BUY", 1.0, 2000.0, 1900.0)], account=a)   # +$10000 risk
    kinds = {r.split(":")[0].split("[")[0] for r in d.reasons}
    for k in ("STALE_ACCOUNT", "STALE_PRICE", "RISK_PER_TRADE", "OPEN_RISK",
              "NET_USD_EXPOSURE", "GROSS_NOTIONAL",
              "MARGIN", "SPREAD", "GROUP_RISK"):
        assert k in kinds, (k, d.reasons)
    assert not d.allow and len(d.reasons) >= 8


# ---------------------------------------------------------------------------
# kill switch
# ---------------------------------------------------------------------------


def ks(equity, peak=100_000.0, day_start=None, limits=None):
    return kill_switch_state(acct(equity=equity), peak,
                             equity if day_start is None else day_start, limits)


def test_kill_switch_ok():
    assert ks(100_000.0) == "OK"
    assert ks(120_000.0, peak=100_000.0) == "OK"           # above peak


@pytest.mark.parametrize("equity,expected", [
    (94_001.0, "OK"),            # dd 5.999 % < soft 6 %
    (94_000.0, "SOFT_STOP"),     # exactly 6 % (60 % of 10 %)
    (92_001.0, "SOFT_STOP"),     # 7.999 %
    (92_000.0, "HARD_FLATTEN"),  # exactly 8 % (80 % of 10 %)
    (50_000.0, "HARD_FLATTEN"),
])
def test_kill_switch_trailing_drawdown_thresholds(equity, expected):
    assert ks(equity) == expected


@pytest.mark.parametrize("equity,expected", [
    (97_001.0, "OK"),            # daily loss 2.999 % < 3 %
    (97_000.0, "SOFT_STOP"),     # exactly 3 % (60 % of 5 %)
    (96_001.0, "SOFT_STOP"),
    (96_000.0, "HARD_FLATTEN"),  # exactly 4 % (80 % of 5 %)
])
def test_kill_switch_daily_loss_thresholds(equity, expected):
    # peak == day start so the drawdown metric equals the daily metric but is
    # judged against the looser 10 % limit; the daily limit is what triggers.
    assert kill_switch_state(acct(equity=equity), 100_000.0, 100_000.0) == expected


def test_kill_switch_hard_overrides_soft():
    # drawdown only soft (6.5 %), daily loss hard (4.5 %)
    state = kill_switch_state(acct(equity=95_500.0), 102_000.0, 100_000.0)
    assert state == "HARD_FLATTEN"
    # and the reverse combination
    assert kill_switch_state(acct(equity=91_000.0), 100_000.0, 91_500.0) == "HARD_FLATTEN"


def test_kill_switch_custom_limits():
    lim = PortfolioLimits(trailing_dd_pct=4.0, daily_loss_pct=2.0, soft_fraction=0.5,
                          hard_fraction=0.75)
    assert kill_switch_state(acct(equity=98_800.0), 100_000.0, 100_000.0, lim) == "SOFT_STOP"
    assert kill_switch_state(acct(equity=98_400.0), 100_000.0, 100_000.0, lim) == "HARD_FLATTEN"


@pytest.mark.parametrize("equity,peak,day", [
    (float("nan"), 100_000.0, 100_000.0), (None, 100_000.0, 100_000.0),
    (90_000.0, float("nan"), 100_000.0), (90_000.0, 100_000.0, None),
    (0.0, 100_000.0, 100_000.0), (90_000.0, 0.0, 100_000.0),
])
def test_kill_switch_fail_closed_on_bad_inputs(equity, peak, day):
    assert kill_switch_state(acct(equity=equity), peak, day) == "SOFT_STOP"


def test_check_denies_when_kill_switch_active():
    a = acct(equity=96_000.0)
    d = ENG.check(prop(), [], a, NOW, None, peak_equity=100_000.0, day_start_equity=100_000.0)
    assert not d.allow and reasons_with(d, "KILL_SWITCH")
    assert d.computed["kill_switch"] == "HARD_FLATTEN"
    ok = ENG.check(prop(), [], acct(), NOW, None, peak_equity=100_000.0, day_start_equity=100_000.0)
    assert ok.allow and ok.computed["kill_switch"] == "OK"


# ---------------------------------------------------------------------------
# property: adding a position can never reduce computed open risk
# ---------------------------------------------------------------------------


def _random_position(rng):
    sym = rng.choice(sorted(PRICES))
    side = rng.choice(["BUY", "SELL"])
    px = PRICES[sym]
    dist = px * rng.uniform(-0.01, 0.02)          # may be on the profit side (trailed)
    sl = px - dist if side == "BUY" else px + dist
    return Position(sym, side, round(rng.choice([0.01, 0.05, 0.1, 0.5, 1.0]), 2), px, sl, None, "p")


def test_adding_position_never_reduces_open_risk():
    rng = random.Random(1234)
    for _ in range(300):
        book = [_random_position(rng) for _ in range(rng.randint(0, 5))]
        extra = _random_position(rng)
        before = ENG.open_risk_usd(book, PRICES)
        after = ENG.open_risk_usd(book + [extra], PRICES)
        assert after >= before - 1e-12
        assert before >= 0.0 and math.isfinite(after)


def test_adding_proposal_never_reduces_total_open_risk_in_check():
    rng = random.Random(99)
    limits = PortfolioLimits(**WIDE, max_positions=50)
    for _ in range(100):
        book = [_random_position(rng) for _ in range(rng.randint(0, 3))]
        sym = rng.choice(sorted(PRICES))
        px = PRICES[sym]
        p = OrderProposal(sym, "BUY", 0.01 if sym != "ETHUSDm" else 0.1, px, px * 0.995, "t")
        d = ENG.check(p, book, acct(), NOW, limits)
        if "open_risk_usd_total" in d.computed:
            assert d.computed["open_risk_usd_total"] >= d.computed["open_risk_usd_existing"]

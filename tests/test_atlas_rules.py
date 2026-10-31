"""Deterministic tests for the Atlas Funded 'Access' rules encoding (src/atlas).

Base account: 10_000 initial. Funded limits: trailing DD 6% = 600, daily 3% = 300.
Evaluation limits: trailing DD 10% = 1000, daily 5% = 500. Safety buffer 60%,
hard flatten 80%.
"""
import json
import math
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from src.atlas import rules as R
from src.atlas.rules import (AccountInfo, AtlasRuleEngine, AtlasState, RulesError,
                             Thresholds, evaluation_progress, load_rules, min_hold_ok,
                             payout_eligibility)

UTC = timezone.utc
CFG = R.DEFAULT_RULES_PATH
ACK = ["ea_approval_required"]
WED = datetime(2026, 10, 14, 12, 0, 0, tzinfo=UTC)
FRI = datetime(2026, 10, 16, 12, 0, 0, tzinfo=UTC)
INIT = 10_000.0


@pytest.fixture(scope="module")
def rules():
    return load_rules(CFG, allow_unverified=ACK)


@pytest.fixture()
def eng(rules):
    return AtlasRuleEngine(rules)


def acct(equity=INIT, balance=None, margin=0.0, free=None, ts=WED, risk=None, floating=None):
    balance = equity if balance is None else balance
    free = (equity - margin) if free is None else free
    return AccountInfo(balance=balance, equity=equity, margin=margin, free_margin=free,
                       ts_utc=ts, floating_pnl=floating, open_risk_by_symbol=risk or {})


def order(stop=1.0, margin=100.0, symbol="XAUUSD"):
    return R.OrderRequest(symbol=symbol, stop_risk_usd=stop, margin_required=margin)


def state(phase="funded", peak=INIT, ref=INIT, day=WED.date(), **kw):
    return AtlasState(initial_balance=INIT, peak_equity=peak, day_ref_equity=ref,
                      day_ref_date_utc=day, phase=phase, day_high_equity=kw.pop("high", ref),
                      day_start_balance=kw.pop("start", INIT), **kw)


# ------------------------------------------------------------------ loader
def _mutate(tmp_path, fn):
    doc = json.loads(CFG.read_text(encoding="utf-8"))
    fn(doc)
    p = tmp_path / "rules.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    return p


def _conflict_cfg(tmp_path, *also_unverified):
    """The real file with ea_approval_required put back into 'conflict' (it was, until 2026-10-31)."""
    def fn(doc):
        doc["rules"]["ea_approval_required"]["status"] = "conflict"
        for name in also_unverified:
            doc["rules"][name]["status"] = "unverified"
    return _mutate(tmp_path, fn)


def test_real_rules_file_loads_without_any_acknowledgement():
    """Every rule needed for enforcement is verified (EA approval resolved 2026-10-31)."""
    assert load_rules(CFG).status("ea_approval_required") == "verified-official"


def test_default_load_refuses_unverified_and_conflict(tmp_path):
    with pytest.raises(RulesError) as e:
        load_rules(_conflict_cfg(tmp_path))
    msg = str(e.value)
    assert "ea_approval_required" in msg


def test_load_with_explicit_ack_succeeds(tmp_path):
    r = load_rules(_conflict_cfg(tmp_path), allow_unverified=ACK)
    assert set(r.acknowledged) == set(ACK)
    assert r.status("ea_approval_required") == "conflict"
    assert r.status("daily_loss_eod_computation") == "verified-official"


def test_ack_only_one_still_refuses(tmp_path):
    with pytest.raises(RulesError, match="ea_approval_required"):
        load_rules(_conflict_cfg(tmp_path, "daily_loss_eod_computation"),
                   allow_unverified=["daily_loss_eod_computation"])


def test_allow_unverified_unknown_name_rejected():
    with pytest.raises(RulesError, match="not in rules file"):
        load_rules(CFG, allow_unverified=ACK + ["nonexistent_rule"])


def test_flipping_enforcement_rule_to_unverified_is_refused(tmp_path):
    p = _mutate(tmp_path, lambda d: d["rules"]["min_hold_seconds"].update(status="unverified"))
    with pytest.raises(RulesError, match="min_hold_seconds"):
        load_rules(p, allow_unverified=ACK)
    assert load_rules(p, allow_unverified=ACK + ["min_hold_seconds"])


def test_unverified_but_not_needed_rules_do_not_block(rules):
    for n in ("gold_symbol", "funded_fee_usd_by_size",
              "first_on_demand_payout_split"):
        assert rules.status(n) == "unverified"
        assert rules.rules[n]["needed_for_enforcement"] is False


def test_loader_rejects_nan_literal(tmp_path):
    txt = CFG.read_text(encoding="utf-8").replace('"evaluation": 0.10', '"evaluation": NaN')
    p = tmp_path / "nan.json"
    p.write_text(txt, encoding="utf-8")
    with pytest.raises(RulesError, match="non-finite"):
        load_rules(p, allow_unverified=ACK)


def test_loader_rejects_infinity_literal(tmp_path):
    txt = CFG.read_text(encoding="utf-8").replace('"funded": 0.06', '"funded": Infinity')
    p = tmp_path / "inf.json"
    p.write_text(txt, encoding="utf-8")
    with pytest.raises(RulesError):
        load_rules(p, allow_unverified=ACK)


@pytest.mark.parametrize("field", ["value", "source", "retrieved", "status",
                                   "needed_for_enforcement"])
def test_loader_rejects_missing_field(tmp_path, field):
    p = _mutate(tmp_path, lambda d: d["rules"]["news_window_minutes"].pop(field))
    with pytest.raises(RulesError, match=field):
        load_rules(p, allow_unverified=ACK)


def test_loader_rejects_bad_status_source_date(tmp_path):
    for fld, bad in (("status", "maybe"), ("source", "http://x"), ("retrieved", "16/10/2026")):
        p = _mutate(tmp_path, lambda d, f=fld, b=bad: d["rules"]["news_window_minutes"].update({f: b}))
        with pytest.raises(RulesError):
            load_rules(p, allow_unverified=ACK)


def test_loader_rejects_missing_required_rule_and_bad_values(tmp_path):
    p = _mutate(tmp_path, lambda d: d["rules"].pop("max_drawdown_pct"))
    with pytest.raises(RulesError, match="max_drawdown_pct"):
        load_rules(p, allow_unverified=ACK)
    p = _mutate(tmp_path, lambda d: d["rules"]["max_drawdown_pct"]["value"].update(funded=1.5))
    with pytest.raises(RulesError, match="funded"):
        load_rules(p, allow_unverified=ACK)
    p = _mutate(tmp_path, lambda d: d["rules"]["max_drawdown_pct"].update(value="10%"))
    with pytest.raises(RulesError):
        load_rules(p, allow_unverified=ACK)


def test_loader_rejects_garbage_and_missing_file(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    with pytest.raises(RulesError):
        load_rules(bad)
    with pytest.raises(RulesError):
        load_rules(tmp_path / "missing.json")


def test_json_records_provenance_for_every_rule():
    doc = json.loads(CFG.read_text(encoding="utf-8"))
    allowed = {"https://help.atlasfunded.com/access", "https://help.atlasfunded.com/max-drawdown",
               "https://help.atlasfunded.com/prohibited-practices",
               "https://help.atlasfunded.com/margin-usage",
               "https://help.atlasfunded.com/daily-loss", "https://help.atlasfunded.com/platforms",
               "https://atlasfunded.com/trading-rules", "https://atlasfunded.com/terms"}
    valid_dates = {"2026-10-16", "2026-10-26", "2026-10-31"}
    for name, rec in doc["rules"].items():
        assert rec["retrieved"] in valid_dates, name
        assert rec["source"] in allowed, name
        assert rec["status"] in ("verified-official", "conflict", "unverified"), name
        assert isinstance(rec["needed_for_enforcement"], bool), name


def test_official_values_in_json(rules):
    assert rules.phase_value("max_drawdown_pct", "evaluation") == 0.10
    assert rules.phase_value("max_drawdown_pct", "funded") == 0.06
    assert rules.phase_value("daily_loss_pct", "evaluation") == 0.05
    assert rules.phase_value("daily_loss_pct", "funded") == 0.03
    assert rules.phase_value("profit_target_pct", "evaluation") == 0.03
    assert rules.value("min_hold_seconds") == 180
    assert rules.value("news_window_minutes") == 5
    assert rules.value("margin_usage_close_pct") == 0.80
    assert rules.value("atlas_protector")["floating_loss_pct_of_initial"] == 0.02
    with pytest.raises(RulesError):
        rules.phase_value("max_drawdown_pct", "bogus")


def test_engine_construction_validates_buffer(rules):
    with pytest.raises(ValueError):
        AtlasRuleEngine(rules, safety_buffer=0.9)
    with pytest.raises(ValueError):
        AtlasRuleEngine(rules, safety_buffer=0.0)
    with pytest.raises(ValueError):
        AtlasRuleEngine(rules, safety_buffer=float("nan"))
    assert AtlasRuleEngine(rules, safety_buffer=0.8)
    with pytest.raises(ValueError):
        AtlasRuleEngine(rules, thresholds=Thresholds(margin_flatten=0.85))
    with pytest.raises(TypeError):
        AtlasRuleEngine({"not": "rules"})


def test_module_has_no_broker_import():
    src = Path(R.__file__).read_text(encoding="utf-8")
    assert not re.search(r"^\s*(import|from)\s+MetaTrader5", src, re.M)


# ------------------------------------------------------- phase thresholds
@pytest.mark.parametrize("phase,dd,daily", [("evaluation", 0.10, 0.05), ("funded", 0.06, 0.03)])
def test_limits_by_phase(eng, phase, dd, daily):
    assert eng.limits(phase) == {"max_drawdown_pct": dd, "daily_loss_pct": daily}


def test_unknown_phase_limits_raises(eng):
    with pytest.raises(ValueError):
        eng.limits("demo")


def test_evaluation_vs_funded_trailing_floor(eng):
    assert eng.trailing_floor(state("evaluation"), "evaluation") == pytest.approx(9000.0)
    assert eng.trailing_floor(state("funded"), "funded") == pytest.approx(9400.0)


def test_evaluation_vs_funded_daily_floor(eng):
    assert eng.daily_floor(state("evaluation"), "evaluation") == pytest.approx(9500.0)
    assert eng.daily_floor(state("funded"), "funded") == pytest.approx(9700.0)


def test_same_loss_different_phase_trailing_action(eng):
    # 600 below peak: funded = 100% of limit -> FLATTEN; evaluation = 60% -> STOP_NEW
    eq = 9400.0
    f = state("funded", peak=INIT, ref=eq)
    e = state("evaluation", peak=INIT, ref=eq)
    assert eng.monitor(acct(eq), f, WED) == "FLATTEN"
    assert eng.monitor(acct(eq), e, WED) == "STOP_NEW"


def test_same_loss_different_phase_daily_action(eng):
    # 300 below the day reference, trailing neutralised (peak == equity)
    eq = 9700.0
    f = state("funded", peak=eq, ref=INIT)
    e = state("evaluation", peak=eq, ref=INIT)
    assert eng.monitor(acct(eq), f, WED) == "FLATTEN"
    assert eng.monitor(acct(eq), e, WED) == "STOP_NEW"


# ---------------------------------------------------------- trailing floor
def test_trailing_floor_rises_with_unrealized_profit(eng):
    st = state()
    assert eng.trailing_floor(st, "funded") == pytest.approx(9400.0)
    assert eng.trailing_floor(st, "funded", equity=10250.0) == pytest.approx(9650.0)
    eng.update_state(acct(10250.0, balance=10000.0), st, WED)
    assert st.peak_equity == 10250.0
    assert eng.trailing_floor(st, "funded") == pytest.approx(9650.0)


def test_trailing_floor_never_falls(eng):
    st = state()
    eng.update_state(acct(10400.0), st, WED)
    floor_hi = eng.trailing_floor(st, "funded")
    for eq in (10300.0, 10100.0, 9900.0, 9500.0):
        eng.update_state(acct(eq), st, WED)
        assert eng.trailing_floor(st, "funded") == pytest.approx(floor_hi)
    assert st.peak_equity == 10400.0
    assert eng.trailing_floor(st, "funded", equity=9000.0) == pytest.approx(floor_hi)


def test_trailing_floor_rejects_nan_equity(eng):
    with pytest.raises(ValueError):
        eng.trailing_floor(state(), "funded", equity=float("nan"))


# --------------------------------------------------- order: buffer boundary
def test_order_ok_baseline(eng):
    d = eng.check_order(order(), acct(), state(), WED)
    assert d.allow and d.reasons == []
    assert d.computed["projected_equity"] == 9999.0


def test_trailing_buffer_exactly_60pct_denied(eng):
    st = state(peak=10400.0, ref=10050.0)           # trailing limit = 600
    # projected 10040 -> 360 below peak = 60.0% -> deny
    d = eng.check_order(order(stop=10.0), acct(10050.0), st, WED)
    assert not d.allow and any(r.startswith("trailing_dd_buffer") for r in d.reasons)
    # projected 10041 -> 59.83% -> allow
    d = eng.check_order(order(stop=9.0), acct(10050.0), st, WED)
    assert d.allow, d.reasons


def test_daily_buffer_exactly_60pct_denied(eng):
    st = state(peak=9830.0, ref=INIT)               # daily limit = 300; 60% = 180
    d = eng.check_order(order(stop=10.0), acct(9830.0), st, WED)   # projected 9820 -> 60.0%
    assert not d.allow and any(r.startswith("daily_loss_buffer") for r in d.reasons)
    d = eng.check_order(order(stop=9.0), acct(9830.0), st, WED)    # 59.7%
    assert d.allow, d.reasons


def test_stop_taking_projected_floor_breach_denied(eng):
    st = state(peak=9700.0, ref=INIT)               # equity already at daily floor
    d = eng.check_order(order(stop=1.0), acct(9700.0), st, WED)
    assert not d.allow and "projected_floor_breach" in d.reasons


def test_evaluation_allows_what_funded_denies(eng):
    st_f = state("funded", peak=9830.0, ref=INIT)
    st_e = state("evaluation", peak=9830.0, ref=INIT)
    assert not eng.check_order(order(stop=10.0), acct(9830.0), st_f, WED).allow
    assert eng.check_order(order(stop=10.0), acct(9830.0), st_e, WED).allow


def test_custom_safety_buffer_changes_boundary(rules):
    e50 = AtlasRuleEngine(rules, safety_buffer=0.5)
    st = state(peak=9830.0, ref=INIT)
    # projected 9840-... equity 9850, stop 0 -> daily_used 50% -> deny under 0.5 buffer
    assert not e50.check_order(order(stop=0.0), acct(9850.0), st, WED).allow
    assert AtlasRuleEngine(rules, 0.6).check_order(order(stop=0.0), acct(9850.0),
                                                   state(peak=9850.0, ref=INIT), WED).allow


# ------------------------------------------------------------------ weekend
def test_weekday_fixtures():
    assert WED.weekday() == 2 and FRI.weekday() == 4


def test_friday_2359_allowed(eng):
    t = datetime(2026, 10, 16, 23, 59, 0, tzinfo=UTC)
    st = state(day=t.date())
    assert eng.check_order(order(), acct(ts=t), st, t).allow


def test_saturday_0000_denied(eng):
    t = datetime(2026, 10, 17, 0, 0, 0, tzinfo=UTC)
    d = eng.check_order(order(), acct(ts=t), state(day=t.date()), t)
    assert not d.allow and "weekend_entry" in d.reasons


def test_sunday_denied_monday_0000_allowed(eng):
    sun = datetime(2026, 10, 18, 23, 59, 59, tzinfo=UTC)
    mon = datetime(2026, 10, 19, 0, 0, 0, tzinfo=UTC)
    assert "weekend_entry" in eng.check_order(order(), acct(ts=sun), state(day=sun.date()), sun).reasons
    assert eng.check_order(order(), acct(ts=mon), state(day=mon.date()), mon).allow


def test_weekend_uses_utc_not_local_offset(eng):
    # Fri 23:30 UTC-05:00 == Sat 04:30 UTC -> must be denied
    local = datetime(2026, 10, 16, 23, 30, tzinfo=timezone(timedelta(hours=-5)))
    utc = local.astimezone(UTC)
    d = eng.check_order(order(), acct(ts=utc), state(day=utc.date()), local)
    assert "weekend_entry" in d.reasons


# --------------------------------------------------------------------- news
def test_news_default_window_includes_pad(eng):
    ev = [WED]
    assert eng.news_window_minutes() == 7.0
    for off in (-7 * 60, 0, 7 * 60):                 # edges inclusive
        t = WED + timedelta(seconds=off)
        d = eng.check_order(order(), acct(ts=t), state(), t, ev)
        assert "news_window" in d.reasons, off
    t = WED + timedelta(seconds=7 * 60 + 1)
    assert eng.check_order(order(), acct(ts=t), state(), t, ev).allow
    t = WED - timedelta(seconds=7 * 60 + 1)
    assert eng.check_order(order(), acct(ts=t), state(), t, ev).allow


def test_news_official_window_edges_without_pad(rules):
    e = AtlasRuleEngine(rules, thresholds=Thresholds(news_extra_pad_minutes=0.0))
    for off, expect_block in ((-300, True), (300, True), (301, False), (-301, False)):
        t = WED + timedelta(seconds=off)
        d = e.check_order(order(), acct(ts=t), state(), t, [WED])
        assert ("news_window" in d.reasons) is expect_block, off


def test_news_dict_events_low_impact_ignored(eng):
    ev_low = [{"time": WED, "impact": "low"}]
    ev_high = [{"time": WED, "impact": "high"}]
    ev_default = [{"ts": WED}]
    assert eng.check_order(order(), acct(), state(), WED, ev_low).allow
    assert not eng.check_order(order(), acct(), state(), WED, ev_high).allow
    assert not eng.check_order(order(), acct(), state(), WED, ev_default).allow


def test_news_bad_event_fails_closed(eng):
    naive = datetime(2026, 10, 14, 15, 0, 0)
    assert not eng.check_order(order(), acct(), state(), WED, [naive]).allow
    assert not eng.check_order(order(), acct(), state(), WED, [{"impact": "high"}]).allow
    assert eng.in_news_window(WED, ["garbage"]) is True


def test_news_far_event_does_not_block(eng):
    assert eng.check_order(order(), acct(), state(), WED, [WED + timedelta(hours=3)]).allow


# ------------------------------------------------------------------- margin
def test_margin_projection_boundary(eng):
    # total (margin+free) stays 10_000
    d = eng.check_order(order(margin=4999.0, stop=1.0), acct(free=10000.0), state(), WED)
    assert d.allow and d.computed["projected_margin_usage"] == pytest.approx(0.4999)
    d = eng.check_order(order(margin=5000.0, stop=1.0), acct(free=10000.0), state(), WED)
    assert not d.allow and any(r.startswith("margin_projection") for r in d.reasons)


def test_margin_projection_includes_existing_margin(eng):
    a = acct(margin=3000.0, free=7000.0)
    assert eng.check_order(order(margin=1999.0), a, state(), WED).allow
    assert not eng.check_order(order(margin=2000.0), a, state(), WED).allow


def test_margin_total_zero_denied(eng):
    d = eng.check_order(order(margin=0.0), acct(margin=0.0, free=0.0), state(), WED)
    assert not d.allow and "margin_total_non_positive" in d.reasons


# --------------------------------------------------- per-instrument risk
def test_instrument_risk_boundary(eng):
    st = state()                                    # cap = 0.5 * 300 = 150
    assert eng.check_order(order(stop=150.0), acct(), st, WED).allow
    d = eng.check_order(order(stop=150.01), acct(), st, WED)
    assert not d.allow and any(r.startswith("instrument_risk") for r in d.reasons)


def test_instrument_risk_counts_existing_same_symbol_only(eng):
    st = state()
    a = acct(risk={"XAUUSD": 100.0, "EURUSD": 500.0})
    assert eng.check_order(order(stop=50.0), a, st, WED).allow
    assert not eng.check_order(order(stop=50.01), a, st, WED).allow
    assert eng.check_order(order(stop=50.01, symbol="GBPUSD"), a, st, WED).allow


def test_instrument_cap_scales_with_phase(eng):
    # evaluation daily limit 500 -> cap 250
    st = state("evaluation")
    assert eng.check_order(order(stop=190.0), acct(), st, WED).allow
    assert not eng.check_order(order(stop=190.0), acct(), state("funded"), WED).allow


# ------------------------------------------------------------ protector
def test_protector_floating_loss_buffer_boundary(eng):
    # 1.0% of 10_000 = 100
    d = eng.check_order(order(), acct(equity=9900.0, balance=10000.0), state(peak=INIT), WED)
    assert not d.allow and any(r.startswith("protector_buffer") for r in d.reasons)
    d = eng.check_order(order(), acct(equity=9900.1, balance=10000.0), state(peak=INIT), WED)
    assert d.allow, d.reasons


def test_protector_projection_with_stop(eng):
    a = acct(equity=9920.0, balance=10000.0)        # floating loss 80
    st = state("evaluation", peak=INIT)             # roomy DD/daily limits isolate the rule
    d = eng.check_order(order(stop=120.0), a, st, WED)      # 80+120 = 200 = official 2%
    assert not d.allow and any(r.startswith("protector_projection") for r in d.reasons)
    assert eng.check_order(order(stop=119.0), a, st, WED).allow


def test_floating_pnl_field_overrides_derivation(eng):
    a = acct(equity=10000.0, balance=10000.0, floating=-150.0)
    assert not eng.check_order(order(), a, state(), WED).allow


def test_protector_strikes_progression(eng):
    st = state()
    assert eng.record_protector_strike(st) == "REDUCED_SPLIT"
    assert eng.record_protector_strike(st) == "BREACH"
    d = eng.check_order(order(), acct(), st, WED)
    assert not d.allow and "protector_breach_state" in d.reasons


# ------------------------------------------------------ fail-closed paths
def test_stale_snapshot_denied_boundary(eng):
    ok = acct(ts=WED - timedelta(seconds=30))
    stale = acct(ts=WED - timedelta(seconds=31))
    assert eng.check_order(order(), ok, state(), WED).allow
    d = eng.check_order(order(), stale, state(), WED)
    assert not d.allow and d.reasons[0].startswith("fail_closed")


def test_missing_timestamp_and_future_timestamp_denied(eng):
    assert not eng.check_order(order(), acct(ts=None), state(), WED).allow
    assert not eng.check_order(order(), acct(ts=WED + timedelta(seconds=60)), state(), WED).allow


@pytest.mark.parametrize("field", ["balance", "equity", "margin", "free_margin"])
@pytest.mark.parametrize("bad", [float("nan"), float("inf"), None])
def test_bad_account_numbers_denied(eng, field, bad):
    a = acct()
    setattr(a, field, bad)
    d = eng.check_order(order(), a, state(), WED)
    assert not d.allow and d.reasons[0].startswith("fail_closed")


def test_bad_order_denied(eng):
    for o in (order(stop=float("nan")), order(stop=-1.0), order(margin=float("nan")),
              R.OrderRequest(symbol="", stop_risk_usd=1.0, margin_required=1.0),
              R.OrderRequest(symbol="XAUUSD", stop_risk_usd=None, margin_required=1.0), "buy"):
        assert not eng.check_order(o, acct(), state(), WED).allow


def test_unknown_phase_and_bad_state_denied(eng):
    assert not eng.check_order(order(), acct(), state(phase="demo"), WED).allow
    st = state()
    st.peak_equity = float("nan")
    assert not eng.check_order(order(), acct(), st, WED).allow
    st = state()
    st.initial_balance = 0.0
    assert not eng.check_order(order(), acct(), st, WED).allow


def test_naive_now_denied(eng):
    assert not eng.check_order(order(), acct(), state(), datetime(2026, 10, 14, 12, 0)).allow


def test_mapping_inputs_accepted(eng):
    a = {"balance": INIT, "equity": INIT, "margin": 0.0, "free_margin": INIT, "ts_utc": WED}
    o = {"symbol": "XAUUSD", "stop_risk_usd": 1.0, "margin_required": 100.0}
    assert eng.check_order(o, a, state(), WED).allow


def test_check_order_never_raises_on_garbage(eng):
    assert not eng.check_order(None, None, None, None).allow


# ---------------------------------------------------------------- monitor
def test_monitor_ok(eng):
    assert eng.monitor(acct(), state(), WED) == "OK"


def test_monitor_trailing_thresholds(eng):
    st = state(peak=INIT, ref=9520.0)               # daily neutral, trailing limit 600
    assert eng.monitor(acct(9520.0), st, WED) == "FLATTEN"       # 480 = 80%
    assert eng.monitor(acct(9521.0), st, WED) == "STOP_NEW"      # 79.8%
    st = state(peak=INIT, ref=9640.0)
    assert eng.monitor(acct(9640.0), st, WED) == "STOP_NEW"      # 360 = 60%
    st = state(peak=INIT, ref=9641.0)
    assert eng.monitor(acct(9641.0), st, WED) == "OK"            # 59.8%


def test_monitor_daily_thresholds(eng):
    assert eng.monitor(acct(9760.0), state(peak=9760.0), WED) == "FLATTEN"    # 240 = 80%
    assert eng.monitor(acct(9761.0), state(peak=9761.0), WED) == "STOP_NEW"
    assert eng.monitor(acct(9820.0), state(peak=9820.0), WED) == "STOP_NEW"   # 180 = 60%
    assert eng.monitor(acct(9821.0), state(peak=9821.0), WED) == "OK"


def test_monitor_margin_thresholds(eng):
    assert eng.monitor(acct(margin=6500.0, free=3500.0), state(), WED) == "FLATTEN"
    assert eng.monitor(acct(margin=6499.0, free=3501.0), state(), WED) == "STOP_NEW"
    assert eng.monitor(acct(margin=5000.0, free=5000.0), state(), WED) == "STOP_NEW"
    assert eng.monitor(acct(margin=4999.0, free=5001.0), state(), WED) == "OK"


def test_monitor_protector_thresholds(eng):
    # peaks neutralised so only the floating-loss rule can fire
    def mon(eq):
        return eng.monitor(acct(equity=eq, balance=INIT), state(peak=INIT, ref=INIT), WED)
    assert mon(9850.0) == "FLATTEN"                 # 1.5%
    assert mon(9850.1) == "STOP_NEW"
    assert mon(9900.0) == "STOP_NEW"                # 1.0%
    assert mon(9900.1) == "OK"


def test_monitor_stale_or_nan_is_stop_new(eng):
    assert eng.monitor(acct(ts=WED - timedelta(minutes=5)), state(), WED) == "STOP_NEW"
    assert eng.monitor(acct(float("nan")), state(), WED) == "STOP_NEW"


def test_monitor_internal_error_flattens(eng):
    assert eng.monitor(acct(), state(phase="demo"), WED) == "FLATTEN"
    assert eng.monitor(acct(), None, WED) == "FLATTEN"


def test_monitor_detail_reports_reasons(eng):
    r = eng.monitor_detail(acct(margin=6500.0, free=3500.0), state(), WED)
    assert r.action == "FLATTEN" and any(x.startswith("margin_hard") for x in r.reasons)


# ----------------------------------------------------------- daily reset
def test_no_roll_before_midnight_utc(eng):
    st = state(high=10300.0)
    t = datetime(2026, 10, 14, 23, 59, 59, tzinfo=UTC)
    assert eng.update_state_on_new_day(st, acct(10100.0), t) is False
    assert st.day_ref_date_utc == WED.date() and st.day_ref_equity == INIT


def test_roll_at_midnight_utc_uses_previous_day_high(eng):
    st = state(high=10300.0)
    t = datetime(2026, 10, 15, 0, 0, 0, tzinfo=UTC)
    assert eng.update_state_on_new_day(st, acct(10100.0, balance=10100.0), t) is True
    assert st.day_ref_date_utc == date(2026, 10, 15)
    assert st.day_ref_equity == 10300.0              # previous day's highest equity
    assert st.day_start_balance == 10100.0
    assert st.cycle_day_profits[date(2026, 10, 14)] == pytest.approx(1.0)  # +1.0% of initial


def test_roll_respects_utc_offset_input(eng):
    st = state(high=10200.0)
    t = datetime(2026, 10, 15, 1, 0, 0, tzinfo=timezone(timedelta(hours=1)))   # == 00:00 UTC
    assert eng.update_state_on_new_day(st, acct(10000.0), t)
    t2 = datetime(2026, 10, 15, 0, 59, 0, tzinfo=timezone(timedelta(hours=1)))  # 23:59 UTC prior
    st2 = state(high=10200.0)
    assert not eng.update_state_on_new_day(st2, acct(10000.0), t2)


def test_roll_reference_uses_balance_if_higher(eng):
    st = state(high=10000.0)
    t = datetime(2026, 10, 15, 0, 0, 1, tzinfo=UTC)
    eng.update_state_on_new_day(st, acct(9990.0, balance=10050.0), t)
    assert st.day_ref_equity == 10050.0


def test_daily_floor_after_roll_tightens_with_higher_reference(eng):
    st = state(high=10500.0)
    t = datetime(2026, 10, 15, 0, 0, 0, tzinfo=UTC)
    eng.update_state_on_new_day(st, acct(10400.0), t)
    # ref 10500, base min(10000,10500)=10000 -> funded limit 300 -> floor 10200
    assert eng.daily_floor(st, "funded") == pytest.approx(10200.0)


def test_clock_backwards_across_day_raises(eng):
    st = state(day=date(2026, 10, 15))
    with pytest.raises(ValueError):
        eng.update_state_on_new_day(st, acct(), WED)


def test_update_state_tracks_day_high(eng):
    st = state()
    eng.update_state(acct(10100.0), st, WED)
    eng.update_state(acct(10050.0), st, WED)
    assert st.day_high_equity == 10100.0


def test_daily_reset_restores_headroom_for_orders(eng):
    st = state(peak=9830.0, ref=INIT, high=10000.0)
    assert not eng.check_order(order(stop=10.0), acct(9830.0), st, WED).allow
    t = datetime(2026, 10, 15, 0, 0, 0, tzinfo=UTC)
    a = acct(9830.0, ts=t)
    eng.update_state(a, st, t)
    assert st.day_ref_equity == 10000.0
    # next day ref is still 10000 (prev high) -> same daily loss; the reset is
    # about the DATE, trailing remains
    assert st.day_ref_date_utc == date(2026, 10, 15)


# -------------------------------------------------------------- min hold
def test_min_hold_179_vs_180():
    t0 = datetime(2026, 10, 14, 12, 0, 0, tzinfo=UTC)
    assert min_hold_ok(t0, t0 + timedelta(seconds=179)) is False
    assert min_hold_ok(t0, t0 + timedelta(seconds=180)) is True
    assert min_hold_ok(t0, t0 + timedelta(seconds=181)) is True


def test_min_hold_epoch_numbers_and_invalid(eng):
    assert min_hold_ok(1000.0, 1179.0) is False
    assert min_hold_ok(1000.0, 1180.0) is True
    assert eng.min_hold_ok(1000.0, 1179.0) is False
    assert min_hold_ok(float("nan"), 1180.0) is False
    assert min_hold_ok(datetime(2026, 1, 1), datetime(2026, 1, 2)) is False   # naive
    assert min_hold_ok(None, None) is False
    t0 = datetime(2026, 10, 14, 12, 0, 0, tzinfo=UTC)
    assert min_hold_ok(t0 + timedelta(seconds=300), t0) is False              # negative hold


# -------------------------------------------------------------- payout
def test_payout_three_qualifying_days_minimum():
    r = payout_eligibility([0.5, 0.5, 0.5], 1.5)
    assert r.eligible and r.qualifying_days == 3
    assert r.best_day_share == pytest.approx(1 / 3)


def test_payout_day_threshold_boundary():
    assert payout_eligibility([0.5, 0.5, 0.49], 1.49).eligible is False
    assert payout_eligibility([0.49, 0.49, 0.49, 0.49], 1.96).qualifying_days == 0


def test_payout_two_qualifying_days_not_enough():
    r = payout_eligibility([1.0, 1.0, 0.1], 2.1)
    assert not r.eligible and r.qualifying_days == 2
    assert any(x.startswith("min_profit_days") for x in r.reasons)


def test_payout_best_day_exactly_40pct_ok():
    r = payout_eligibility([2.0, 2.0, 1.0], 5.0)
    assert r.eligible and r.best_day_share == pytest.approx(0.40)
    assert r.delayed_by_consistency is False


def test_payout_best_day_over_40pct_delayed():
    r = payout_eligibility([2.01, 1.5, 1.49], 5.0)
    assert not r.eligible and r.delayed_by_consistency
    assert r.best_day_share == pytest.approx(0.402)


def test_payout_losing_days_count_toward_total_not_qualifying():
    # cycle profit 3.0 = 2.0+1.0+1.0+0.5+(-1.5) ; best 2.0 / 3.0 = 66% -> delayed
    r = payout_eligibility([2.0, 1.0, 1.0, 0.5, -1.5], 3.0)
    assert r.qualifying_days == 4 and r.delayed_by_consistency and not r.eligible


def test_payout_non_positive_cycle_and_empty():
    assert not payout_eligibility([0.5, 0.5, 0.5], 0.0).eligible
    assert not payout_eligibility([], 0.0).eligible
    assert not payout_eligibility([0.6, 0.6, 0.6], -1.0).eligible


def test_payout_usd_threshold_boundary():
    days = [0.6, 0.6, 0.6, 0.6]
    assert payout_eligibility(days, 2.4, cycle_profit_usd=100.0).eligible
    r = payout_eligibility(days, 2.4, cycle_profit_usd=99.99)
    assert not r.eligible and any(x.startswith("below_min_profit_usd") for x in r.reasons)


def test_payout_accepts_mapping_and_rejects_nan():
    m = {date(2026, 10, 1): 0.6, date(2026, 10, 2): 0.6, date(2026, 10, 3): 0.6,
         date(2026, 10, 4): 0.6}
    assert payout_eligibility(m, 2.4).eligible
    assert not payout_eligibility([0.6, float("nan"), 0.6], 1.2).eligible
    assert not payout_eligibility([0.6, 0.6, 0.6], float("nan")).eligible
    assert not payout_eligibility(None, 1.0).eligible


def test_engine_payout_wrapper_uses_json_values(eng):
    assert eng.payout_eligibility([2.0, 2.0, 1.0], 5.0).eligible
    assert not eng.payout_eligibility([2.01, 1.5, 1.49], 5.0).eligible
    assert not eng.payout_eligibility([2.0, 2.0, 1.0], 5.0, cycle_profit_usd=50.0).eligible


# ------------------------------------------------------ evaluation target
def test_evaluation_progress_boundary():
    assert evaluation_progress(10300.0, 10000.0)["target_reached"] is True
    p = evaluation_progress(10299.99, 10000.0)
    assert p["target_reached"] is False and p["progress"] == pytest.approx(0.9999667, rel=1e-5)


def test_evaluation_progress_values_and_negative():
    p = evaluation_progress(9500.0, 10000.0)
    assert p["profit_pct"] == pytest.approx(-0.05) and p["target_usd"] == pytest.approx(300.0)
    assert p["target_reached"] is False


def test_evaluation_progress_rejects_bad_input(eng):
    for b, i in ((float("nan"), 1000.0), (1000.0, 0.0), (1000.0, float("inf"))):
        with pytest.raises(ValueError):
            evaluation_progress(b, i)
    assert eng.evaluation_progress(10300.0, 10000.0)["target_reached"]


# ------------------------------------------------------------- inactivity
def test_inactivity_boundary(eng):
    st = state()
    assert eng.inactivity_ok(st, WED) is False                    # never traded -> not ok
    st.last_trade_ts = WED - timedelta(days=29, hours=23)
    assert eng.inactivity_ok(st, WED) is True
    st.last_trade_ts = WED - timedelta(days=30)
    assert eng.inactivity_ok(st, WED) is False


# ------------------------------------------------------------ state factory
def test_state_new_factory():
    st = AtlasState.new(5000.0, WED, "funded")
    assert st.peak_equity == 5000.0 and st.day_ref_equity == 5000.0
    assert st.day_ref_date_utc == WED.date() and st.phase == "funded"
    assert math.isfinite(st.initial_balance)

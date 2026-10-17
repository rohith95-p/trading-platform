"""Reconcile the live-parity backtest engine against the broker (READ-ONLY MT5).

Replays 2026-10-05 18:00 IST .. 2026-10-15 22:00 IST through BacktestEngine with
the live-parity flags on (see EngineConfig.live_parity), disabling the bot over
the periods it was demonstrably not running, starting from the broker's real
balance, and compares the resulting trade list with the real demo-account deals.

    venv\\Scripts\\python.exe -I scripts/validation/reconcile_live_parity.py [--refresh] [--details]

Needs a running MT5 terminal (history_deals_get / copy_rates_range only -- no
order is ever sent). Bars are cached under research/data_live_parity/ so the main
research cache (and its hashes) is never touched.

Window choice (documented, not tuned):
  * start 2026-10-05 18:00 IST: the 17:45:57 FVG order that day was logged with
    sl_atr_mult 0.1 / tp_atr_mult 2.0 (logs/trades/2026-10-05.jsonl); every order
    from 18:45 on carries 0.5 / 1.5. The old-config week 09-28..10-05 is excluded.
  * end 2026-10-15 22:00 IST: logs/heartbeat last written 22:00 on 10-15.
"""
import argparse
import collections
import datetime as dt
import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import numpy as np                                            # noqa: E402
import MetaTrader5 as mt5                                     # noqa: E402

from src.backtesting.costs import SCENARIOS                   # noqa: E402
from src.backtesting.data import fetch_and_cache, load_bars   # noqa: E402
from src.backtesting.engine import (BacktestEngine, EngineConfig,   # noqa: E402
                                    LIVE_SCAN_PHASE_SEC)
from src.strategies.portfolio_v5_core import PORTFOLIO_6_LEG  # noqa: E402

UTC = dt.timezone.utc
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
DATA_ROOT = os.path.join("research", "data_live_parity")
MAGICS = {5001, 5002, 5003, 5005, 5008, 5009}


def ist(s: str) -> int:
    """'2026-10-14 22:24' (IST) -> epoch seconds."""
    fmt = "%Y-%m-%d %H:%M:%S" if s.count(":") == 2 else "%Y-%m-%d %H:%M"
    return int(dt.datetime.strptime(s, fmt).replace(tzinfo=IST).timestamp())


def fmt(ts: int) -> str:
    return dt.datetime.fromtimestamp(ts, UTC).astimezone(IST).strftime("%m-%d %H:%M:%S")


WINDOW = (ist("2026-10-05 18:00"), ist("2026-10-15 22:00"))

# Bot-down periods. (A) given by the owner; (B) proven by the per-minute D1-GATE
# heartbeat in logs/main_loop.log, which is dense (one line per 60s) on 10-12 and
# 10-13 and shows these holes. The log is NOT dense on 10-06..10-11, so uptime
# there is unknown and the bot is assumed up (flagged in the report).
DOWN_OWNER = [
    ("2026-10-14 00:00", "2026-10-14 22:24"),   # log gap, restarted 22:24 IST
    ("2026-10-15 00:00", "2026-10-15 18:23"),   # down until 18:23 IST
]
DOWN_LOG = [
    ("2026-10-12 09:20:19", "2026-10-12 17:03:04"),
    ("2026-10-12 21:38:49", "2026-10-13 18:04:11"),   # incl. the 17:05:42 crash-start
    ("2026-10-13 21:16:17", "2026-10-13 22:21:19"),
    ("2026-10-13 22:42:20", "2026-10-14 00:00"),
]
# Live portfolio history: 6 legs until the 2026-10-12 17:03 IST restart, 4 legs
# after it (main_loop.log "Active Strategies" lines). Retired legs: magic 5008/5009.
RETIRED = ("PDHLR_STRATEGY_V5", "NY_LIQUIDITY_EXPANSION_V5")
RETIRE_AT = ist("2026-10-12 17:03:04")
# SizingLadder as it stood in the live process: until commit d9c219e (2026-10-13 22:47 IST,
# first live at the 2026-10-14 22:24 IST restart) the $100-200 rung allowed ONE position.
OLD_LADDER = ((0.0, 0.01, 1, 0.01), (100.0, 0.01, 1, 0.01), (200.0, 0.01, 2, 0.02),
              (400.0, 0.01, 3, 0.03), (800.0, 0.02, 2, 0.04), (1200.0, 0.02, 3, 0.06))
LADDER_CHANGE = ist("2026-10-14 22:24:07")
# scripts/protect_profit.py before commit d9c219e: GIVEBACK_PEAK 4.0 / GIVEBACK_FLOOR 1.5
# (the 10-13 19:55 close is logged as "giveback (peak +6.32 -> +1.31)": 1.31 > today's 1.0 floor).
AS_RAN_PROTECT = dict(protect_giveback_peak=4.0, protect_giveback_floor=1.5)
# logs/protect_profit.log holds no 'watcher started' line before 2026-10-12 05:55:15 IST and
# no protect_profit close exists in the broker history before 2026-10-13: the profit-protection
# watcher is only evidenced from that restart on.
PROTECT_FROM = ist("2026-10-12 05:55:15")
# risk_rules.ENFORCE was False until the 2026-10-12 05:55 IST restart (code: commit
# 6a27858 2026-10-11; trade_log 'closed' rows show enforced=false on 10-07 and
# true on 10-12).
ENFORCE_FROM = ist("2026-10-12 05:55:17")


# ---------------------------------------------------------------------------
# broker side
# ---------------------------------------------------------------------------

def fetch_broker():
    if not mt5.initialize():
        raise SystemExit("MT5 terminal not available")
    acct = mt5.account_info()
    deals = mt5.history_deals_get(dt.datetime(2026, 1, 1, tzinfo=UTC), dt.datetime.now(UTC) + dt.timedelta(days=1))
    mt5.shutdown()
    deals = sorted(deals or [], key=lambda d: (d.time, d.ticket))
    return float(acct.balance), deals


def balance_at(now_balance, deals, ts):
    """Balance just before `ts` = current balance minus every later deal's cashflow."""
    later = sum(d.profit + d.swap + d.commission + getattr(d, "fee", 0.0) for d in deals if d.time >= ts)
    return now_balance - later


def broker_trades(deals, lo, hi):
    by_pos = collections.defaultdict(list)
    for d in deals:
        if d.symbol == "XAUUSDm" and d.type in (0, 1) and d.magic in MAGICS:
            by_pos[d.position_id].append(d)
    out = []
    for pid, ds in by_pos.items():
        ins = [x for x in ds if x.entry == 0]
        outs = [x for x in ds if x.entry == 1]
        if ins and outs and lo <= ins[0].time < hi:
            out.append(dict(t=ins[0].time, dir="BUY" if ins[0].type == 0 else "SELL", magic=ins[0].magic,
                            price=ins[0].price, exit_t=outs[-1].time, exit=outs[-1].price,
                            lots=ins[0].volume, why=ins[0].comment,
                            exit_why=outs[-1].comment or str(outs[-1].reason),
                            pnl=sum(x.profit + x.swap + x.commission for x in outs)))
    out.sort(key=lambda x: x["t"])
    return out


# ---------------------------------------------------------------------------
# data
# ---------------------------------------------------------------------------

def ensure_data(refresh: bool):
    need = {"M15": "2026-08-01", "M5": "2026-09-01", "M1": "2026-09-20", "D1": "2026-03-01"}
    for tf, start in need.items():
        if refresh or not os.path.exists(os.path.join(DATA_ROOT, f"XAUUSDm_{tf}.npy")):
            fetch_and_cache("XAUUSDm", tf, dt.datetime.fromisoformat(start).replace(tzinfo=UTC), None, DATA_ROOT)
    return load_bars("XAUUSDm", timeframes=("M15", "M5", "M1", "D1"), data_root=DATA_ROOT)


# ---------------------------------------------------------------------------
# engine side
# ---------------------------------------------------------------------------

def windows(include_log_gaps: bool, extra=(), protect_from=0, no_outages=False):
    pairs = [] if no_outages else list(DOWN_OWNER) + (list(DOWN_LOG) if include_log_gaps else [])
    w = [(ist(a), ist(b)) for a, b in pairs] + list(extra)
    dis = {"*": w}
    if protect_from:
        dis["@protect_profit"] = [(0, protect_from)]
    for r in RETIRED:
        dis[r] = [(RETIRE_AT, WINDOW[1] + 86400)]
    return dis


def lower_bound_windows(first_log):
    """Bot assumed down from 00:00 IST until the first live log record of each day
    (a day with no record at all is down all day)."""
    out = []
    d = dt.datetime.fromtimestamp(WINDOW[0], UTC).astimezone(IST).date()
    end = dt.datetime.fromtimestamp(WINDOW[1], UTC).astimezone(IST).date()
    while d <= end:
        day0 = int(dt.datetime(d.year, d.month, d.day, tzinfo=IST).timestamp())
        out.append((day0, first_log.get(d, day0 + 86400)))
        d += dt.timedelta(days=1)
    return out


def as_ran_kw():
    """Code versions the live process was really running over the window."""
    from src.core.sizing_ladder import SizingLadder
    return dict(d1_intraday_override_mult=2.0, risk_rules_enforce_from_ts=ENFORCE_FROM,
                sizing_ladder_schedule=[(0, OLD_LADDER),
                                        (LADDER_CHANGE, tuple(tuple(r) for r in SizingLadder.LADDER))],
                **AS_RAN_PROTECT)


def run_engine(bars, start_balance, cfg_kw, include_log_gaps=True, parity=True, seed=None, extra_down=(),
               protect_from=0, no_outages=False):
    if parity:
        cfg = EngineConfig.live_parity_preset(symbol="XAUUSDm", starting_balance=start_balance,
                                              disabled_windows=windows(include_log_gaps, extra_down, protect_from, no_outages),
                                              record_decisions=True, **cfg_kw)
    else:   # legacy engine, same data / balance / outage windows
        cfg = EngineConfig(symbol="XAUUSDm", starting_balance=start_balance, sizing_mode="fixed",
                           fixed_lots=0.01, disabled_windows=windows(include_log_gaps, extra_down, 0, no_outages),
                           record_decisions=True, **cfg_kw)
    eng = BacktestEngine(bars=bars, cost=SCENARIOS["observed"], config=cfg)
    if seed and parity:
        eng.seed_risk_state(**seed)
    strategies = [c() for c in PORTFOLIO_6_LEG]
    res = eng.run(strategies, WINDOW[0], WINDOW[1])
    magic = {s.name: s.magic for s in strategies}
    name_of = {v: k for k, v in magic.items()}
    rows = [dict(t=t.entry_time, dir="BUY" if t.is_buy else "SELL", magic=magic[t.strategy],
                 price=t.entry_price, exit_t=t.exit_time, exit=t.exit_price, lots=t.lots,
                 pnl=t.net_pl, why=t.exit_reason, strategy=t.strategy) for t in res.trades]
    rows.sort(key=lambda x: x["t"])
    return rows, res, name_of


def match(broker, eng):
    """Greedy nearest-in-time pairing: same leg, same direction, entry within 5 min."""
    cands = []
    for i, b in enumerate(broker):
        for k, e in enumerate(eng):
            if e["dir"] == b["dir"] and e["magic"] == b["magic"] and abs(e["t"] - b["t"]) <= 300:
                cands.append((abs(e["t"] - b["t"]), i, k))
    cands.sort()
    ub, ue, pairs = set(), set(), []
    for gap, i, k in cands:
        if i in ub or k in ue:
            continue
        ub.add(i); ue.add(k); pairs.append((i, k, gap))
    return pairs, ub, ue


# ---------------------------------------------------------------------------
# live signal log (logs/trades/*.jsonl) -- read-only context for reason guesses
# ---------------------------------------------------------------------------

def load_live_signals():
    rows = []
    for f in sorted(glob.glob(os.path.join(ROOT, "logs", "trades", "2026-10-*.jsonl"))):
        for line in open(f, encoding="utf-8", errors="replace"):
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if r.get("kind") in ("signal", "order") and r.get("strategy") != "TEST_STRATEGY":
                rows.append(r)
    return rows


def in_windows(ts, ws):
    return any(a <= ts < b for a, b in ws)


def guess_engine_only(e, broker, live_sigs, name_of, ups_unknown_first_log):
    """Why did the engine take a trade the broker did not?"""
    strat = name_of.get(e["magic"])
    candle = (e["t"] // 900) * 900 - 900       # last closed candle at entry
    reasons = []
    mine = [r for r in live_sigs if r.get("strategy") == strat and r.get("direction") == e["dir"]
            and abs(int(r.get("candle") or 0) - candle) <= 900]
    if mine:
        c = collections.Counter(f"{r.get('action')}: {r.get('reason')}" for r in mine if r.get("kind") == "signal")
        reasons.append("live logged this signal -> " + "; ".join(f"{k} x{v}" for k, v in c.most_common(2)))
    open_b = sum(1 for b in broker if b["t"] <= e["t"] < b["exit_t"])
    if open_b:
        reasons.append(f"broker had {open_b} position(s) open then")
    if not mine:
        ist_dt = dt.datetime.fromtimestamp(e["t"], UTC).astimezone(IST)
        first = ups_unknown_first_log.get(ist_dt.date())
        if first is None:
            reasons.append("no live record at all that day (bot probably not running)")
        elif e["t"] < first:
            reasons.append(f"before the first live log record of the day ({fmt(first)}): bot probably not running")
        else:
            reasons.append("live logged no signal for this candle (live strategy did not fire, or feed differs)")
    return " | ".join(reasons)


def guess_broker_only(b, eng_dec, name_of):
    strat = name_of.get(b["magic"])
    near = [d for d in eng_dec if d["strategy"] == strat and d["dir"] == b["dir"]
            and b["t"] - 1500 <= d["ts"] <= b["t"] + 300]
    if not near:
        return "engine produced no signal for this leg/direction near that time (strategy/feature or data difference)"
    c = collections.Counter(d["outcome"] for d in near)
    return "engine decisions: " + "; ".join(f"{k} x{v}" for k, v in c.most_common(3))


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------

def report(label, broker, eng, name_of, eng_dec, live_sigs, first_log, details):
    pairs, ub, ue = match(broker, eng)
    print(f"\n=== {label} ===")
    bn, en = sum(b["pnl"] for b in broker), sum(e["pnl"] for e in eng)
    print(f"trades        broker {len(broker):3d}   engine {len(eng):3d}")
    print(f"net P&L       broker ${bn:8.2f}   engine ${en:8.2f}   (gap ${en - bn:+.2f})")
    print(f"matched       {len(pairs)} pairs = {len(pairs) / max(len(broker), 1):.0%} of broker, "
          f"{len(pairs) / max(len(eng), 1):.0%} of engine  (same leg, direction, entry within 5 min)")
    corr = None
    if len(pairs) >= 3:
        pb = np.array([broker[i]["pnl"] for i, _, _ in pairs])
        pe = np.array([eng[k]["pnl"] for _, k, _ in pairs])
        corr = float(np.corrcoef(pb, pe)[0, 1]) if pb.std() > 0 and pe.std() > 0 else float("nan")
        same_sign = int(((pb > 0) == (pe > 0)).sum())
        gaps = np.array([(broker[i]["price"] - eng[k]["price"]) * (1 if broker[i]["dir"] == "BUY" else -1)
                         for i, k, _ in pairs])
        slip = gaps.mean()
        r_ex = float("nan")
        if len(pairs) >= 4:
            keep = np.argsort(np.abs(pb - pe))[:-1]               # drop the single worst pair
            if pb[keep].std() > 0 and pe[keep].std() > 0:
                r_ex = float(np.corrcoef(pb[keep], pe[keep])[0, 1])
        print(f"matched P&L   broker ${pb.sum():.2f}  engine ${pe.sum():.2f}   per-trade correlation r={corr:.3f}  "
              f"same sign {same_sign}/{len(pairs)}   mean |P&L diff| ${np.mean(np.abs(pb - pe)):.2f}   "
              f"r without the single worst pair {r_ex:.3f}")
        print(f"              entry gap (broker minus engine, + = broker worse): mean ${slip:+.3f}  sd ${gaps.std(ddof=1):.3f}  "
              f"mean|gap| ${np.abs(gaps).mean():.3f}  (se of mean ${gaps.std(ddof=1) / np.sqrt(len(gaps)):.3f});  "
              f"mean time gap {np.mean([g for _, _, g in pairs]):.0f}s")
    bo = [b for i, b in enumerate(broker) if i not in ub]
    eo = [e for k, e in enumerate(eng) if k not in ue]
    print(f"broker-only   {len(bo)} trades, P&L ${sum(b['pnl'] for b in bo):.2f}")
    for b in bo:
        print(f"   {fmt(b['t'])} {b['dir']:4s} {name_of.get(b['magic'], b['magic']):22s} pnl {b['pnl']:+7.2f}  "
              f"-> {guess_broker_only(b, eng_dec, name_of)}")
    print(f"engine-only   {len(eo)} trades, P&L ${sum(e['pnl'] for e in eo):.2f}")
    for e in eo:
        print(f"   {fmt(e['t'])} {e['dir']:4s} {name_of.get(e['magic'], e['magic']):22s} pnl {e['pnl']:+7.2f} ({e['why']})"
              f"  -> {guess_engine_only(e, broker, live_sigs, name_of, first_log)}")
    if details:
        print("matched detail (broker | engine):")
        for i, k, g in pairs:
            b, e = broker[i], eng[k]
            print(f"   {fmt(b['t'])} {b['dir']:4s} {name_of.get(b['magic'])[:20]:20s} entry {b['price']:.3f}/{e['price']:.3f} "
                  f"exit {b['exit']:.3f}/{e['exit']:.3f} pnl {b['pnl']:+.2f}/{e['pnl']:+.2f} ({b['exit_why']}/{e['why']}) dt={g}s")
    return dict(n_b=len(broker), n_e=len(eng), net_b=bn, net_e=en, matched=len(pairs), corr=corr)


def calibrate_delay(broker):
    """Seconds between an M15 close and the live fill, for fills on the first scan."""
    phases = [b["t"] % 900 for b in broker if b["t"] % 900 < 60]
    return phases


def first_log_per_day(live_sigs):
    first = {}
    for r in live_sigs:
        d = dt.datetime.fromtimestamp(int(r["ts"]), UTC).astimezone(IST).date()
        first[d] = min(first.get(d, 10 ** 12), int(r["ts"]))
    return first


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true", help="re-download bars into research/data_live_parity")
    ap.add_argument("--details", action="store_true", help="print every matched pair")
    args = ap.parse_args()

    now_bal, deals = fetch_broker()
    start_bal = round(balance_at(now_bal, deals, WINDOW[0]), 2)
    # peak balance before the window, ignoring the 8-minute $10,000 trial deposit of 08-23
    # (deposit then $9,900 withdrawal, deal comments D-trial-USD / W-trial-USD).
    trail = [balance_at(now_bal, deals, d.time + 1) for d in deals if d.time < WINDOW[0]]
    peak_bal = round(max(b for b in trail if b < 5000), 2)
    broker = broker_trades(deals, *WINDOW)
    print(f"window {fmt(WINDOW[0])} .. {fmt(WINDOW[1])} IST | broker balance now ${now_bal:.2f}, "
          f"at window start ${start_bal:.2f} (peak before ${peak_bal:.2f})")
    ph = calibrate_delay(broker)
    print(f"entry-delay calibration: {len(ph)} fills landed <60s after an M15 close; seconds after close "
          f"min/median/mean/max = {min(ph)}/{np.median(ph):.0f}/{np.mean(ph):.1f}/{max(ph)}  "
          f"(engine LIVE_SCAN_PHASE_SEC = {LIVE_SCAN_PHASE_SEC})")

    bars = ensure_data(args.refresh)
    live_sigs = load_live_signals()
    first_log = first_log_per_day(live_sigs)
    month0 = ist("2026-10-01 00:00")
    seed = dict(peak_equity=peak_bal, month_anchor="2026-10",
                month_start_balance=round(balance_at(now_bal, deals, month0), 2))

    results = {}
    quiet = {}

    def go(key, label, details=False, **kw):
        rows, res, name_of = run_engine(bars, start_bal, **kw)
        results[key] = report(label, broker, rows, name_of, res.diagnostics.get("decisions", []),
                              live_sigs, first_log, details)
        quiet[key] = {k: v for k, v in res.diagnostics.items() if k not in ("decisions", "risk_state_final") and v}
        return res

    go("before_no_outages", "BEFORE  legacy engine, same window/data/balance but NO outage exclusion",
       cfg_kw={}, parity=False, no_outages=True)
    go("before", "BEFORE  legacy engine (no live-parity flags), same data/balance/outages",
       cfg_kw={}, parity=False)
    go("after_asran", "AFTER   live_parity, as-ran code versions (D1 override 2.0x, ENFORCE from 10-12 05:55, "
       "old 1-position ladder until 10-14 22:24, protect 4.0/1.5)", details=args.details,
       cfg_kw=as_ran_kw(), protect_from=PROTECT_FROM, seed=seed)
    print("engine diag:", quiet["after_asran"])
    go("after_asran_lower_uptime", "AFTER   as-ran, LOWER-BOUND uptime (bot only from the first live log record of each day)",
       cfg_kw=as_ran_kw(), protect_from=PROTECT_FROM, seed=seed, extra_down=lower_bound_windows(first_log))
    kw0 = as_ran_kw(); kw0["entry_delay_sec"] = 0
    go("after_asran_delay0", "AFTER   as-ran, but entry_delay_sec = 0 (fill at the minute's open)",
       cfg_kw=kw0, protect_from=PROTECT_FROM, seed=seed)
    go("after_preset", "AFTER   live_parity_preset() = code as of 2026-10-17 (D1 override 1.0x, ENFORCE always, "
       "2-position ladder, protect 6.0/1.0)", cfg_kw={}, seed=seed)
    go("after_owner_windows_only", "AFTER   as-ran, but ONLY the owner's two outage windows excluded",
       cfg_kw=as_ran_kw(), protect_from=PROTECT_FROM, seed=seed, include_log_gaps=False)
    print("\nSUMMARY")
    for k, v in results.items():
        print(f"  {k:26s} trades {v['n_b']} vs {v['n_e']:3d}  net ${v['net_b']:7.2f} vs ${v['net_e']:8.2f}  "
              f"matched {v['matched']:2d}  r={v['corr']}")


if __name__ == "__main__":
    main()

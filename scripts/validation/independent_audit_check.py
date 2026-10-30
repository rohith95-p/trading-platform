"""Step 2 of the independent audit (run independent_audit_run.py first).

Re-derive every engine trade from raw M1 bars (numpy only, no engine code)."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import numpy as np
from scripts.validation import independent_audit_run as ar

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "research", "results", "audit_2026-10-30")
D = json.load(open(os.path.join(OUT, "trades.json")))
B = ar.bars()
m1 = B.m1
T, O, H, L, C = (m1[k].astype(np.int64 if k == "time" else float) for k in ("time", "open", "high", "low", "close"))
SPR = np.where(m1["spread"] > 0, m1["spread"].astype(float), 260.0) * 0.001   # fallback = CostModel.fixed_spread_points
POINT, VPP, SLIP, COMM, SWAP_LONG = 0.001, 100.0, 20 * 0.001, 3.50, -515.5

out = {}
for w in ("DEV", "TEST", "RECENT"):
    tr = D[w]["trades"]
    bad = {"pnl": 0, "comm": 0, "swap": 0, "exit_bar": 0, "exit_px": 0, "missed_hit": 0, "balance_chain": 0}
    gap_cost, gap_n, entry_bar_touch, amb, coarse = 0.0, 0, 0, 0, 0
    bal = 5000.0
    examples = []
    for t in tr:
        d = 1.0 if t["is_buy"] else -1.0
        lots = t["lots"]
        gross = (t["exit_price"] - t["entry_price"]) * d * lots * VPP
        if abs(gross - t["gross_pl"]) > 1e-6: bad["pnl"] += 1
        if abs(t["commission"] - COMM * lots) > 1e-9: bad["comm"] += 1
        nights = (t["exit_time"] // 86400) - (t["entry_time"] // 86400)
        sw = SWAP_LONG * POINT * VPP * lots * nights if t["is_buy"] else 0.0
        if abs(sw - t["swap"]) > 1e-6: bad["swap"] += 1
        if abs(gross - COMM * lots + sw - t["net_pl"]) > 1e-6: bad["pnl"] += 1
        bal += t["net_pl"]
        if abs(bal - t["balance_after"]) > 1e-4: bad["balance_chain"] += 1
        # first bar strictly after the entry minute
        i0 = np.searchsorted(T, (t["entry_time"] // 60) * 60, side="right")
        ie = np.searchsorted(T, t["exit_time"], side="left")
        if (i0 >= len(T) or T[i0] - t["entry_time"] > 3 * 86400       # no M1 bars here: engine ran on M15 (coarse)
                or (t["exit_reason"] in ("SL", "TP") and (ie >= len(T) or T[ie] != t["exit_time"]))):
            coarse += 1
            continue
        seg = slice(i0, ie + 1)
        if t["is_buy"]:
            sl_hit = L[seg] <= t["sl"]; tp_hit = H[seg] >= t["tp"]
        else:
            sl_hit = H[seg] + SPR[seg] >= t["sl"]; tp_hit = L[seg] + SPR[seg] <= t["tp"]
        any_hit = sl_hit | tp_hit
        first = int(np.argmax(any_hit)) if any_hit.any() else None
        # entry minute itself (engine does not walk the rest of it): could it have touched a level?
        j = i0 - 1
        if t["is_buy"]:
            if L[j] <= t["sl"] or H[j] >= t["tp"]: entry_bar_touch += 1
        elif H[j] + SPR[j] >= t["sl"] or L[j] + SPR[j] <= t["tp"]: entry_bar_touch += 1
        r = t["exit_reason"]
        if r in ("SL", "TP"):
            if first is None or T[i0 + first] != t["exit_time"]:
                bad["exit_bar"] += 1; examples.append(("exit_bar", t))
            k = i0 + first if first is not None else ie
            want = "SL" if (sl_hit[first] if first is not None else False) else "TP"
            if sl_hit[first] and tp_hit[first]: amb += 1
            exp_px = (t["sl"] - SLIP if t["is_buy"] else t["sl"] + SLIP) if want == "SL" else t["tp"]
            if want != r or abs(exp_px - t["exit_price"]) > 1e-6:
                bad["exit_px"] += 1; examples.append(("exit_px", t))
            if r == "SL":   # gap through the stop: real fill = bar open, engine = stop level
                o = O[k] if t["is_buy"] else O[k] + SPR[k]
                beyond = (o < t["sl"]) if t["is_buy"] else (o > t["sl"])
                if beyond:
                    gap_n += 1
                    gap_cost += abs(o - t["sl"]) * lots * VPP
        else:
            if first is not None and T[i0 + first] < t["exit_time"]:
                bad["missed_hit"] += 1; examples.append(("missed", t))
    pl = np.array([t["net_pl"] for t in tr])
    out[w] = dict(n=len(tr), net=round(float(pl.sum()), 2), coarse_m15_trades_skipped=coarse, bad=bad, ambiguous_bars=amb,
                  sl_gaps=gap_n, sl_gap_extra_cost=round(gap_cost, 2), entry_bar_touch=entry_bar_touch,
                  reasons={r: sum(1 for t in tr if t["exit_reason"] == r) for r in {t["exit_reason"] for t in tr}})
    print(w, json.dumps(out[w]))
    for e in examples[:3]:
        print("   e.g.", e[0], {k: e[1][k] for k in ("strategy", "is_buy", "entry_time", "exit_time", "entry_price", "exit_price", "sl", "tp", "exit_reason")})

# look-ahead probe: trades entered before the cut must be identical in the truncated run
full = {(t["entry_time"], t["strategy"]): t for t in D["RECENT"]["trades"]}
cut = D["RECENT_CUT"]["trades"]
cut_end = max(t["exit_time"] for t in cut)
same = diff = 0
for t in cut:
    if t["exit_reason"] == "end_of_data" or t["exit_time"] >= cut_end - 3600:
        continue
    f = full.get((t["entry_time"], t["strategy"]))
    if f and all(abs(f[k] - t[k]) < 1e-9 for k in ("entry_price", "exit_price", "sl", "tp", "exit_time")):
        same += 1
    else:
        diff += 1
        print("   lookahead diff:", t["strategy"], t["entry_time"], f and f["exit_time"])
print("LOOKAHEAD probe: identical", same, "different", diff)
json.dump(out, open(os.path.join(OUT, "check.json"), "w"), indent=1)

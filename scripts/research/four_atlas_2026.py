"""Four archived Ultra Core strategies, executed on ordered XAUUSD bid/ask quotes."""
from __future__ import annotations

import argparse
import csv
import json
import os
from dataclasses import asdict, fields
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

os.environ.update(ULTRA_TRADE_24H="1", ULTRA_DISABLE_ALERTS="1", ULTRA_NO_TRIAL_LEDGER="1")
from src.backtesting.engine import BacktestEngine, EngineConfig, Trade
from src.backtesting.costs import SCENARIOS
from src.strategies.portfolio_atlas import PORTFOLIO
from scripts.research.four_atlas_archive import load_bars, ticks_for_month


class QuoteEngine(BacktestEngine):
    """Retain the engine's opening-quote scan order. Use each actual subsequent quote for protection."""
    def __init__(self, *args):
        super().__init__(*args)
        self.minute = None
        self.month = None
        self.entry_quotes = {}
        self.exit_quotes = {}
        self.next_exit = {}
        self.closing = []

    def minute_quotes(self, ts):
        if self.minute != ts:
            d = datetime.fromtimestamp(ts, timezone.utc)
            key = d.year, d.month
            if key != self.month:
                self.all_quotes = ticks_for_month(*key)
                self.quote_times = np.ascontiguousarray(self.all_quotes["ms"])
                self.month = key
            low, high = self.quote_times.searchsorted([ts*1000, (ts+60)*1000])
            self.first_index = int(low)
            self.quotes = self.all_quotes[low:high]
            if len(self.quotes) == 0:
                raise ValueError(f"Observed M1 bar has no quotes: {ts}")
            self.minute = ts
        return self.quotes

    def _sample_equity(self, ts, bid, spread_pts, phase):
        if phase == "interval_end":
            # The engine asks each ticket about the whole same minute. Broker settlements,
            # risk-streak updates and ledger balances must follow the actual quote order.
            for ms, index, pos, price, reason in sorted(self.closing, key=lambda e: (e[0],e[1],e[2].ticket)):
                super()._close(pos,price,ms//1000,reason)
            self.closing.clear()
        self.stage = phase
        super()._sample_equity(ts, bid, spread_pts, phase)

    def _open(self, strategy_name, magic, is_buy, fill_price, ts, *args, **kwargs):
        quotes = self.minute_quotes(ts)
        first = quotes[0]
        expected = float(first["ask" if is_buy else "bid"]) + (1 if is_buy else -1)*self.cost.slip(self.spec.point)
        if abs(expected-fill_price) > self.spec.point*.51:
            raise ValueError(f"Entry quote mismatch: {ts}, {expected}, {fill_price}")
        pos = super()._open(strategy_name, magic, is_buy, expected, ts, *args, **kwargs)
        if pos:
            self.entry_quotes[pos.ticket] = int(first["ms"]), self.first_index
        return pos

    def _m1_slice(self,start_ts,end_ts):
        rows=super()._m1_slice(start_ts,end_ts)
        if rows is None or not len(rows):
            raise ValueError(f"Unexpected M15 without a quoted minute: {start_ts}")
        return rows

    def _walk_minute(self, pos, bar, ts, point, ambiguous, is_m15_close=False):
        quotes = self.minute_quotes(ts)
        if self.stage == "open":
            quotes = quotes[:1]
        elif self.stage != "open_after_orders":
            raise RuntimeError(self.stage)
        side = quotes["bid" if pos.is_buy else "ask"]
        stops = side <= pos.sl if pos.is_buy else side >= pos.sl
        targets = side >= pos.tp if pos.is_buy else side <= pos.tp
        hits = np.flatnonzero(stops | targets)
        terminal = int(hits[0]) if len(hits) else len(side)-1
        marks = side[:terminal+1]
        pos.price_current = float(marks[-1])
        if pos.is_buy:
            pos.mfe_price = max(pos.mfe_price, float(marks.max()))
            pos.mae_price = min(pos.mae_price, float(marks.min()))
        else:
            pos.mfe_price = min(pos.mfe_price, float(marks.min()))
            pos.mae_price = max(pos.mae_price, float(marks.max()))
        if not len(hits):
            return None
        self.next_exit[pos.ticket] = (int(quotes["ms"][terminal]), self.first_index+terminal)
        if stops[terminal]:
            return float(side[terminal]) - (1 if pos.is_buy else -1)*self.cost.slip(point), "SL"
        return pos.tp, "TP"

    def _close(self, pos, exit_price, ts, reason):
        if pos.ticket in self.next_exit:
            event = self.next_exit.pop(pos.ticket)
        else:
            quotes = self.minute_quotes(ts)
            idx = len(quotes)-1 if reason=="END_OF_DATA" else 0
            event = int(quotes[idx]["ms"]), self.first_index+idx
            exit_price = float(quotes[idx]["bid" if pos.is_buy else "ask"])-(1 if pos.is_buy else -1)*self.cost.slip(self.spec.point)
        self.exit_quotes[pos.ticket] = event
        # _rr_after_close normally estimates the offset inside an OHLC minute;
        # our timestamp already includes that offset.
        pos.hit_frac = 0.
        if self.stage=="open_after_orders" and reason in ("SL","TP"):
            self.closing.append((*event,pos,exit_price,reason))
        else:
            super()._close(pos,exit_price,event[0]//1000,reason)


def run(name, year=2026, start=None, phase="evaluation", out=None):
    if phase not in ("evaluation","funded"): raise ValueError(phase)
    start = int(start if start is not None else datetime(year,1,1,tzinfo=timezone.utc).timestamp())
    end = int(datetime(2026,11,1,tzinfo=timezone.utc).timestamp()) if year==2026 else int(datetime(year+1,1,1,tzinfo=timezone.utc).timestamp())
    if name=="portfolio":
        classes=PORTFOLIO
    elif name=="retained_portfolio":
        classes=[c for c in PORTFOLIO if c.__name__!="NYSessionReversalV6"]
    else:
        classes=[c for c in PORTFOLIO if c.__name__==name]
    if not classes: raise ValueError(name)
    dest=Path(out) if out else Path(f"research/results/four_strategies_{year}")/name
    dest.mkdir(parents=True,exist_ok=True)
    bars=load_bars(year)
    cfg=EngineConfig.live_parity_preset(
        starting_balance=5000., fixed_lots=.02, sizing_mode="fixed", leverage=50. if phase=="funded" else 100.,
        max_concurrent=3, max_same_direction=3, history_bars=7500, protect_profit=False,
        # Keep all observed minutes in partially quoted M15 blocks; absent M1 is refused.
        m1_policy="coarse", entry_delay_sec=0,
        sizing_ladder_schedule=[(0,[(0.,.02,3,.06)])],
    )
    cost=SCENARIOS["realistic_ecn"]
    engine=QuoteEngine(bars,cost,cfg)
    if cfg.close_only_trail or not cfg.causal_minute_order:
        raise ValueError("This replay requires causal scans and tick-triggered protection")
    res=engine.run([cls() for cls in classes],start,end)
    rows=[]
    for trade in res.trades:
        row=asdict(trade)
        row["entry_time_ms"],row["entry_quote_index"]=engine.entry_quotes[trade.ticket]
        row["exit_time_ms"],row["exit_quote_index"]=engine.exit_quotes[trade.ticket]
        rows.append(row)
    if any(a["exit_time_ms"]>b["exit_time_ms"] for a,b in zip(rows,rows[1:])):
        raise ValueError("Nonchronological MT5-style settlements")
    cols=[f.name for f in fields(Trade)]+["entry_time_ms","entry_quote_index","exit_time_ms","exit_quote_index"]
    with (dest/"trades.csv").open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=cols); w.writeheader(); w.writerows(rows)
    pnl=np.array([r["net_pl"] for r in rows])
    gross_profit=float(pnl[pnl>0].sum());gross_loss=-float(pnl[pnl<0].sum())
    result=dict(name=name,year=year,phase=phase,start=start,end_exclusive=end,config=cfg.as_dict(),
                cost=asdict(cost),data_hash=res.data_hash,diagnostics=res.diagnostics,
                strategies=[c.__name__ for c in classes],trades=len(rows),wins=int((pnl>0).sum()),
                gross_profit=gross_profit,gross_loss=gross_loss,net=float(pnl.sum()),pf=gross_profit/gross_loss if gross_loss else None,
                win_rate=float((pnl>0).mean()) if len(pnl) else None)
    assert abs(5000+pnl.sum()-engine.balance)<1e-6
    assert res.diagnostics["bars_without_m1"]==0
    (dest/"summary.json").write_text(json.dumps(result,indent=2,default=lambda v:v.item()),encoding="utf-8")
    print(name,len(rows),float(pnl.sum()),result["pf"],flush=True)
    return result


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("name")
    parser.add_argument("--year",type=int,default=2026)
    parser.add_argument("--start",type=int)
    parser.add_argument("--phase",default="evaluation",choices=["evaluation","funded"])
    parser.add_argument("--out")
    run(**vars(parser.parse_args()))

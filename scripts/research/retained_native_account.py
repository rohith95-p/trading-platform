"""Reconcile native retained-strategy MT5 deals, frozen Python fills and Atlas equity."""
import argparse
from collections import defaultdict
import csv
from io import StringIO
import json
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.research.four_atlas_archive import ticks_for_month
from scripts.research.four_atlas_lifecycle import Account, COST, DAY, audit_trade_ledger
from scripts.research.luna_six_month_audit import read_report

NAMES = {"portfolio":"retained_portfolio", "filtered":"AsianRangeFilteredV6",
         "breakout":"AsianBreakoutV6","london":"LondonMomentumTightV6"}
MAGIC = {7311:"ASIAN_BREAKOUT_V6",7320:"ASIAN_RANGE_FILTERED_V6",7324:"LONDON_MOMENTUM_TIGHT_V6"}


class NativeAccount(Account):
    """Use the native deal charges. Fees on the open are paid immediately."""
    verify_protector_from_quotes = False

    def equity(self, day, bid, ask):
        eq = self.cash
        for p in self.open.values():
            ounces = 100*p.lots
            eq = eq + ((bid-p.entry_price) if p.is_buy else (p.entry_price-ask))*ounces
            nights = p.exit_time_ms//DAY-p.entry_time_ms//DAY
            if p.swap and nights:
                eq = eq + p.swap*min(day-p.entry_time_ms//DAY,nights)/nights
        return eq

    def fill(self, action, p, ms):
        if self.status != "active":
            return
        # Closing net_pl includes entry-side charges already booked.
        if self.phase=="funded" and action=="exit" and p.exit_reason=="ATLAS_PROTECTOR" and self.last_strike_ms!=ms:
            self.last_strike_ms=ms
            self.strikes+=1
            self.events.append(dict(event="native_protector_liquidation",strike=self.strikes,time=pd.Timestamp(ms,unit="ms",tz="UTC").isoformat()))
            if self.strikes>=2:
                self.end("second_protector_breach",ms,self.final_equity)
                return
        self.cash += p.entry_fee if action=="entry" else -p.entry_fee
        super().fill(action,p,ms)


def read_export(path):
    data=path.read_bytes()
    text=data.decode('utf-16' if data.startswith((b'\xff\xfe',b'\xfe\xff')) else 'utf-8-sig')
    sep=csv.Sniffer().sniff(text[:1000],delimiters='\t,;').delimiter
    return pd.read_csv(StringIO(text),sep=sep)


def locate(deal, previous):
    ts=int(deal.time_msc)
    d=pd.Timestamp(ts,unit='ms',tz='UTC')
    q=ticks_for_month(d.year,d.month)
    a,b=q['ms'].searchsorted([ts,ts+1])
    exact=b>a
    if not exact:
        lo=ts//1000*1000
        a,b=q['ms'].searchsorted([lo,lo+1000])
    a=max(int(a),previous)
    if a>=b:
        raise ValueError(f"No ordered original tick in the MT5 fill second: {d}")
    side='ask' if deal.type==0 else 'bid'
    j=a+int(np.argmin(np.abs(q[side][a:b]-deal.price)))
    return int(q['ms'][j]),j,exact


def normalize(deals):
    open_by_id={}
    out=[]
    previous={}
    for d in deals.itertuples(index=False):
        if int(d.type) not in (0,1):
            continue
        key=pd.Timestamp(d.time_msc,unit='ms',tz='UTC').strftime('%Y-%m')
        ms,idx,exact=locate(d,previous.get(key,0))
        previous[key]=idx
        pos=int(d.position_id)
        if d.entry==0:
            if pos in open_by_id:
                raise ValueError('Netting/pyramiding of existing position requires per-fill accounting')
            open_by_id[pos]=(d,ms,idx,exact)
        elif d.entry==1:
            initial, ems, ei, eexact=open_by_id.pop(pos)
            assert initial.type!=d.type and abs(initial.volume-d.volume)<1e-9
            fees=initial.fee+initial.commission+d.fee+d.commission
            row=dict(ticket=pos,strategy=MAGIC.get(int(initial.magic),f'magic_{int(initial.magic)}'),
                     is_buy=bool(initial.type==0),lots=initial.volume,entry_time=ems//1000,exit_time=ms//1000,
                     entry_time_ms=ems,exit_time_ms=ms,entry_quote_index=ei,exit_quote_index=idx,
                     entry_ms_exact=eexact,exit_ms_exact=exact,entry_price=initial.price,exit_price=d.price,
                     initial_sl=initial.sl,tp=initial.tp,entry_fee=initial.fee+initial.commission,commission=-fees,
                     gross_pl=d.profit,swap=initial.swap+d.swap,net_pl=d.profit+initial.swap+d.swap+fees,
                     exit_reason={4:"SL",5:"TP"}.get(int(d.reason),f"native_reason_{int(d.reason)}"))
            out.append(row)
        else:
            raise ValueError(f"Unsupported native deal entry {d.entry}")
    assert not open_by_id,'Open positions remain without a terminal mark'
    return pd.DataFrame(out)


def comparable(positions):
    adjusted=positions.copy()
    slip=COST.slip(.001)
    sign=np.where(adjusted.is_buy,1.,-1.)
    adjusted['entry_price']+=sign*slip
    adjusted['exit_price']-=sign*slip*(adjusted.exit_reason!='TP')
    adjusted['gross_pl']=(adjusted.exit_price-adjusted.entry_price)*sign*adjusted.lots*100.
    adjusted['swap']=[COST.swap(p.lots,p.is_buy,p.entry_time,p.exit_time,.001,100.) for p in adjusted.itertuples()]
    adjusted['commission']=adjusted.lots*COST.commission_per_lot_roundtrip
    adjusted['net_pl']=adjusted.gross_pl+adjusted.swap-adjusted.commission
    return adjusted


def metrics(rows):
    pnl=rows.net_pl
    gp=float(pnl[pnl>0].sum())
    gl=float(-pnl[pnl<0].sum())
    return dict(trades=len(pnl),wins=int((pnl>0).sum()),win_rate_pct=float((pnl>0).mean()*100) if len(pnl) else None,
                net=float(pnl.sum()),pf=gp/gl if gl>0 else None,gross_profit=gp,gross_loss=gl)


def compare(native,python,out):
    keys=['strategy','is_buy','signal_minute','instance']
    cols=['ticket','entry_time_ms','exit_time_ms','entry_price','exit_price','net_pl']
    frames=[]
    for df in (native,python):
        f=df.assign(signal_minute=df.entry_time_ms//60000)
        f['instance']=f.groupby(keys[:-1]).cumcount()
        frames.append(f[keys+cols])
    joined=pd.merge(*frames,on=keys,how="outer",suffixes=("_mt5","_python"),indicator=True)
    joined.to_csv(out,index=False)
    matched=joined[joined._merge=='both']
    return dict(matched_entry_minute_direction_strategy=len(matched),native_only=int((joined._merge=='left_only').sum()),
                python_only=int((joined._merge=='right_only').sum()),
                matches_exit_same_minute=int((matched.exit_time_ms_mt5//60000==matched.exit_time_ms_python//60000).sum()),
                matched_native_net=float(matched.net_pl_mt5.sum()),matched_python_net=float(matched.net_pl_python.sum()),
                max_abs_entry_price_delta=float((matched.entry_price_mt5-matched.entry_price_python).abs().max()) if len(matched) else None)


def analyze(folder,year,roster,phase="evaluation",start=None,protector_ms=()):
    prefix=f"{year}_{roster}"+("_funded" if phase=="funded" else "")
    metrics_htm,booked=read_report(folder/f"{prefix}.htm")
    exported=read_export(folder/f"{prefix}_deals.csv")
    if len(exported):
        eligible=exported[exported.type.isin([0,1])]
        assert len(eligible)==len(booked),(len(eligible),len(booked))
        for r,d in zip(eligible.itertuples(),booked):
            assert r.order==d["order"] and abs(r.price-d["price"])<.00051 and abs(r.volume-d["volume"])<1e-8
    raw=normalize(exported)
    if raw.empty:
        raise ValueError('Zero fills: explicitly audit the 30-day inactivity deadline')
    for ms in protector_ms:
        hits=raw.exit_time_ms==ms
        if not hits.any(): raise ValueError(f"Tester journal Protector {ms} had no matching close")
        raw.loc[hits,"exit_reason"]="ATLAS_PROTECTOR"
    arr=comparable(raw)
    raw.to_csv(folder/f"{prefix}_trades.csv",index=False)
    cfg=dict(name=roster, phase=phase, start=int(pd.Timestamp(start or f'{year}-01-01',tz='UTC').timestamp()),
             end_exclusive=int(pd.Timestamp('2026-11-01' if year==2026 else '2026-01-01',tz='UTC').timestamp()))
    assert abs(raw.net_pl.sum()-float(metrics_htm['Total Net Profit'].replace(' ','')))<.011
    cfg['net']=float(raw.net_pl.sum())
    native=audit_trade_ledger(cfg,raw,NativeAccount,False)
    cfg['net']=float(arr.net_pl.sum())
    overlay=audit_trade_ledger(cfg,arr)
    py=Path(f"research/results/four_strategies_{year}")/NAMES[roster]
    if phase=="funded":
        py=py/'funded'
    python=pd.read_csv(py/'trades.csv')
    report=dict(year=year,roster=roster,phase=phase,mt5=metrics_htm,native_after_terminal_charges=metrics(raw),
                standardized_ecn=metrics(arr),python=metrics(python),
                fill_comparison=compare(raw,python,folder/f"{prefix}_fill_comparison.csv"),
                exact_fill_ms=int(raw.entry_ms_exact.sum()+raw.exit_ms_exact.sum()),fill_count=2*len(raw),
                multi_rollover_positions_with_swap=int(((raw.exit_time_ms//DAY-raw.entry_time_ms//DAY>1)&(raw.swap!=0)).sum()),
                timing="Exact tick milliseconds resolved at the closest bid/ask fill price among same-ms quotes; missing milliseconds require an ordered quote in the same second.",
                native=native,standardized_ecn_path=overlay)
    (folder/f"{prefix}_audit.json").write_text(json.dumps(report,indent=2))
    print(prefix,report['native_after_terminal_charges'],report['fill_comparison'],native['atlas']['status'],native['atlas']['time'],
          'ECN:',overlay['atlas']['status'],overlay['atlas']['time'])


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("year",type=int)
    p.add_argument("roster",choices=NAMES)
    p.add_argument("--phase",choices=['funded','evaluation'],default="evaluation")
    p.add_argument("--start")
    p.add_argument("--protector-ms",type=int,nargs="*",default=[])
    p.add_argument("--folder",type=Path,default=Path("research/results/retained_mt5"))
    analyze(**vars(p.parse_args()))

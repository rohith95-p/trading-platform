"""Independent fill checks and portfolio-to-standalone attribution for 2026."""
import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from scripts.research.four_atlas_archive import ticks_for_month
from src.strategies.portfolio_atlas import PORTFOLIO

ROOT = Path("research/results")


def verify(path):
    summary = json.loads((path/"summary.json").read_text())
    ledger = list(csv.DictReader((path/"trades.csv").open(encoding="utf-8")))
    slip = summary["cost"]["slippage_points"]*.001
    balance = 5000.
    previous = (0,0)
    for trade in ledger:
        buy = trade['is_buy']=='True'
        side = 1. if buy else -1.
        quotes=[]
        for prefix in ['entry','exit']:
            time=int(trade[prefix+'_time_ms'])
            day=datetime.fromtimestamp(time/1000,timezone.utc)
            q=ticks_for_month(day.year,day.month)[int(trade[prefix+'_quote_index'])]
            assert int(q['ms'])==time
            quotes.append(q)
        entry,exit_quote=quotes
        entry_px=float(trade['entry_price'])
        exit_px=float(trade['exit_price'])
        expected=entry['ask' if buy else 'bid']+side*slip
        assert abs(entry_px-expected)<1e-6
        mark=exit_quote['bid' if buy else 'ask']
        if trade['exit_reason']=='TP':
            assert side*(mark-float(trade['tp']))>=-1e-8
            assert abs(exit_px-float(trade['tp']))<1e-8
        else:
            assert abs(exit_px-(mark-side*slip))<1e-6
            if trade['exit_reason']=='SL':
                assert side*(mark-float(trade['sl']))<=1e-8
        assert trade['lots']=='0.02' and float(trade['initial_sl'])>0
        gross=(exit_px-entry_px)*side*100.*float(trade['lots'])
        net=gross-float(trade['commission'])+float(trade['swap'])
        assert abs(net-float(trade['net_pl']))<1e-7
        balance+=net
        assert abs(balance-float(trade['balance_after']))<1e-6
        tick_order=(int(trade['exit_time_ms']),int(trade['exit_quote_index']))
        assert previous<=tick_order
        previous=tick_order
    assert abs(balance-5000.-summary['net'])<1e-6
    return ledger


def keyed(rows):
    return {(r['strategy'],r['entry_time_ms'],r['entry_quote_index'],r['is_buy']):r for r in rows}


def main(year,retained):
    out=ROOT/f"four_strategies_{year}"
    portfolio_dir=out/('retained_portfolio' if retained else 'portfolio')
    portfolio=verify(portfolio_dir)
    records=[]
    details=[]
    for cls in PORTFOLIO:
        if retained and cls.__name__=='NYSessionReversalV6':
            continue
        name=cls().name
        solo=verify(out/cls.__name__)
        inside=[r for r in portfolio if r['strategy']==name]
        s,p=keyed(solo),keyed(inside)
        assert len(s)==len(solo) and len(p)==len(inside)
        exact=set(s)&set(p)
        only_s=set(s)-set(p)
        only_p=set(p)-set(s)
        records.append(dict(strategy=name,standalone_count=len(s),standalone_net=round(sum(float(r['net_pl']) for r in solo),3),
                            portfolio_count=len(p),portfolio_net=round(sum(float(r['net_pl']) for r in inside),3),
                            same_entry_count=len(exact),standalone_only_count=len(only_s),portfolio_only_count=len(only_p),
                            standalone_only_net=round(sum(float(s[k]['net_pl']) for k in only_s),3),
                            portfolio_only_net=round(sum(float(p[k]['net_pl']) for k in only_p),3)))
        for k in sorted(set(s)|set(p)):
            details.append(dict(strategy=name,entry_time_ms=k[1],entry_quote_index=k[2],is_buy=k[3],
                                observed_in='both' if k in exact else ('standalone_only' if k in only_s else 'portfolio_only'),
                                standalone_ticket=s.get(k,{}).get('ticket'),portfolio_ticket=p.get(k,{}).get('ticket'),
                                standalone_net=s.get(k,{}).get('net_pl'),portfolio_net=p.get(k,{}).get('net_pl')))
    for filename,rows in [('portfolio_contributions.csv',records),('compared_entries.csv',details)]:
        with ((portfolio_dir if retained else out)/filename).open('w',newline='',encoding='utf-8') as f:
            writer=csv.DictWriter(f,fieldnames=rows[0]);writer.writeheader();writer.writerows(rows)
    print(json.dumps(records,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--year',type=int,default=2026)
    parser.add_argument('--retained',action='store_true')
    main(**vars(parser.parse_args()))

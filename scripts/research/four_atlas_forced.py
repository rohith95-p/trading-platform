"""Replay the original quote engine after a verified Atlas forced-close event.

The intervention index is discovered on the previous run. The position identity
and observed mark are checked on rerun. Forced fills pay market slippage.
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.research import four_atlas_2026 as runner
from scripts.research.four_atlas_lifecycle import run as audit


def recouple(folder):
    output=Path(folder)
    initial=json.loads((output/'summary.json').read_text())
    rules=[]
    original=runner.QuoteEngine

    class FundedEngine(original):
        def _walk_minute(self, pos, bar, ts, point, ambiguous, is_m15_close=False):
            for rule in rules:
                if rule['ticket']!=pos.ticket or rule['ms']//60000!=ts//60:
                    continue
                if rule['entry_ms']!=self.entry_quotes[pos.ticket][0]:
                    raise ValueError('Forced ticket changed across replay')
                q=self.minute_quotes(ts)
                if self.stage=='open' and rule['quote_index']!=self.first_index:
                    continue
                j=rule['quote_index']-self.first_index
                if int(q[j]['ms'])!=rule['ms']:
                    raise ValueError('Forced close quote timestamp mismatch')
                sides=q['bid' if pos.is_buy else 'ask'][:j+1]
                pos.price_current=float(sides[-1])
                if pos.is_buy:
                    pos.mfe_price=max(pos.mfe_price,float(sides.max()))
                    pos.mae_price=min(pos.mae_price,float(sides.min()))
                else:
                    pos.mfe_price=min(pos.mfe_price,float(sides.min()))
                    pos.mae_price=max(pos.mae_price,float(sides.max()))
                self.next_exit[pos.ticket]=(rule['ms'],rule['quote_index'])
                fill=float(sides[-1])-(1 if pos.is_buy else -1)*self.cost.slip(point)
                return fill,rule['reason']
            return super()._walk_minute(pos,bar,ts,point,ambiguous,is_m15_close)

    try:
        runner.QuoteEngine=FundedEngine
        old=output/'forced_fills.json'
        if old.exists():
            rules.extend(json.loads(old.read_text()))
        while True:
            result=audit(output)['atlas']
            status=result['status']
            if status not in ('news_entry_requires_liquidation','protector_requires_liquidation','margin_requires_liquidation'):
                break
            if status=='margin_requires_liquidation':
                raise ValueError('Margin liquidation needs profit deduction coupling')
            event=result['rule_events'][-1]
            ms=int(pd.Timestamp(event['time']).value//1_000_000)
            d=pd.Timestamp(ms,unit='ms',tz='UTC')
            q=runner.ticks_for_month(d.year,d.month)
            indices=np.flatnonzero(q['ms']==ms)
            trades=pd.read_csv(output/'trades.csv').set_index('ticket')
            open_positions=trades.loc[event['tickets']]
            if status.startswith('protector'):
                # Locate the first executable liquidation quote below -$100,
                # including rollover and reserved commission, among equal-ms rows.
                floatpl=np.zeros(len(indices))
                for ticket,p in open_positions.iterrows():
                    v=q['bid' if p.is_buy else 'ask'][indices]
                    floatpl+=((v-p.entry_price)*(1 if p.is_buy else -1)*100*p.lots
                              -p.commission+runner.SCENARIOS['realistic_ecn'].swap(
                                p.lots,p.is_buy,p.entry_time,ms//1000,.001,100.))
                j=int(indices[np.flatnonzero(floatpl <= -100)[0]])
            else:
                j=int(open_positions.iloc[0].entry_quote_index)
            for ticket,p in open_positions.iterrows():
                rule=dict(ticket=int(ticket),entry_ms=int(p.entry_time_ms),ms=ms,quote_index=j,
                          reason='ATLAS_NEWS' if status.startswith('news') else 'ATLAS_PROTECTOR')
                if rule in rules:
                    raise ValueError('Forced close did not propagate through normal engine path')
                rules.append(rule)
            runner.run(initial['name'],year=initial['year'],start=initial['start'],phase='funded',out=output)
            old.write_text(json.dumps(rules,indent=2))
        return result

    finally:
        runner.QuoteEngine=original


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('folder',type=Path)
    args=p.parse_args()
    r=recouple(args.folder)
    print(r['status'],r['time'],r['balance'],r['modeled_cash_received'])

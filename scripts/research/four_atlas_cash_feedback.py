"""Verify fixed-lot funded engine fills after scheduled payout and deduction cash debits."""
import argparse
from collections import deque
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scripts.research.four_atlas_2026 import QuoteEngine, EngineConfig, SCENARIOS, PORTFOLIO, load_bars


def check(path):
    summary=json.loads((path/"summary.json").read_text())
    account=json.loads((path/"atlas.json").read_text())["atlas"]
    rows=pd.read_csv(path/"trades.csv")
    cash_events=deque(sorted((pd.Timestamp(e["time"]).value//1000000,e.get("gross",e.get("amount")))
        for e in account["modeled_payouts"]+[e for e in account["rule_events"] if e["event"]=="profit_deduction"]))
    total=sum(amount for _,amount in cash_events)
    class Debited(QuoteEngine):
        def _sample_equity(self, ts, bid, spread_pts, phase):
            super()._sample_equity(ts,bid,spread_pts,phase)
            if phase == 'open':
                while cash_events and cash_events[0][0]<=ts*1000:
                    self.balance-=cash_events.popleft()[1]
                    self.stub.balance=self.balance
    cfg=EngineConfig.live_parity_preset(**summary['config'])
    eng=Debited(load_bars(summary['year']),SCENARIOS['realistic_ecn'],cfg)
    res=eng.run([c() for c in PORTFOLIO if c.__name__ in summary['strategies']],summary['start'],summary['end_exclusive'])
    same=len(res.trades)==len(rows)
    for tr,r in zip(res.trades,rows.itertuples()):
        same=same and tr.strategy==r.strategy and eng.entry_quotes[tr.ticket]==(r.entry_time_ms,r.entry_quote_index) and eng.exit_quotes[tr.ticket]==(r.exit_time_ms,r.exit_quote_index) and abs(tr.net_pl-r.net_pl)<1e-7
    result=dict(identical_fills=bool(same),debited=total,remaining_events=len(cash_events),trades=len(res.trades),end_balance=eng.balance)
    (path/"cash_feedback_check.json").write_text(json.dumps(result,indent=2))
    assert same and not cash_events and abs(eng.balance-account['balance'])<1e-6,result
    print(summary['name'],result)


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("folder",type=Path,nargs="+")
    for path in p.parse_args().folder:
        check(path)

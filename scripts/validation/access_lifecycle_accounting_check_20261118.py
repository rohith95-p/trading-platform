"""Independent arithmetic checks for saved lifecycle outputs; not a price-path audit."""
from __future__ import annotations
from datetime import datetime,timezone
import csv
import gzip
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
FOLDERS=('access_lifecycle_2026-11-18','access_provider_calendar_2026-11-18','access_flat_clock_2026-11-18')


def check(directory):
    summary=json.loads((directory/'summary.json').read_text())
    output={'scope':'saved trace/cash arithmetic only; no independent strategy, tick or broker reconstruction',
            'phases':[],'actual_cash_received':summary['actual_cash_received']}
    assert summary['actual_cash_received']==0
    for phase in summary['phases']:
        name=phase['phase']
        all_trades=json.loads((directory/f'{name}_trades.json').read_text())
        trades=all_trades[:phase['trades']]
        cash=sum(row['net_pl'] for row in trades)
        gross_paid=sum(float(row['gross']) for row in phase['conditional_settlements'])
        assert len(trades)==phase['trades']
        assert abs(cash-phase['net_trade_cash'])<1e-7
        assert abs(5000+cash-gross_paid-float(phase['ledger_balance']))<1e-7
        with gzip.open(directory/f'{name}_observations.csv.gz','rt') as stream:
            rows=list(csv.DictReader(stream))
        assert len(rows)==phase['observations']
        times=[int(row['time']) for row in rows]
        assert times==sorted(times)
        equity=[float(row['net_liquidation_equity']) for row in rows]
        assert abs(min([5000.,*equity])-phase['minimum_sampled_net_liquidation_equity'])<1e-7
        peak=5000.; max_dd=0.
        rate=.10 if name=='evaluation' else .06
        for row in rows:
            value=float(row['net_liquidation_equity'])
            peak=max(peak,value); max_dd=max(max_dd,peak-value)
            assert abs(float(row['trailing_floor'])-peak*(1-rate))<1e-6
            if row['status']=='active':
                assert value+1e-7>=float(row['daily_floor'])
                assert value+1e-7>=float(row['trailing_floor'])
        assert abs(max_dd-phase['sampled_max_drawdown_usd'])<1e-6
        if phase['status']=='passed':
            assert float(phase['ledger_balance'])>=5150 and int(rows[-1]['positions'])==0
        output['phases'].append({'phase':name,'trades':len(trades),'observations':len(rows),
             'net_cash':cash,'ledger_balance':float(phase['ledger_balance']),
             'last_observation':times[-1],
             'last_observation_utc':datetime.fromtimestamp(times[-1],timezone.utc).isoformat(),
             'cash_identity_and_observed_floors_checked':True,
             'post_stop_engine_settlements_not_ledgered':len(all_trades)-len(trades)})
    (directory/'trace_accounting_check.json').write_text(json.dumps(output,indent=2))
    return output


def main():
    for folder in FOLDERS:
        result=check(ROOT/'research/results'/folder)
        print(json.dumps({'folder':folder,**result}))


if __name__=='__main__':
    main()

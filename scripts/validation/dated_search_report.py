"""Compare the recovered candidate family on identical calendar observations."""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from src.research.dated_results import align_results
from src.research.metrics import deflated_sharpe_ratio, expected_max_sr


def main():
    groups={}
    for path in Path('research/dated_results').glob('*.json'):
        record=json.loads(path.read_text())
        groups.setdefault(record['name'],[]).append((path.stem,record))
    pooled={}
    for name,runs in groups.items():
        series={}
        spans=[]
        for key,run in sorted(runs):
            interval=pd.date_range(run['start'],run['end'])
            if any(interval.intersection(other).size for other in spans):
                raise ValueError('Overlapping versions require explicit selection: '+name)
            spans.append(interval)
            series.update(run['series'])
        dates=pd.DatetimeIndex(sorted(set().union(*(set(s) for s in spans))))
        pooled[name]={'observation':'realized_cash_pnl','series':series,
                      'start':str(dates[0].date()),'end':str(dates[-1].date())}
        if len(dates)!=len(pd.date_range(dates[0],dates[-1])):
            raise ValueError('Discontinuous coverage: '+name)
    common_start=max(p['start'] for p in pooled.values())
    common_end=min(p['end'] for p in pooled.values())
    matrix=align_results(pooled,common_start,common_end)
    matrix=matrix.loc[matrix.index.weekday<5]/5000.
    sr=matrix.mean()/matrix.std(ddof=0)
    variance=float(sr.var(ddof=1))
    report={'start':common_start,'end':common_end,'business_days':len(matrix),
            'recovered_candidates':len(pooled),'cross_trial_sharpe_variance':variance,
            'coverage_note':'This recovered subset excludes earlier screens and prior research. The recovered count is a lower-bound sensitivity.',
            'observation_note':'Fixed-$5000 realized cash P&L, not marked-to-market account returns.',
            'correlation':matrix.corr().to_dict(),'candidates':{}}
    for name in matrix:
        a=matrix[name].to_numpy()
        report['candidates'][name]={'net':round(a.sum()*5000,2),'daily_sharpe':float(sr[name]),
            'dsr_sensitivity':{str(n):{'expected_max_sr':expected_max_sr(n,variance),
                                      'dsr':deflated_sharpe_ratio(a,n,variance)}
                               for n in (len(pooled),48,217,500)}}
    matrix.to_csv('research/registry/recovered_daily_returns.csv')
    Path('research/registry/recovered_search_report.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({k:v for k,v in report.items() if k!='correlation'},indent=2))


if __name__=='__main__':
    main()

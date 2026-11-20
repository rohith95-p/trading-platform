"""One fixed causal selection diagnostic on previously inspected intraday P&L."""
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd

ARMS = ('auction_follow','auction_fade','cot_follow','cot_fade','orb_target_1',
        'orb_target_2','gld_creations','gold_iv_premium','miners_residual',
        'paxg_flow','us_intraday_momentum')


def select_monthly(matrix, start='2023-01-01', end='2025-12-31'):
    if (not isinstance(matrix.index,pd.DatetimeIndex) or matrix.index.has_duplicates
            or not matrix.index.is_monotonic_increasing or matrix.columns.has_duplicates
            or not np.isfinite(matrix.to_numpy()).all()):
        raise ValueError('Require sorted unique finite dated observations')
    output = pd.Series(0.,index=matrix.loc[start:end].index,name='selected_cash_pnl')
    decisions = []
    # UTC periods avoid a local-calendar dependency in strategy decisions.
    months = output.index.tz_localize(None).to_period('M') if output.index.tz else output.index.to_period('M')
    for month in months.unique():
        dates = output.index[months==month]
        train = matrix.loc[matrix.index<dates[0]].tail(252)
        eligible = {}
        if len(train)==252:
            for name in sorted(matrix.columns):
                p = train[name]
                gains,losses = p.clip(lower=0).sum(),-p.clip(upper=0).sum()
                pf = gains/losses if losses else (np.inf if gains else 0.)
                sd = p.std(ddof=1)
                if (p!=0).sum()>=30 and pf>=1.3 and sd>0 and p.mean()>0:
                    eligible[name] = float(p.mean()/sd)
        chosen = max(eligible,key=eligible.get) if eligible else None
        if chosen:
            output.loc[dates] = matrix.loc[dates,chosen]
        decisions.append(dict(month=str(month),choice=chosen,training_days=len(train),
                              training_end=str(train.index[-1].date()) if len(train) else None,
                              scores=eligible))
    return output,decisions


def daily_metrics(p):
    a = np.asarray(p,dtype=float)
    positive,negative = a[a>0].sum(),-a[a<0].sum()
    equity = np.r_[5000.,5000.+a.cumsum()]
    peak = np.maximum.accumulate(equity)
    dd = peak-equity
    downside = np.sqrt(np.mean(np.minimum(a,0)**2))
    sd = a.std(ddof=1)
    net = a.sum()
    years = len(a)/252
    annual = (equity[-1]/5000)**(1/years)-1 if equity[-1]>0 else None
    dd_pct = float(np.max(dd/peak))
    return dict(observation='daily_realized_cash_pnl',days=len(a),active_days=int(sum(a!=0)),
                profitable_days=int(sum(a>0)),net_usd=float(net),
                daily_profit_factor=float(positive/negative) if negative else None,
                annualized_daily_sharpe=float(np.sqrt(252)*a.mean()/sd) if sd else None,
                annualized_daily_sortino=float(np.sqrt(252)*a.mean()/downside) if downside else None,
                omega_zero_threshold=float(positive/negative) if negative else None,
                realized_balance_max_dd_usd=float(dd.max()),realized_balance_max_dd_pct=100*dd_pct,
                recovery_factor=float(net/dd.max()) if dd.max() else None,
                calmar=annual/dd_pct if annual is not None and dd_pct else None)


def main():
    path = Path('research/registry/recovered_daily_returns.csv')
    input_bytes = path.read_bytes()
    input_key = hashlib.sha256(input_bytes).hexdigest()
    snapshot = Path('research/data/selection_inputs')/(input_key+'.csv')
    snapshot.parent.mkdir(parents=True,exist_ok=True)
    if not snapshot.exists():
        snapshot.write_bytes(input_bytes)
    full = pd.read_csv(path,index_col=0,parse_dates=True)*5000.
    matrix = full.loc[:,ARMS]
    selected,decisions = select_monthly(matrix)
    control = matrix.loc[selected.index].mean(axis=1)
    months = selected.groupby(selected.index.strftime('%Y-%m')).sum().to_numpy()
    rng = np.random.default_rng(25230)
    totals = rng.choice(months,size=(5000,len(months)),replace=True).sum(axis=1)
    def digest(p):
        return hashlib.sha256(Path(p).read_bytes()).hexdigest()
    report = dict(input_sha256=input_key,input_snapshot=str(snapshot),runner_sha256=digest(__file__),
        protocol_sha256=digest('research/registry/PREREG_MonthlyStrategySelection_2026-11-11.md'),
        caveat='Retrospective causal diagnostic on a post-hoc candidate universe; daily PF is not trade PF. No Atlas survival/payout claim.',
        candidate_arms=list(ARMS),decisions=decisions,selected=daily_metrics(selected),
        equal_allocation_diagnostic=daily_metrics(control),
        yearly={str(year):daily_metrics(p) for year,p in selected.groupby(selected.index.year)},
        month_block_bootstrap=dict(draws=5000,net_percentiles_2_5_50_97_5=np.percentile(totals,[2.5,50,97.5]).tolist(),
                                  conditional_fraction_negative=float(np.mean(totals<0))))
    output = pd.DataFrame(dict(selected_cash_pnl=selected,equal_allocation_cash_pnl=control))
    output.to_csv('research/registry/monthly_strategy_selection_daily.csv')
    Path('research/registry/monthly_strategy_selection.json').write_text(json.dumps(report,indent=2,allow_nan=False))
    print(json.dumps({k:v for k,v in report.items() if k not in ('decisions','candidate_arms')},indent=2))


if __name__=='__main__':
    main()

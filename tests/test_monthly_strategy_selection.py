import numpy as np
import pandas as pd
import pytest
from scripts.research.monthly_strategy_selection import select_monthly


def test_future_results_do_not_change_earlier_choices():
    index = pd.bdate_range('2022-01-01','2024-12-31',tz='UTC')
    a = np.where(np.arange(len(index))%4==0,-1.,2.)
    frame = pd.DataFrame(dict(a=a,b=-a),index=index)
    _,first = select_monthly(frame)
    changed = frame.copy()
    changed.loc['2024-01-01':] *= -100
    _,second = select_monthly(changed)
    # January's own outcomes must not affect its selection either.
    assert [d for d in first if d['month']<='2024-01']==[d for d in second if d['month']<='2024-01']
    assert all(d['choice']=='a' for d in first)
    assert all(d['training_end']<d['month']+'-01' for d in first)


def test_no_eligible_arm_stays_in_cash_and_ties_are_stable():
    index = pd.bdate_range('2022-01-01','2023-02-28',tz='UTC')
    zero = pd.DataFrame(dict(z=np.zeros(len(index))),index=index)
    pnl,decisions = select_monthly(zero)
    assert pnl.sum()==0 and all(d['choice'] is None for d in decisions)
    tied = pd.DataFrame(dict(z=np.ones(len(index)),a=np.ones(len(index))),index=index)
    tied.iloc[::4] = -1
    _,decisions = select_monthly(tied)
    assert all(d['choice']=='a' for d in decisions)
    with pytest.raises(ValueError):
        select_monthly(tied.iloc[::-1])

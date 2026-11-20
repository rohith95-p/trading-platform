from types import SimpleNamespace
import numpy as np
import pandas as pd
from scripts.research.public_sweep import confirmed_pivot,advance_zone,replay


def bar(o,h,l,c):
    return SimpleNamespace(open=o,high=h,low=l,close=c)


def test_pivot_requires_right_neighbors_and_zone_requires_impulse_close():
    rows = [bar(9,10,8,9) for _ in range(7)]
    rows[3] = bar(10,12,9,11)
    assert confirmed_pivot(rows,5) is None
    assert confirmed_pivot(rows,6)==(3,12,-1)
    # A bullish impulse at index 2 confirms the preceding bearish OB only at its close.
    rows = [bar(10,11,9,10),bar(10,10.5,8,9),bar(9,11,8.5,10.8)]
    search = dict(origin=1,side=1,wick=8)
    assert advance_zone(search,rows,1) is None
    assert advance_zone(search,rows,2)==(10.5,8,2)


def test_appending_future_extremes_preserves_completed_trades():
    rng = np.random.default_rng(7751)
    index = pd.date_range('2020-01-01',periods=4000,freq='15min',tz='UTC')
    c = 1500+np.cumsum(rng.normal(0,1,len(index)))
    o = np.r_[1500,c[:-1]]
    f = pd.DataFrame(dict(open=o,high=np.maximum(o,c)+rng.uniform(.2,1.5,len(index)),
                          low=np.minimum(o,c)-rng.uniform(.2,1.5,len(index)),close=c,
                          time=[int(t.timestamp()) for t in index],spread=260),index=index)
    for trend in (False,True):
        full,_ = replay(f,trend)
        prefix,_ = replay(f.iloc[:3000],trend)
        completed = [r for r in prefix if r['reason']!='boundary']
        assert completed
        assert full[:len(completed)]==completed


def test_no_impulse_bar_fill_or_pre_entry_target_credit():
    # Confirm low pivot 3 at close 6, sweep 7, bullish OB confirmation 8.
    values = [(9,10,8,9)]*7
    values[3] = (9,10,5,9)
    values += [(9,9,4,6),(6,9,5,8),(10,21,8,10),(10,12,9,10)]
    index = pd.date_range('2020-01-01 13:00',periods=len(values),freq='15min',tz='UTC')
    f = pd.DataFrame(values,columns=['open','high','low','close'],index=index)
    f['time'] = [int(t.timestamp()) for t in index]
    f['spread'] = 260
    before,_ = replay(f.iloc[:9],False)
    assert before==[]  # Confirming candle cannot fill its newly discovered OB.
    records,diagnostics = replay(f,False)
    assert diagnostics['entry_bar_targets_deferred']==1
    assert len(records)==1 and records[0]['reason']=='boundary'
    # Entry 9, end bid 10 minus .02 slippage, 2 oz, .07 commission.
    assert abs(records[0]['pnl']-1.89)<1e-9


def test_marketable_limit_receives_opening_quote_improvement_both_sides():
    values = [(9,10,8,9)]*7
    values[3] = (9,10,5,9)
    values += [(9,9,4,6),(6,9,5,8),(8,12,7.5,10),(10,12,9,10)]
    index = pd.date_range('2020-01-01 13:00',periods=len(values),freq='15min',tz='UTC')
    for side in (1,-1):
        rows = values if side==1 else [(20-o,20-l,20-h,20-c) for o,h,l,c in values]
        f = pd.DataFrame(rows,columns=['open','high','low','close'],index=index)
        f['time'] = [int(t.timestamp()) for t in index]
        f['spread'] = 260
        records,_ = replay(f,False)
        assert len(records)==1 and records[0]['reason']=='boundary'
        assert abs(records[0]['pnl']-3.37)<1e-9

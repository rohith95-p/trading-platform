import numpy as np
import pandas as pd
import pytest
from scripts.research.forecast_fill_core import prepare,replay


def test_explicit_2026_extension_preserves_prior_training_and_uses_only_past_sessions():
    index=pd.bdate_range('2004-01-01','2026-10-30',tz='UTC')+pd.Timedelta(hours=14)
    c=1000*np.exp(np.cumsum(np.random.default_rng(26).normal(.0001,.008,len(index))))
    f=pd.DataFrame(dict(open=c,high=c+5,low=c-5,close=c,spread=260,time=index.asi8//10**9),index=index)
    _,old,_=prepare(f)
    _,extended,freezes=prepare(f,last_year=2026)
    pd.testing.assert_frame_equal(old.loc[:'2025-12-31'],extended.loc[:'2025-12-31'])
    assert old.loc['2026':,'probability'].isna().all()
    assert extended.loc['2026':,'probability'].notna().any()
    assert len([r for r in freezes if r['freeze'].startswith('2026')])==2
    assert all(r['train_last_session']<r['freeze'] for r in freezes)


def test_training_freezes_and_decisions_ignore_future_prices():
    index = pd.bdate_range('2004-01-01','2019-12-31',tz='UTC')+pd.Timedelta(hours=14)
    rng = np.random.default_rng(10950)
    c = 1000*np.exp(np.cumsum(rng.normal(.0002,.01,len(index))))
    f = pd.DataFrame(dict(open=c,high=c+5,low=c-5,close=c,spread=260,
                          time=[int(t.timestamp()) for t in index]),index=index)
    _,full,_ = prepare(f)
    _,prefix,freezes = prepare(f.loc[:'2017-12-31'])
    pd.testing.assert_frame_equal(full.loc[prefix.index],prefix)
    assert freezes and all(r['train_last_session']<r['freeze'] for r in freezes)
    assert prefix.probability.notna().any()


def test_trailing_high_applies_only_after_its_session_closes():
    index = pd.to_datetime(['2020-01-02 14:00','2020-01-03 14:00'],utc=True)
    days = pd.to_datetime(['2020-01-02','2020-01-03'])
    f = pd.DataFrame(dict(open=[100,100],high=[200,101],low=[90,90],close=[100,100],
                          spread=260,session=days,time=[int(t.timestamp()) for t in index]),index=index)
    d = pd.DataFrame(dict(enter=[True,False],leave=[False,False],entry_atr=[10,10],
                          prior_atr=[10,10],prior_high=[100,200]),index=days)
    records = replay(f,d)
    assert len(records)==1 and records[0]['reason']=='stop'
    assert records[0]['time']==int(index[1].timestamp())+900
    # -.67 execution/commission, plus one calendar rollover at -1.031 for .02 lot.
    assert records[0]['pnl']==pytest.approx(-1.701)

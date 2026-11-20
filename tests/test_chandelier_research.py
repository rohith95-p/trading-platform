import numpy as np
from scripts.research.chandelier_zlsma import linreg_last,indicators,replay
from src.backtesting.costs import SCENARIOS


def candles(n):
    x=np.zeros(n,dtype=[('time','i8'),('open','f8'),('high','f8'),('low','f8'),('close','f8'),('spread','i8')])
    x['time']=np.arange(n)*60;x['open']=2000+np.sin(np.arange(n)*.3)*5
    x['close']=x['open']+.2;x['high']=x['open']+1;x['low']=x['open']-1;x['spread']=260
    return x


def test_lsma_matches_independent_polynomial_fit():
    x=np.random.default_rng(46).normal(size=130)
    actual=linreg_last(x)
    for i in (49,73,129):
        fit=np.polyfit(np.arange(50),x[i-49:i+1],1)
        assert np.isclose(actual[i],np.polyval(fit,49),atol=1e-12)


def test_ha_and_ordinary_indicator_prefix_causality():
    raw=candles(450)
    for ha in (True,False):
        full=indicators(raw,ha);prefix=indicators(raw[:333],ha)
        for key in full:np.testing.assert_allclose(full[key][:333],prefix[key],equal_nan=True)


def test_real_quote_entry_and_gap_stop_even_with_signal_candles_elsewhere():
    raw=candles(3);raw['open']=[2000,2000,1990];raw['high']=[2001,2001,1991];raw['low']=[1999,1999,1989];raw['close']=raw['open']
    bars=candles(1);bars['open']=1500;bars['close']=1500
    f=dict(entry=np.array([1]),stop=np.array([1995.]),close_long=np.array([False]),close_short=np.array([False]))
    trades,count=replay(raw,bars,f,60,0,180,SCENARIOS['realistic_ecn'])
    assert count==0 and len(trades)==1
    t=trades[0];assert np.isclose(t['entry'],2000.28)
    assert t['reason']=='gap_stop' and t['exit_time']==120
    assert np.isclose(t['exits'][0]['price'],1989.98)
    assert np.isclose(t['pnl'],2*(1989.98-2000.28)-.07)


def test_short_stop_uses_observed_ask_extreme_not_constant_open_spread():
    base=candles(3)
    raw=np.zeros(3,dtype=base.dtype.descr+[(f'ask_{k}','f8') for k in ('open','high','low','close')])
    for k in base.dtype.names:raw[k]=base[k]
    for k in ('open','high','low','close'):raw[k]=2000;raw['ask_'+k]=2000.26
    raw['ask_high'][1]=2010
    bars=candles(1)
    f=dict(entry=np.array([-1]),stop=np.array([2005.]),close_long=np.array([False]),close_short=np.array([False]))
    trades,count=replay(raw,bars,f,60,0,180,SCENARIOS['realistic_ecn'])
    assert len(trades)==1 and trades[0]['reason']=='stop'
    assert trades[0]['exit_time']==120
    assert np.isclose(trades[0]['exits'][0]['price'],2005.02)

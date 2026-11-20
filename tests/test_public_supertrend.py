import numpy as np
import pandas as pd
from scripts.research.public_supertrend import indicators,replay


def test_band_signals_are_unchanged_when_future_prices_are_removed():
    rng=np.random.default_rng(7)
    price=2000+np.cumsum(rng.normal(0,3,400))
    d=pd.DataFrame(dict(open=price,high=price+1,low=price-1,close=price,
                        spread=200,time=1600000000+3600*np.arange(400)),
                   index=pd.date_range('2020-01-01',periods=400,freq='h',tz='UTC'))
    full=indicators(d.copy())
    short=indicators(d.iloc[:250].copy())
    assert np.allclose(full.atr.iloc[:250],short.atr,equal_nan=True)
    assert np.array_equal(full.signal.iloc[:250],short.signal)


def test_short_stop_fills_at_gap_ask_and_adverse_slip():
    d=pd.DataFrame(dict(time=[1600000000,1600003600],open=[2000.,2010.],high=[2001.,2011.],
        low=[1999.,2009.],close=[2000.,2010.],spread=[200.,200.],signal=[-1,0],atr_entry=[1.,1.]))
    result=replay(d)
    # Sell at 1999.98, gap stop cover at 2010.20 + .02, two ounces, .07 commission.
    assert len(result)==1
    assert abs(result[0][1]-(-20.55))<1e-8

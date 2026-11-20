import numpy as np
import pandas as pd
import pytest
from scripts.research.vwap_ema import indicators,replay


@pytest.mark.parametrize('side',[1,-1])
def test_adverse_ema_close_exits_at_following_executable_open(side):
    times = pd.date_range('2020-01-02 14:00',periods=3,freq='15min',tz='UTC')
    rows = ([(100,101,98,100),(100,100.5,98.9,99),(98,99,97,98)] if side==1
            else [(100,102,99,100),(100,101.1,99.5,101),(102,103,101,102)])
    f = pd.DataFrame(rows,index=times,columns=['open','high','low','close'])
    f['time'] = [int(t.timestamp()) for t in times]
    f['spread'],f['atr'],f['ema50'],f['ema20'] = 260,1.,100.,100.
    f['signal'] = [side,0,0]
    records,ambiguous = replay(f,'github_core')
    assert len(records)==1
    assert records[0]['reason']=='close_signal_or_session'
    assert records[0]['time']==int(times[2].timestamp())
    assert records[0]['pnl']==pytest.approx(-4.67)
    assert ambiguous==0


@pytest.mark.parametrize('arm',['github_core','paper_core'])
def test_indicators_are_causal_and_paper_session_resets(arm):
    times = pd.date_range('2020-01-01',periods=400,freq='15min',tz='UTC')
    c = 100+np.sin(np.arange(400)/10)
    f = pd.DataFrame(dict(open=c-.1,high=c+.3,low=c-.4,close=c,
                          tick_volume=100+np.arange(400)%30),index=times)
    full = indicators(f,arm)
    prefix = indicators(f.iloc[:300],arm)
    pd.testing.assert_frame_equal(full.iloc[:300],prefix)
    if arm=='paper_core':
        first = full.between_time('13:30','13:30')
        np.testing.assert_allclose(first.vwap,(first.high+first.low+first.close)/3)
        assert full.between_time('20:00','20:00').vwap.isna().all()

import numpy as np
import pandas as pd
import pytest
from scripts.research.turtle_s2 import prepare,replay
from src.backtesting.costs import SCENARIOS


def test_channels_use_only_closed_sessions():
    index = pd.bdate_range('2020-01-01',periods=80,tz='UTC')+pd.Timedelta(hours=14)
    c = np.arange(80)+100.
    f = pd.DataFrame(dict(open=c,high=c+1,low=c-1,close=c,spread=260,
                          time=[int(t.timestamp()) for t in index]),index=index)
    full = prepare(f)
    prefix = prepare(f.iloc[:65])
    pd.testing.assert_frame_equal(full.iloc[:65],prefix)
    assert full.entry_high.iloc[55]==pytest.approx(155.001)


@pytest.mark.parametrize('side',[1,-1])
def test_breakout_and_gap_stop_use_executable_quotes(side):
    index = pd.date_range('2020-01-02 14:00',periods=2,freq='15min',tz='UTC')
    values = [(100,102,100,101),(90,92,89,90)] if side==1 else [(100,100,98,99),(110,111,109,110)]
    f = pd.DataFrame(values,columns=['open','high','low','close'],index=index)
    f['time'] = [int(t.timestamp()) for t in index]
    f['spread'],f['n_value'] = 260,2.
    f['entry_high'],f['entry_low'],f['exit_high'],f['exit_low'] = 101.,99.,120.,80.
    records,diag = replay(f,1,SCENARIOS['realistic_ecn'])
    assert len(records)==1 and records[0]['reason']=='stop_or_channel'
    assert records[0]['pnl']==pytest.approx(-22.67)
    assert diag['unit_fills']==1


def test_pyramid_caps_units_and_liquidates_all_at_gap_quote():
    index = pd.date_range('2020-01-02 14:00',periods=3,freq='15min',tz='UTC')
    f = pd.DataFrame([(100,102,100,101),(102,106,102,105),(90,91,89,90)],
                     columns=['open','high','low','close'],index=index)
    f['time'] = [int(t.timestamp()) for t in index]
    f['spread'],f['n_value'] = 260,2.
    f['entry_high'],f['entry_low'],f['exit_high'],f['exit_low'] = 101.,99.,120.,80.
    records,diag = replay(f,4,SCENARIOS['realistic_ecn'])
    assert len(records)==1 and records[0]['units']==4
    assert diag['unit_fills']==4
    assert records[0]['pnl']==pytest.approx(-106.04)

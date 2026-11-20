import numpy as np
from scripts.research.genesis_prepare import aggregate_m5
from scripts.research.genesis_management import ManagementState,management_actions
from scripts.research.genesis_backtest import simulate_trade,learning_multiplier,sampled_equity
from src.backtesting.costs import SCENARIOS
import pytest


def test_m5_aggregation_rejects_incomplete_group():
    dtype = [('time','i8'),('open','f8'),('high','f8'),('low','f8'),('close','f8'),('spread','i8')]
    raw = np.zeros(10,dtype=dtype)
    raw['time'] = np.arange(10)*60
    raw['open'],raw['close'],raw['high'],raw['low'] = 100,101,102,99
    full = aggregate_m5(raw)
    assert list(full['time'])==[0,300]
    missing = aggregate_m5(np.delete(raw,2))
    assert list(missing['time'])==[300]


def test_rebasing_original_risk_changes_partial_trigger():
    original = ManagementState(1,2000,2000.1,2000.1,2005.1,2,5,False,True)
    corrected = ManagementState(1,2000,1990,2000.1,2005.1,2,5,False,True)
    assert any(a['action']=='PARTIAL_CLOSE' for a in management_actions(original)['actions'])
    assert not any(a['action']=='PARTIAL_CLOSE' for a in management_actions(corrected)['actions'])


def trade_bars(values):
    dtype = [('time','i8'),('open','f8'),('high','f8'),('low','f8'),('close','f8'),('spread','i8')]
    raw = np.zeros(len(values),dtype=dtype)
    for i,(o,h,l,c) in enumerate(values):
        raw[i] = (1577973600+60*i,o,h,l,c,260)
    return raw


def test_static_gap_fill_has_correct_quote_and_timestamp():
    raw = trade_bars([(100,101,99,100),(100,101,99,100),(90,91,89,90)])
    record = simulate_trade(raw,0,dict(direction='BUY',sl_distance=2.,tp_distance=4.),
                            SCENARIOS['realistic_ecn'],'static',np.ones(3))
    assert record['pnl']==pytest.approx(-20.67)
    assert record['exit_time']==raw['time'][2]


def test_partial_and_final_exit_sum_one_trade_with_proportional_fees():
    raw = trade_bars([(100,100,99.5,100),(102.5,103,102.1,102.5),(102,102.1,101.8,102)])
    record = simulate_trade(raw,0,dict(direction='BUY',sl_distance=1.,tp_distance=10.),
                            SCENARIOS['realistic_ecn'],'constant_initial_risk',np.ones(3))
    assert record['partials']==1
    assert record['pnl']==pytest.approx(3.83)
    equity = sampled_equity(raw,[record],SCENARIOS['realistic_ecn'])
    assert equity['sampled_minimum_equity_usd']<5000.


def test_learning_uses_minimum_closed_history_and_bounded_r():
    assert learning_multiplier([(10.,100.)]*9)==1.
    assert learning_multiplier([(10.,100.)]*10)==pytest.approx(1.5)
    assert learning_multiplier([(-10.,-100.)]*10)==pytest.approx(.5)

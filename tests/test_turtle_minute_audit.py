import numpy as np
import pandas as pd
import pytest
from src.backtesting.costs import SCENARIOS
from scripts.validation.turtle_minute_audit import opening_equity,account_scenario,sequential_scenario


@pytest.mark.parametrize('side',[1,-1])
def test_opening_equity_charges_entry_fee_then_reconciles_final_cash(side):
    index = pd.date_range('2020-01-02 14:00',periods=3,freq='min',tz='UTC')
    t = np.array([int(x.timestamp()) for x in index])
    f = pd.DataFrame(dict(time=t,open=100.,close=100.,spread=260),index=index)
    price = 100.28 if side==1 else 99.98
    records = [dict(time=int(t[-1])+60,pnl=-.67,side=side,fills=[dict(price=price,time=int(t[0]))])]
    times,realized,floating,active = opening_equity(f,records,SCENARIOS['realistic_ecn'])
    assert list(active)==[0,1,1,0]
    assert floating[1]==pytest.approx(-.595)
    assert floating[-1]==0 and realized[-1]==pytest.approx(-.67)
    assert times[-1]==t[-1]+60


def test_funded_hard_floor_precedes_protector_diagnostic():
    times = np.array([1577973600,1577973660])
    result = account_scenario(times,np.array([0.,-300.]),np.array([0.,-100.]),
                              np.array([0,1]),[dict(time=int(times[1]),pnl=-300.)],'funded')
    assert result['status']=='breached'
    assert result['hypothetical_cash_total']==0


def test_protector_stops_before_reusing_invalid_unmodified_trade_path():
    times = np.array([1577973600,1577973660,1577973720])
    result = account_scenario(times,np.zeros(3),np.array([0.,-100.,1000.]),np.array([0,1,1]),[],'funded')
    assert result['status']=='protector_liquidation_required'
    assert result['stopped_at']==times[1]


def test_funded_phase_does_not_inherit_evaluation_profit():
    times = np.array([1577973600,1577973660,1577973720])
    records = [dict(time=int(times[1]),entry_time=int(times[0]),pnl=200.),
               dict(time=int(times[2]),entry_time=int(times[1]),pnl=40.)]
    result = sequential_scenario(times,np.array([0.,200.,240.]),np.zeros(3),np.zeros(3),records,
                                 dict(status='passed',stopped_at=int(times[1])))
    assert result['balance_usd']==pytest.approx(5040.)
    assert result['hypothetical_cash_total']==0

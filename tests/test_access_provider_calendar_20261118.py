"""Provider-calendar assumption is distinct from missing active-market quotes."""
from datetime import datetime, timezone
from types import SimpleNamespace

import numpy as np
import pytest

from scripts.validation.access_provider_calendar_20261118 import (
    market_state, quote_minute_expected, scheduled_closed_gap, CalendarPolicy, CalendarEngine,
)
from scripts.validation.access_lifecycle_20261118 import IndeterminatePath
from src.backtesting.costs import SCENARIOS
from src.backtesting.engine import EngineConfig
from tests.test_access_lifecycle_20261118 import fake_engine
from tests.test_engine_live_parity import make_bars, T0


def stamp(day, hour, minute=0, second=0):
    return int(datetime(2026, 7, day, hour, minute, second, tzinfo=timezone.utc).timestamp())


@pytest.mark.parametrize("ts,state", [
    (stamp(6,20,57,59),"open"), (stamp(6,20,58),"closed"),
    (stamp(6,22,0,29),"closed"), (stamp(6,22,0,30),"close_only"),
    (stamp(6,22,1,59),"close_only"), (stamp(6,22,2),"open"),
    (stamp(10,20,58),"closed"), (stamp(11,12),"closed"),
    (stamp(12,22,1,29),"closed"), (stamp(12,22,1,30),"close_only"),
    (stamp(12,22,4,59),"close_only"), (stamp(12,22,5),"open"),
])
def test_exact_published_summer_schedule_boundaries(ts,state):
    assert market_state(ts)==state


def test_first_partial_close_only_minute_can_have_quote_but_not_new_entry():
    assert quote_minute_expected(stamp(6,22,0))
    assert market_state(stamp(6,22,0)) != "open"
    assert scheduled_closed_gap(stamp(6,20,58),stamp(6,22,0))
    assert not scheduled_closed_gap(stamp(6,20,58),stamp(6,22,1))


def engine_with_calendar_quotes():
    bars=make_bars(days=2)
    bars.m1=bars.m1[np.array([quote_minute_expected(int(t)) for t in bars.m1['time']])]
    config=EngineConfig(sizing_mode="fixed", fixed_lots=.02, record_equity_samples=True,
                        entry_delay_sec=0, m1_policy="coarse")
    policy=CalendarPolicy("evaluation",T0)
    return CalendarEngine(bars,SCENARIOS['frictionless'],config,lifecycle_policy=policy)


def test_partial_block_returns_thirteen_real_observations_not_coarse_prices():
    engine=engine_with_calendar_quotes()
    start=T0+20*3600+45*60
    observed=engine._m1_slice(start,start+900)
    assert len(observed)==13
    assert list(observed['time'])==list(range(start,start+13*60,60))
    assert engine.diag['bars_without_m1']==0
    closed=engine._m1_slice(T0+21*3600,T0+21*3600+900)
    assert closed is not None and len(closed)==0


def test_unexpected_active_missing_minute_still_refuses():
    engine=engine_with_calendar_quotes()
    start=T0+12*3600
    engine.m1=engine.m1[engine.m1['time']!=start+60]
    engine._m1_t=engine.m1['time']
    with pytest.raises(IndeterminatePath,match='missing_active'):
        engine._m1_slice(start,start+900)


def test_quotes_during_assumed_closed_time_refuse_clock_mismatch():
    engine=engine_with_calendar_quotes()
    start=T0+21*3600
    extra=engine.m1[:1].copy(); extra['time']=start
    engine.m1=np.sort(np.concatenate([engine.m1,extra]),order='time')
    engine._m1_t=engine.m1['time']
    with pytest.raises(IndeterminatePath,match='contradict'):
        engine._m1_slice(start,start+900)


def test_close_only_entry_refused_before_any_risk_or_fill_method():
    engine=engine_with_calendar_quotes()
    assert engine._open('TEST',1,True,4000.,stamp(6,22,1),None,None,None,None) is None
    assert engine.close_only_entry_blocks==1
    assert engine.positions==[]


def test_known_daily_closed_gap_retains_exposure_without_invented_marks():
    start,end=stamp(6,20,58),stamp(6,22,0)
    policy=CalendarPolicy('evaluation',start)
    policy.last_positions=1
    position=SimpleNamespace(lots=.02,is_buy=True,entry_time=start-60)
    engine=fake_engine(positions=[position],phase='open',ts=end)
    assert not policy.observe(engine,end)
    event=next(e for e in policy.events if e['kind']=='calendar_assumed_closed_gap')
    assert event['from']==start and event['to']==end and event['no_interpolated_marks']
    assert policy.observations==1


def test_unverified_active_gap_refuses_even_when_flat():
    start,end=stamp(6,12),stamp(6,13)
    policy=CalendarPolicy('evaluation',start)
    with pytest.raises(IndeterminatePath,match='unverified_active'):
        policy.observe(fake_engine(phase='open',ts=end),end)

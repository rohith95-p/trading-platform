"""Flat missing quotes may advance only after a fixed-strategy impossibility proof."""
from types import SimpleNamespace

import numpy as np
import pytest

from scripts.validation import access_flat_clock_20261118 as flat
from scripts.validation.access_lifecycle_20261118 import IndeterminatePath
from scripts.validation.access_provider_calendar_20261118 import quote_minute_expected
from src.backtesting.costs import SCENARIOS
from src.backtesting.engine import EngineConfig
from tests.test_engine_live_parity import make_bars,T0,RATE_DTYPE


def make_engine():
    bars=make_bars(days=2)
    bars.m1=bars.m1[np.array([quote_minute_expected(int(t)) for t in bars.m1['time']])]
    cfg=EngineConfig(sizing_mode='fixed',fixed_lots=.02,record_equity_samples=True,
                     entry_delay_sec=0,m1_policy='coarse',live_exec_order=True,history_bars=32)
    policy=flat.FlatClockPolicy('evaluation',T0)
    return flat.FlatClockEngine(bars,SCENARIOS['frictionless'],cfg,lifecycle_policy=policy)


def remove_minutes(engine,minutes):
    engine.m1=engine.m1[~np.isin(engine.m1['time'],minutes)]
    engine._m1_t=engine.m1['time']


def test_real_fixed_strategies_have_no_signal_or_pending_path_outside_clock():
    from src.strategies.portfolio_atlas import PORTFOLIO
    rng=np.random.default_rng(123)
    for label in range(0,86400,900):
        if label==25200 or 43200<=label<57600:
            continue
        for level in (500.,4000.,9000.):
            rates=np.zeros(400,dtype=RATE_DTYPE)
            rates['time']=T0+label+900*(np.arange(400)-398)
            rates['open']=level+rng.uniform(-10,10,400)
            rates['close']=level+rng.uniform(-10,10,400)
            rates['high']=np.maximum(rates['open'],rates['close'])+50
            rates['low']=np.minimum(rates['open'],rates['close'])-50
            for cls in PORTFOLIO:
                strategy=cls()
                assert strategy.execute_immediately and strategy.edge_trigger
                assert strategy.evaluate(rates) is None
                strategy.set_pending(SimpleNamespace(),int(rates['time'][-2]))
                assert strategy.check_pending_confirmation(rates) is None


def test_flat_2200_missing_minutes_keep_all_eleven_observed_quotes():
    engine=make_engine(); start=T0+22*3600
    missing=list(range(start,start+240,60)); remove_minutes(engine,missing)
    observed=engine._m1_slice(start,start+900)
    assert len(observed)==11
    assert list(observed['time'])==list(range(start+240,start+900,60))
    assert engine.flat_inert_blocks[0]['missing_minutes']==missing
    assert engine.flat_inert_blocks[0]['actual_signal_bar']%86400>=16*3600
    assert engine.flat_inert_blocks[0]['no_prices_invented']


@pytest.mark.parametrize('hour,minute',[(7,15),(12,0),(13,0),(15,45),(0,0),(23,59)])
def test_missing_candidate_or_midnight_minutes_cannot_be_waived(hour,minute):
    engine=make_engine(); start=T0+hour*3600+(minute//15)*900
    remove_minutes(engine,[T0+hour*3600+minute*60])
    with pytest.raises(IndeterminatePath,match='not_proven'):
        engine._m1_slice(start,start+900)


def test_no_open_risk_can_be_hidden_by_flat_exception():
    engine=make_engine(); start=T0+22*3600; remove_minutes(engine,[start])
    engine.positions=[object()]
    with pytest.raises(IndeterminatePath,match='not_proven'):
        engine._m1_slice(start,start+900)


def test_stale_candidate_clock_view_refuses_even_at_2200():
    engine=make_engine(); start=T0+22*3600
    keep=(engine.m15['time']<=T0+13*3600)|(engine.m15['time']>=start)
    engine.m15=engine.m15[keep]; engine._m15_t=engine.m15['time']
    remove_minutes(engine,[start])
    with pytest.raises(IndeterminatePath,match='not_proven'):
        engine._m1_slice(start,start+900)


def test_dropped_candidate_M15_block_cannot_skip_available_M1_quotes():
    engine=make_engine(); start=T0+13*3600
    engine.m15=engine.m15[engine.m15['time']!=start]; engine._m15_t=engine.m15['time']
    policy=engine.lifecycle_policy; policy.last_seen=start
    engine.current_block_start=start+900
    engine.equity_samples=[{'time':start+900,'phase':'open'}]
    with pytest.raises(IndeterminatePath,match='available_quotes'):
        policy.observe(engine,start+900)


def test_drop_offclock_M15_also_cannot_discard_real_quotes():
    engine=make_engine(); start=T0+22*3600
    engine.m15=engine.m15[engine.m15['time']!=start]; engine._m15_t=engine.m15['time']
    policy=engine.lifecycle_policy; policy.last_seen=start
    engine.current_block_start=start+900
    engine.equity_samples=[{'time':start+900,'phase':'open'}]
    with pytest.raises(IndeterminatePath,match='available_quotes'):
        policy.observe(engine,start+900)


def test_fixed_source_lock_detects_unreviewed_changes(monkeypatch):
    monkeypatch.setattr(flat,'digest',lambda path:'changed')
    with pytest.raises(ValueError,match='Frozen source changed'):
        flat.verify_source_lock()


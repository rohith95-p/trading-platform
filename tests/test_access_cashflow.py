from types import SimpleNamespace

import pytest
from src.backtesting.access import AccessAccount
from tests.test_engine_live_parity import make_bars, Fire, run, C_NY, DAY


def test_two_cash_payouts_then_loss():
    monday = 1704067200
    account = AccessAccount('funded', monday)
    engine = SimpleNamespace(balance=5000., positions=[], trades=[], stub=SimpleNamespace(),
                             floating_pl=lambda: 0.)
    for offset in (24,25,28,38,39,42):
        ts = monday + offset*86400
        engine.balance += 40.
        engine.trades.append(SimpleNamespace(exit_time=ts, net_pl=40.))
        assert not account.observe(engine, ts)
    assert [r['cash'] for r in account.payouts] == [100.,100.]
    assert engine.balance == pytest.approx(5000+240-2*111.11)
    engine.balance -= 50
    assert not account.observe(engine, ts+60)
    assert account.peak*(1-account.trailing_rate) < engine.balance
    assert engine.balance == pytest.approx(4967.78)


@pytest.mark.parametrize('up', [True, False])
def test_directional_positive_and_random_side_controls(up):
    # The planted direction becomes visible in the signal candle. Subsequent
    # prices continue in that direction. A balanced random-side benchmark
    # has two equally likely outcomes; enumerate both rather than draw seeds.
    sign = 1 if up else -1
    bars = make_bars(price_fn=lambda t: 4000+sign*min(10,max(0,(t-C_NY)/900)))
    outcomes = []
    for side in (True, False):
        _, result = run(bars,[Fire(candles=[C_NY], is_buy=side, sl_atr_mult=2.,tp_atr_mult=2.)],
                        a=DAY,b=C_NY+7200)
        assert len(result.trades) == 1
        outcomes.append(result.trades[0].net_pl)
    assert outcomes[0 if up else 1] > 0
    assert outcomes[1 if up else 0] < 0

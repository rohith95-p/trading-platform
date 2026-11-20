import pandas as pd
import pytest
from scripts.research.prior_day_breakout import replay


@pytest.mark.parametrize('side,expected',[(1,-44.67),(-1,-26.67)])
def test_breakout_uses_next_open_and_executable_gap_stop(side,expected):
    # January server time = UTC+2. Two complete prior days set 100/90 levels.
    times = pd.to_datetime(['2020-01-01 00:00','2020-01-02 00:00',
                            '2020-01-02 23:00','2020-01-02 23:15','2020-01-02 23:30'],utc=True)
    rows = [(95,100,90,95),(95,100,90,95)]
    rows += ([(99,102,98,101),(102,103,101,102),(80,81,79,80)] if side == 1
             else [(91,92,88,89),(88,89,87,88),(101,102,100,101)])
    f = pd.DataFrame(rows,index=times,columns=['open','high','low','close'])
    f['time'] = [int(t.timestamp()) for t in times]
    f['spread'] = 260
    result, ambiguous = replay(f)
    assert len(result) == 1
    assert result[0]['reason'] == 'stop'
    assert result[0]['pnl'] == pytest.approx(expected)
    assert ambiguous == 0
    # Changing later daily extremes cannot change the already executed trade.
    future = f.iloc[-1:].copy()
    future.index += pd.Timedelta(minutes=15)
    future['time'] += 900
    future['high'] = 1000
    future['low'] = 1
    extended, _ = replay(pd.concat([f,future]))
    assert extended[0] == result[0]

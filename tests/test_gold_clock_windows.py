import pandas as pd
import pytest
from scripts.research.gold_clock_windows import schedule,replay
from src.backtesting.costs import SCENARIOS


def test_london_overnight_deadline_follows_weekend_dst_change():
    index = pd.to_datetime(['2024-03-29 15:15','2024-04-01 09:30'],utc=True)
    entry,due = schedule(index,'london_overnight_long')
    assert list(entry)==[0]
    assert due[0]==int(index[1].timestamp())  # Monday10:30BST =09:30UTC.


def test_missing_exit_quote_keeps_position_and_charges_funding():
    index = pd.to_datetime(['2024-01-02 00:15','2024-01-02 07:45','2024-01-03 08:00'],utc=True)
    f = pd.DataFrame(dict(time=[int(t.timestamp()) for t in index],open=100.,close=100.,spread=260),index=index)
    records = replay(f,'asia_long',SCENARIOS['realistic_ecn'])
    assert len(records)==1
    assert records[0]['delayed_seconds']==86400
    assert records[0]['swap']==pytest.approx(-1.031)
    assert records[0]['pnl']==pytest.approx(-1.701)

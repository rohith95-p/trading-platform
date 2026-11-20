import numpy as np
import pytest
from src.backtesting.costs import SCENARIOS
from scripts.research.post_bls_reaction import release_from_url,simulate


def test_official_date_parser_uses_eastern_dst():
    winter = release_from_url('https://www.bls.gov/news.release/archives/empsit_03082024.htm')
    summer = release_from_url('https://www.bls.gov/news.release/archives/cpi_03122024.htm')
    assert winter['release_utc']=='2024-03-08T13:30:00+00:00'
    assert summer['release_utc']=='2024-03-12T12:30:00+00:00'
    with pytest.raises(ValueError):
        release_from_url('https://example.com/cpi_03122024.htm')


def test_time_exit_ignores_later_intraminute_extremes_and_short_uses_ask():
    dtype = [('time','i8'),('open','f8'),('high','f8'),('low','f8'),('close','f8'),('spread','i8')]
    w = np.zeros(61,dtype=dtype)
    w['time'] = 1600000000+60*np.arange(61)
    w['open'],w['close'],w['high'],w['low'],w['spread'] = 100,100,101,99,260
    w['high'][60],w['low'][60] = 1000,1
    for side in (-1,1):
        result = simulate(w,side,SCENARIOS['realistic_ecn'])
        assert result['reason']=='time'
        assert result['exit_time']==w['time'][60]
        assert result['pnl']==pytest.approx(-.67)

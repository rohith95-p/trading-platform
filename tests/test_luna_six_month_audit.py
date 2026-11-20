import numpy as np
import pandas as pd

from scripts.research import luna_six_month_audit as audit


def test_unrealized_daily_breach_precedes_profitable_close(monkeypatch):
    start = pd.Timestamp("2026-05-01", tz="UTC")
    ts = int(start.timestamp())
    deals = [
        dict(ts=ts+1, symbol="XAUUSDm", side="buy", action="in", volume=.10, price=4500.,
             profit=0., fee=0., swap=0., balance=5000.),
        dict(ts=ts+4, symbol="XAUUSDm", side="sell", action="out", volume=.10, price=4515.,
             profit=150., fee=0., swap=0., balance=5150.),
    ]
    times = (ts + np.arange(5))*1000
    # Exactly $4,750 is still on the floor. The next quote breaks it.
    bid = np.array([4500.,4499.,4475.,4474.9,4515.])
    monkeypatch.setattr(audit, "quote_chunks", lambda *args: [(times,bid,bid+.2)])
    result = audit.audit_ledger({},deals,"eval",start+pd.Timedelta(days=1),start)
    assert result["first_event"] == "daily"
    assert result["events"]["daily"]["time"] == audit.stamp(times[3])
    assert result["events"]["daily"]["balance"] == 5000
    assert result["events"]["daily"]["equity"] == 4749
    assert result["events"]["target"]["time"] == audit.stamp(times[4])


def test_hedged_books_pay_both_exit_spreads_and_settle_to_report_balance():
    def deal(action, side, balance, price, profit, time):
        return dict(ts=time, volume=.01, action=action, side=side, price=price, fee=-.02,
                    swap=0., profit=profit, balance=balance)
    deals = [deal("in","buy",4999.98,2000.,0.,1),deal("in","sell",4999.96,2002.,0.,2),
             deal("out","sell",5000.94,2001.,1.,3),deal("out","buy",5001.42,2001.5,.5,4)]
    _, long_oz, short_oz, cash, balance = audit.portfolio_states(deals)
    assert long_oz.tolist() == [0,1,1,0,0]
    assert short_oz.tolist() == [0,0,1,1,0]
    assert abs(cash[2] + long_oz[2]*2001 - short_oz[2]*2001.5 - 5001.46) < 1e-8
    assert cash[-1] == balance[-1] == 5001.42

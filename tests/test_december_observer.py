from datetime import datetime, timezone
from types import SimpleNamespace

import numpy as np

from scripts.december_observer import START, capture_hour, inspect, valid_rates


def test_damaged_and_duplicate_rates_are_blocked():
    dtype = [(name, "f8") for name in ("time", "open", "high", "low", "close", "tick_volume")]
    rates = np.array([(1, 10, 11, 9, 10, 1), (2, 10, 11, 9, 10, 1)], dtype=dtype)
    assert valid_rates(rates, 2)
    rates["time"][1] = 1
    assert not valid_rates(rates, 2)
    rates["time"][1] = 2
    rates["close"][1] = np.nan
    assert not valid_rates(rates, 2)


def test_real_account_is_refused_before_market_calls():
    api = SimpleNamespace(account_info=lambda: SimpleNamespace(trade_mode=2),
                          terminal_info=lambda: SimpleNamespace(connected=True))
    assert inspect(api, datetime.now(timezone.utc), 123, "Expected-Demo", 15, 16408) == {
        "status": "demo_identity_mismatch"
    }


def test_capture_keeps_duplicate_ms_and_excludes_next_hour(tmp_path):
    lo = START * 1000
    raw = np.array([(lo + 3, 2200., 2200.1), (lo + 3, 2200., 2200.2),
                    (lo + 3_600_000, 2201., 2201.1)],
                   dtype=[("time_msc", "i8"), ("bid", "f8"), ("ask", "f8")])
    api = SimpleNamespace(copy_ticks_range=lambda *args: raw)
    assert capture_hour(api, tmp_path, START, 0) == 2
    rows = np.load(tmp_path / f"{START}.npy", allow_pickle=False)
    assert rows["time_msc"].tolist() == [lo + 3, lo + 3]
    assert rows["ask"].tolist() == [2200.1, 2200.2]

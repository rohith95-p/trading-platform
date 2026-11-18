"""Independent protective-fill arithmetic; deliberately imports no engine code."""
import numpy as np


def first_replayed_minute(times, entry_time, config=None):
    config = config or {}
    include_entry = (config.get("walk_entry_bar_m1", False)
                     and config.get("entry_delay_sec", 0) == 0)
    return int(np.searchsorted(times, (entry_time // 60) * 60,
                               side="left" if include_entry else "right"))


def protective_fill(trade, bid_open, spread_price, slip, config, *, both=False):
    """Expected fill given known hit type, optionally resolving a co-touch."""
    reason = trade["exit_reason"]
    if both:
        reason = "TP" if config.get("ambiguous_resolution", "sl_first") == "tp_first" else "SL"
    if reason == "TP":
        return float(trade["tp"]), reason
    stop = float(trade["sl"])
    if config.get("gap_fill_stops", False):
        stop = min(stop, bid_open) if trade["is_buy"] else max(stop, bid_open + spread_price)
    return stop + (-slip if trade["is_buy"] else slip), "SL"


def swap_charge(trade, costs, point, value_per_price):
    if not costs.get("enable_swap", True):
        return 0.
    offset = costs.get("rollover_hour_utc", 0.) * 3600
    first = int((trade["entry_time"] - offset) // 86400) + 1
    last = int((trade["exit_time"] - offset) // 86400)
    units = max(0, last - first + 1)
    triple = costs.get("triple_swap_weekday")
    if triple is not None:
        units += 2 * sum((day + 3) % 7 == triple for day in range(first, last + 1))
    points = costs.get("swap_long_points", -515.5) if trade["is_buy"] else costs.get("swap_short_points", 0.)
    return units * points * point * value_per_price * trade["lots"]

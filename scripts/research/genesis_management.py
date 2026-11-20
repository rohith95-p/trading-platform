"""Pure port of reviewed TradeManager actions; verified separately against bytecode."""
from dataclasses import dataclass


@dataclass
class ManagementState:
    side: int
    entry: float
    initial_stop: float
    stop: float
    price: float
    atr: float
    peak: float=0.
    partial: bool=False
    breakeven: bool=False


def management_actions(t):
    profit = t.side*(t.price-t.entry)
    peak = max(t.peak,profit)
    risk = abs(t.entry-t.initial_stop)
    r = profit/risk if risk>0 else 0.
    peak_r = peak/risk if risk>0 else 0.
    actions = []
    if risk>0 and profit<=-1.5*risk:
        return dict(peak=peak,actions=[dict(action='CLOSE_FULL',new_sl=0.,close_percent=0.)])
    if not t.partial and r>=2:
        actions.append(dict(action='PARTIAL_CLOSE',new_sl=0.,close_percent=50.))
    candidates = []
    if peak_r>=1:
        candidate = t.entry+t.side*.8*peak
        if t.side*(candidate-t.stop)>0:
            candidates.append(candidate)
    if r>=1.5:
        candidate = t.price-t.side*t.atr
        if t.side*(candidate-t.stop)>0:
            candidates.append(candidate)
    if not t.breakeven and r>=.5:
        candidates.append(t.entry+t.side*.1)
    if candidates:
        best = max(candidates) if t.side==1 else min(candidates)
        if t.side*(best-t.stop)>0:
            actions.append(dict(action='MODIFY_SL',new_sl=round(best,5),close_percent=0.))
    return dict(peak=peak,actions=actions)

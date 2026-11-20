"""Access cash-flow scenario for the $5K program, sampled at simulated minutes."""
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from src.atlas.rules import payout_eligibility


class AccessAccount:
    def __init__(self, phase, start, balance=5000., target_cash=100., split=.9):
        if phase not in ('evaluation', 'funded') or balance <= 0 or target_cash <= 0 or not 0 < split <= 1:
            raise ValueError('Invalid Access scenario')
        self.phase = phase
        self.anchor = self.peak = balance
        self.daily_rate, self.trailing_rate = (.05, .10) if phase == 'evaluation' else (.03, .06)
        self.daily_floor = balance * (1-self.daily_rate)
        self.day = start // 86400
        self.next_request = start + 28*86400
        self.gross = float((Decimal(str(target_cash))/Decimal(str(split))).quantize(Decimal('.01'), rounding=ROUND_HALF_UP))
        self.split = split
        self.days = defaultdict(float)
        self.seen = 0
        self.payouts = []
        self.status = 'active'
        self.finished_at = None

    def observe(self, engine, ts):
        equity = engine.balance + engine.floating_pl()
        day = ts // 86400
        if day != self.day:
            self.day = day
            self.daily_floor = equity*(1-self.daily_rate)
        self.peak = max(self.peak, equity)
        for trade in engine.trades[self.seen:]:
            self.days[trade.exit_time//86400] += trade.net_pl
        self.seen = len(engine.trades)
        if equity < max(self.daily_floor, self.peak*(1-self.trailing_rate)):
            self.status = 'breached'
        elif self.phase == 'evaluation':
            if not engine.positions and engine.balance >= self.anchor*1.03:
                self.status = 'passed'
        elif not engine.positions and ts >= self.next_request and engine.balance-self.anchor >= self.gross:
            profit = sum(self.days.values())
            eligible = payout_eligibility([v*100/self.anchor for v in self.days.values()],
                                          profit*100/self.anchor, cycle_profit_usd=profit)
            if eligible.eligible and datetime.fromtimestamp(ts, timezone.utc).weekday() < 5:
                engine.balance -= self.gross
                engine.stub.balance = engine.balance
                self.daily_floor -= self.gross
                self.peak = self.anchor = engine.balance
                self.days.clear()
                self.next_request = ts + 14*86400
                self.payouts.append(dict(time=ts, gross=self.gross, cash=round(self.gross*self.split,2),
                                         remaining_balance=engine.balance))
        if self.status != 'active':
            self.finished_at = ts
            return True
        return False

"""Experimental Access cash ledger, frozen to public rules read 2026-11-18.

No production imports, price simulation, broker binding or payout approval model.
Callers supply after-cost closed P&L and every relevant equity observation. Missing
ticks can hide breaches. Crossing midnight requires the actual midnight equity;
the first observation of a later day is deliberately not used as a substitute.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP


CENT = Decimal("0.01")
DAY = 86400


def amount(value) -> Decimal:
    result = Decimal(str(value))
    if not result.is_finite():
        raise ValueError("amount must be finite")
    return result


@dataclass(frozen=True)
class AccessRuleProfile:
    version: str = "public-access-2026-11-18-experimental"
    source_date: str = "2026-11-18"
    source_urls: tuple[str, ...] = (
        "https://help.atlasfunded.com/access",
        "https://help.atlasfunded.com/max-drawdown",
        "https://help.atlasfunded.com/daily-loss",
        "https://help.atlasfunded.com/consistency",
        "https://help.atlasfunded.com/atlas-protector",
        "https://help.atlasfunded.com/payout-eligibility",
    )
    evaluation_target: Decimal = Decimal("0.03")
    evaluation_trailing: Decimal = Decimal("0.10")
    funded_trailing: Decimal = Decimal("0.06")
    evaluation_daily: Decimal = Decimal("0.05")
    funded_daily: Decimal = Decimal("0.03")
    consistency: Decimal = Decimal("0.20")
    qualifying_day: Decimal = Decimal("0.005")
    qualifying_days: int = 3
    protector: Decimal = Decimal("0.02")
    normal_split: Decimal = Decimal("0.90")
    protector_split: Decimal = Decimal("0.50")
    minimum_cycle_profit: Decimal = Decimal("100")
    first_wait_days: int = 28
    subsequent_wait_days: int = 14


PROFILE = AccessRuleProfile()


@dataclass(frozen=True)
class Eligibility:
    eligible: bool
    reasons: tuple[str, ...]
    cycle_profit: Decimal
    lifetime_best_day: Decimal
    qualifying_days: int
    required_consistency_profit: Decimal


class ExperimentalAccessLedger:
    """Supplied-event ledger; deliberately disconnected from live rule engines.

    ``initial_balance`` anchors qualifying-day and Protector amounts for life.
    Payout re-anchors drawdown and account-profit balance. This interpretation
    must be checked against the eventual account contract. UTC closed P&L is
    supplied after all costs; news/short-trade/margin deductions are NOT modeled.
    A request reserves no funds; settlement is a distinct explicitly supplied
    event, not a prediction that the firm approves or pays.
    """

    def __init__(self, phase: str, opened_at: int, balance=5000):
        if phase not in {"evaluation", "funded"}:
            raise ValueError("phase must be evaluation or funded")
        self.initial_balance = amount(balance)
        if self.initial_balance <= 0:
            raise ValueError("balance must be positive")
        self.phase = phase
        self.opened_at = self._timestamp(opened_at)
        self.last_at = self.opened_at
        self.utc_day = self.opened_at // DAY
        self.balance = self.equity = self.peak_equity = self.profit_anchor = self.initial_balance
        self.daily_floor = self.equity * (1 - self.daily_rate)
        self.cycle_days: dict[int, Decimal] = {}
        self.lifetime_days: dict[int, Decimal] = {}
        self.cycle_profit = Decimal(0)
        self.protector_hits = 0
        self.protector_armed = True
        self.status = "active"
        self.last_paid_at: int | None = None
        self.pending: dict | None = None
        self.payouts: list[dict] = []

    @staticmethod
    def _timestamp(ts):
        if isinstance(ts, bool) or not isinstance(ts, int) or ts < 0:
            raise ValueError("timestamp must be a nonnegative integer UTC epoch")
        return ts

    @property
    def daily_rate(self):
        return PROFILE.evaluation_daily if self.phase == "evaluation" else PROFILE.funded_daily

    @property
    def trailing_floor(self):
        rate = PROFILE.evaluation_trailing if self.phase == "evaluation" else PROFILE.funded_trailing
        return self.peak_equity * (1 - rate)

    @property
    def split(self):
        return PROFILE.protector_split if self.protector_hits else PROFILE.normal_split

    @property
    def lifetime_best_day(self):
        return max([Decimal(0), *self.lifetime_days.values()])

    @property
    def next_payout_at(self):
        return (self.opened_at + PROFILE.first_wait_days * DAY if self.last_paid_at is None
                else self.last_paid_at + PROFILE.subsequent_wait_days * DAY)

    def _advance(self, ts, midnight_equity=None):
        ts = self._timestamp(ts)
        if ts < self.last_at:
            raise ValueError("events must be chronological")
        day = ts // DAY
        if day != self.utc_day:
            if day != self.utc_day + 1 or midnight_equity is None:
                raise ValueError("each UTC reset needs its observed midnight equity")
            reset = amount(midnight_equity)
            if reset <= 0:
                raise ValueError("midnight equity must be positive")
            self.daily_floor = reset * (1 - self.daily_rate)
            self.utc_day = day
            self._mark_equity(reset)
        self.last_at = ts

    def observe(self, ts, equity, *, midnight_equity=None):
        value = amount(equity)
        self._advance(ts, midnight_equity)
        self._mark_equity(value)
        return self.status

    def _mark_equity(self, value):
        self.equity = value
        if self.status != "active":
            return
        self.peak_equity = max(self.peak_equity, value)
        if value < self.daily_floor or value < self.trailing_floor:
            self.status = "breached"
        floating = value - self.balance
        if floating >= 0:
            self.protector_armed = True
        if (self.status == "active" and self.phase == "funded" and self.protector_armed
                and floating <= -PROFILE.protector * self.initial_balance):
            self.protector_hits += 1
            self.protector_armed = False
            if self.protector_hits >= 2:
                self.status = "breached"
            # The caller must supply actual close fills. This ledger cannot
            # manufacture liquidation prices from the observed floating loss.

    def record_closed_profit(self, ts, net_profit, *, midnight_equity=None):
        """Book supplied after-cost realized cash; call observe for equity/path.

        May book Protector liquidation fills after a breach. It never resumes a
        breached account and never assumes that closing a leg makes it flat.
        """
        value = amount(net_profit)
        self._advance(ts, midnight_equity)
        self.balance += value
        self.cycle_profit += value
        day = ts // DAY
        self.cycle_days[day] = self.cycle_days.get(day, Decimal(0)) + value
        self.lifetime_days[day] = self.lifetime_days.get(day, Decimal(0)) + value

    def evaluation_passed(self, *, open_positions: int):
        self._check_positions(open_positions)
        return (self.phase == "evaluation" and self.status == "active" and open_positions == 0
                and self.balance >= self.initial_balance * (1 + PROFILE.evaluation_target))

    @staticmethod
    def _check_positions(count):
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            raise ValueError("open_positions must be a known nonnegative count")

    def eligibility(self, ts, *, kyc_verified: bool | None, open_positions: int,
                    midnight_equity=None):
        self._advance(ts, midnight_equity)
        reasons = []
        qualified = sum(p >= self.initial_balance * PROFILE.qualifying_day
                        for p in self.cycle_days.values())
        required = self.lifetime_best_day / PROFILE.consistency
        if self.phase != "funded":
            reasons.append("not_funded")
        if self.status != "active":
            reasons.append("not_active")
        if self.pending is not None:
            reasons.append("pending_payout")
        if kyc_verified is not True:
            reasons.append("kyc_unverified")
        self._check_positions(open_positions)
        if open_positions:
            reasons.append("open_positions")
        if ts < self.next_payout_at:
            reasons.append("payout_window")
        if self.balance <= self.profit_anchor:
            reasons.append("account_not_in_profit")
        if self.cycle_profit < PROFILE.minimum_cycle_profit:
            reasons.append("profit_threshold")
        if qualified < PROFILE.qualifying_days:
            reasons.append("qualifying_days")
        if self.cycle_profit > 0 and self.cycle_profit < required:
            reasons.append("consistency")
        if datetime.fromtimestamp(ts, timezone.utc).weekday() >= 5:
            reasons.append("weekend_request")
        return Eligibility(not reasons, tuple(reasons), self.cycle_profit,
                           self.lifetime_best_day, qualified, required)

    def request_payout(self, ts, target_cash=100, *, kyc_verified: bool | None,
                       open_positions: int, midnight_equity=None):
        cash = amount(target_cash).quantize(CENT, rounding=ROUND_HALF_UP)
        if cash <= 0:
            raise ValueError("target cash must be positive")
        check = self.eligibility(ts, kyc_verified=kyc_verified, open_positions=open_positions,
                                 midnight_equity=midnight_equity)
        if not check.eligible:
            raise ValueError("payout blocked: " + ", ".join(check.reasons))
        gross = (cash / self.split).quantize(CENT, rounding=ROUND_HALF_UP)
        if gross > min(self.cycle_profit, self.balance - self.profit_anchor):
            raise ValueError("request exceeds available realized profit")
        self.pending = dict(requested_at=ts, gross=gross, cash=cash, split=self.split)
        return dict(self.pending)

    def settle_payout(self, ts, *, approved: bool, open_positions: int, midnight_equity=None):
        """Supply a real/scenario approval event; no automatic approvals."""
        if self.pending is None:
            raise ValueError("no pending payout")
        if not isinstance(approved, bool):
            raise ValueError("approval must be an explicit boolean")
        if not isinstance(open_positions, int) or isinstance(open_positions, bool) or open_positions != 0:
            raise ValueError("settlement requires known flat account")
        self._advance(ts, midnight_equity)
        if not approved:
            self.pending = None
            return None
        if self.status != "active" or self.balance - self.pending["gross"] < self.profit_anchor:
            raise ValueError("account no longer supports requested payout")
        if self.split != self.pending["split"]:
            raise ValueError("profit split changed while payout pending; reject and request again")
        record = dict(self.pending, paid_at=ts)
        self.balance -= record["gross"]
        self.equity = self.balance
        self.daily_floor -= record["gross"]
        self.profit_anchor = self.peak_equity = self.balance
        self.cycle_profit = Decimal(0)
        self.cycle_days.clear()
        self.last_paid_at = ts
        self.pending = None
        self.payouts.append(record)
        return dict(record)

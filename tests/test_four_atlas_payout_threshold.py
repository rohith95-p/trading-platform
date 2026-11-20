import numpy as np

from scripts.research.four_atlas_lifecycle import Account, DAY


def test_access_qualifying_day_threshold_moves_with_payout_anchor():
    account = Account("funded", 0, np.array([]))
    account.cash = 5300
    account.cycle.update({day: 50 for day in range(6)})
    account.lifetime.update(account.cycle)
    account.maybe_pay(28 * DAY)
    assert account.cash_paid == 100
    assert account.profit_anchor == 5188.89
    account.cycle.update({29: 25, 30: 25.94, 31: 25.95})
    assert account.qualifying_days() == 1

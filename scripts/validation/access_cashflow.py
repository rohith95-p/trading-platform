"""Offline evaluation followed by a fresh funded account on the RECENT window."""
import json
import os


def main():
    os.environ.update(ULTRA_TRADE_24H='1', ULTRA_DISABLE_ALERTS='1', ULTRA_NO_TRIAL_LEDGER='1')
    from src.backtesting.access import AccessAccount
    from src.backtesting.engine import BacktestEngine, EngineConfig
    from src.backtesting.master import load_master, window
    from src.backtesting.costs import SCENARIOS
    from src.strategies.portfolio_atlas import PORTFOLIO

    start, end = window('RECENT')
    bars = load_master(('M15','M1','D1'), start=start, end=end)
    for phase in ('evaluation','funded'):
        cfg = EngineConfig.live_parity_preset(starting_balance=5000., fixed_lots=.02,
            max_concurrent=3, max_same_direction=3, history_bars=7500,
            protect_profit=False, m1_policy='skip')
        engine = BacktestEngine(bars, SCENARIOS['realistic_ecn'], cfg)
        policy = AccessAccount(phase, start)
        result = engine.run([cls() for cls in PORTFOLIO], start, end, account_policy=policy)
        print(json.dumps(dict(phase=phase, status=policy.status, trades=len(result.trades),
            end_balance=round(engine.balance,2), payouts=policy.payouts,
            sampled_trailing_floor=round(policy.peak*(1-policy.trailing_rate),2))))
        if policy.status != 'passed':
            break
        start = (policy.finished_at//900+1)*900


if __name__ == '__main__':
    main()

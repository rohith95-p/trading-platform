"""Fixed diagnostic scenarios on an already-used window; no parameter search."""
import reproduce as r
import dataclasses
import json
from src.backtesting.master import load_master, window
from src.backtesting.engine import BacktestEngine, EngineConfig
from src.backtesting.costs import SCENARIOS
from src.strategies.portfolio_atlas import PORTFOLIO

if __name__ == '__main__':
    a,b = window('RECENT')
    bars = load_master(('M15','M1','D1'), start=a, end=b)
    arms = [('frictionless', SCENARIOS['frictionless'], False),
            ('ecn_double_spread_triple_slippage', dataclasses.replace(
                SCENARIOS['realistic_ecn'], spread_multiplier=2., slippage_points=60.), False),
            ('ecn_gap_stops', SCENARIOS['realistic_ecn'], True)]
    report = {}
    for name,cost,gap in arms:
        cfg = EngineConfig.live_parity_preset(sizing_mode='fixed', fixed_lots=.02,
            starting_balance=5000., max_concurrent=3, max_same_direction=3,
            history_bars=7500, protect_profit=False, m1_policy='skip', gap_fill_stops=gap)
        result = BacktestEngine(bars,cost,cfg).run([c() for c in PORTFOLIO],a,b)
        pls = r.np.array([t.net_pl for t in result.trades])
        report[name] = dict(trades=len(pls), net=float(pls.sum()),
            pf=float(pls[pls>0].sum()/-pls[pls<0].sum()), diagnostics=result.diagnostics,
            cost=dataclasses.asdict(cost), engine_config=cfg.as_dict())
        print(name, len(pls), float(pls.sum()), report[name]['pf'], flush=True)
        (r.OUT/'stress.json').write_text(json.dumps(report,indent=2,default=str),encoding='utf-8')

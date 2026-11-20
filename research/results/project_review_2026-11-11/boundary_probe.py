"""Synthetic probe: open position, requested end before loaded data end."""
import reproduce as r
from src.backtesting.data import BarSet, SymbolSpec
from src.backtesting.engine import BacktestEngine, EngineConfig, Position
from src.backtesting.costs import SCENARIOS

if __name__ == '__main__':
    dtype = [('time','i8'),('open','f8'),('high','f8'),('low','f8'),
             ('close','f8'),('tick_volume','i8'),('spread','i4'),('real_volume','i8')]
    t0 = r.utc(2024,1,1)
    def bars(n,step):
        a = r.np.zeros(n,dtype=dtype)
        a['time'] = t0+r.np.arange(n)*step
        for f in ['open','close']: a[f] = 2000.
        a['high'],a['low'],a['spread'] = 2000.1,1999.9,200
        return a
    m15,m1 = bars(400,900),bars(6000,60)
    spec = SymbolSpec('XAUUSDm',3,.001,.001,.1,.01,200.,.01,100.)
    dataset = BarSet('XAUUSDm',m15,None,m1,None,spec,{})
    cfg = EngineConfig(starting_balance=5000.,sizing_mode='fixed',fixed_lots=.02,
        enable_d1_bias_gate=False,enable_consolidation_exit=False)
    eng = BacktestEngine(dataset,SCENARIOS['frictionless'],cfg)
    start,end = int(m15['time'][300]),int(m15['time'][310])
    eng.positions.append(Position(ticket=1,strategy='BOUNDARY_PROBE',magic=99999,
        is_buy=True,lots=.02,entry_price=2000.,entry_time=start,
        sl=0.,tp=100000.,initial_sl=0.,atr_at_entry=.2,session='TEST',
        mfe_price=2000.,mae_price=2000.,price_current=2000.))
    result = eng.run([],start,end)
    out = dict(requested_end=end,loaded_end=int(m15['time'][-1]),
        exits=[dict(time=t.exit_time,reason=t.exit_reason,after_requested_end=t.exit_time>end)
               for t in result.trades])
    (r.OUT/'boundary_probe.json').write_text(r.json.dumps(out,indent=2),encoding='utf-8')
    print(out)

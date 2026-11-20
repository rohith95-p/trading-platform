"""Reconstruct modeled funded account immediately before every native guarded fill."""
from pathlib import Path
import json
import pandas as pd
from scripts.research.retained_native_account import NativeAccount
from scripts.research.four_atlas_lifecycle import audit_trade_ledger, utc

ROOT = Path("research/results/guarded_retained_mt5")
NAMES = ["2025_portfolio_funded_phase_split", "2026_portfolio_funded_phase_split",
         "2025_portfolio_funded_phase_split_continuous"]

class HeadroomAccount(NativeAccount):
    verify_protector_from_quotes = True

    def __init__(self, phase, start, news):
        super().__init__(phase, start, news)
        self.orders = []

    def fill(self, action, p, ms):
        if action == 'entry' and self.phase == 'funded' and self.status == 'active':
            # One open at most: cash = modeled equity immediately before the fill.
            assert not self.open and abs(self.final_equity-self.cash)<1e-7
            assert p.initial_sl>0 and p.lots==.01 and p.entry_ms_exact
            adverse = (p.entry_price-p.initial_sl) * (1 if p.is_buy else -1)
            assert adverse > 0
            stop_risk = adverse * 100*p.lots
            reserved = stop_risk + 5 + max(0.,-p.entry_fee)
            protector_floor = self.cash-100
            floors = {'daily': .97*self.anchor, 'trailing': .94*self.peak,
                      'protector': protector_floor}
            amounts = {key:self.cash-floor for key,floor in floors.items()}
            tight = min(amounts, key=amounts.get)
            self.orders.append(dict(time=utc(ms), ticket=int(p.ticket), strategy=p.strategy,
                                    cash=self.cash, midnight_anchor=self.anchor, peak=self.peak,
                                    settled_payouts=len(self.payouts), initial_sl=p.initial_sl,
                                    lots=p.lots, native_entry_price=p.entry_price, stop_risk=stop_risk,
                                    reserved_risk=reserved, tightest=tight,
                                    **{key+'_headroom':v for key,v in amounts.items()},
                                    **{key+'_after_reserve':v-reserved for key,v in amounts.items()},
                                    minimum_after_reserve=amounts[tight]-reserved))
        super().fill(action,p,ms)

    def result(self):
        return dict(super().result(), checked_orders=self.orders)

def run():
    summary = {}
    tables = []
    for stem in NAMES:
        data=json.loads((ROOT/f'{stem}_audit.json').read_text())
        trades=pd.read_csv(ROOT/f'{stem}_trades.csv')
        cfg=dict(name=stem,phase='funded',net=trades.net_pl.sum(),
                 start=int(pd.Timestamp(data['start']).timestamp()),
                 end_exclusive=int(pd.Timestamp(data['end_exclusive']).timestamp()))
        audited=audit_trade_ledger(cfg,trades,HeadroomAccount,False)['atlas']
        prior=data['native']['atlas']
        for key in ['status','entries','modeled_payouts','balance','protector_strikes']:
            if key=='balance':
                assert abs(audited[key]-prior[key])<1e-7
            else:
                assert audited[key]==prior[key]
        orders=pd.DataFrame(audited['checked_orders'])
        assert len(orders)==len(trades)
        orders.insert(0,'run',stem)
        tables.append(orders)
        worst = orders.loc[orders.minimum_after_reserve.idxmin()]
        summary[stem]=dict(orders=len(orders),after_withdrawal=int((orders.settled_payouts>0).sum()),
                           negative_margins=int((orders.minimum_after_reserve<=0).sum()),
                           min_after_reserve=worst.minimum_after_reserve,worst=worst.to_dict(),
                           minimums={k:float(orders[k+'_after_reserve'].min()) for k in ['daily','trailing','protector']})
    pd.concat(tables,ignore_index=True).to_csv(ROOT/'funded_headroom_orders.csv',index=False)
    (ROOT/'funded_headroom.json').write_text(json.dumps(summary,indent=2))
    for k,v in summary.items():
        print(k,v['orders'],v['after_withdrawal'],v['min_after_reserve'],v['minimums'],v['worst']['time'],v['worst']['reserved_risk'])

if __name__=='__main__':
    run()

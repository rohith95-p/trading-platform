"""Audit one joint native MT5 run, preserving the second-level Luna signal provenance."""
import argparse
import json
from pathlib import Path
import pandas as pd
from scripts.research.retained_native_account import NativeAccount, comparable, metrics, normalize, read_export
from scripts.research.four_atlas_lifecycle import audit_trade_ledger
from scripts.research.luna_six_month_audit import read_report

out = Path(__file__).resolve().parents[1] / "results/mt5_joint"

class JointAccount(NativeAccount):
    verify_protector_from_quotes = True


def run(year, mask, phase, start, label):
    label = f"{label}_{year}_{mask}_{phase}"
    report, trades = read_report(out / f"{label}.htm")
    deals = read_export(out / f"{label}_deals.csv")
    assert len(deals) == len(trades)
    for row, d in zip(deals.itertuples(), trades):
        assert row.order==d['order'] and abs(row.price-d['price'])<.00051
    raw = normalize(deals)
    ordered = raw.sort_values('entry_time_ms')
    assert not (ordered.entry_time_ms.to_numpy()[1:] < ordered.exit_time_ms.to_numpy()[:-1]).any()
    assert raw.lots.eq(.01).all() and raw.initial_sl.gt(0).all()
    raw['strategy'] = raw.strategy.replace({'magic_47761':'LUNA_BASKET_SOURCE'})
    raw.to_csv(out / f"{label}_trades.csv", index=False)
    assert abs(raw.net_pl.sum()-float(report['Total Net Profit'].replace(' ','')))<.011
    begin = start or f"{year}-01-01"
    end = "2026-11-01" if year==2026 else "2026-01-01"
    cfg = dict(name=label,phase=phase,start=int(pd.Timestamp(begin,tz='UTC').timestamp()),
               end_exclusive=int(pd.Timestamp(end,tz='UTC').timestamp()),net=float(raw.net_pl.sum()))
    exactly = raw.entry_ms_exact.all() and raw.exit_ms_exact.all()
    checked = audit_trade_ledger(cfg, raw, JointAccount, False)
    ecn = comparable(raw)
    stress = audit_trade_ledger(dict(cfg,net=float(ecn.net_pl.sum())),ecn)
    data = dict(metrics=report,raw=metrics(raw),ecn=metrics(ecn),native=checked,ecn_path=stress,
                exact_millisecond_deals=bool(exactly),
                contributions={k:metrics(v) for k,v in raw.groupby('strategy')})
    (out/f"{label}_audit.json").write_text(json.dumps(data,indent=2))
    print(label, data['raw'],checked['atlas']['status'],checked['atlas']['time'], flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('year',type=int)
    p.add_argument('mask',type=int)
    p.add_argument('phase',choices=['evaluation','funded'])
    p.add_argument('--start')
    p.add_argument('--label',default='joint')
    run(**vars(p.parse_args()))

"""Measure overlapping archived original Luna and unrestricted retained exposures (diagnostic only)."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from scripts.research.luna_six_month_audit import read_report, portfolio_states

out = Path(__file__).resolve().parents[1] / "results"
_, deals = read_report(out/"luna_four_year_20261120/arch48_default.htm")
stamp, longs, shorts, *_ = portfolio_states(deals)
results = {}
for year in [2026,2025]:
    native=pd.read_csv(out/f"retained_mt5/{year}_portfolio_trades.csv")
    overlaps=[]
    for leg in native.itertuples():
        a,b=stamp.searchsorted([leg.entry_time_ms,leg.exit_time_ms],side="right")
        a-=1
        lv,sv=longs[a:b],shorts[a:b]
        same=(lv if leg.is_buy else sv)>1e-7
        opposite=(sv if leg.is_buy else lv)>1e-7
        overlaps.append(dict(year=year,ticket=leg.ticket,strategy=leg.strategy,same=bool(same.any()),
                             opposite=bool(opposite.any()),any_luna=bool((same|opposite).any())))
    table=pd.DataFrame(overlaps)
    table.to_csv(out/f"mt5_joint/{year}_original_overlap.csv",index=False)
    results[year]={'retained_positions':len(table),**table[['same','opposite','any_luna']].sum().astype(int).to_dict()}
(out/"mt5_joint/original_overlap.json").write_text(json.dumps(results,indent=2))
print(results)

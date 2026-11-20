"""Diagnostic daily proxy screen specified in PREREG_LaggedMacroScreen."""
from pathlib import Path

import numpy as np
import pandas as pd


def main():
    root = Path(__file__).resolve().parents[2]
    frame = pd.read_csv(root / "research/data/d1_study/master.csv", index_col="Date",
                        parse_dates=True).loc[:'2025', ['gold', 'dxy', 'y10']].dropna()
    changes = np.sign(frame.diff(5).shift(1))
    direction = (-changes.dxy).where(changes.dxy == changes.y10, 0.)
    variants = {'agreement': direction,
                'divergence': direction.where(changes.gold == -direction, 0.),
                'long': pd.Series(1., index=frame.index)}
    forward = frame.gold.shift(-1) / frame.gold - 1.
    for start, end in [('2000','2011'), ('2012','2018'), ('2019','2025')]:
        for name, signal in variants.items():
            pos = signal.loc[start:end].iloc[:-1]
            returns = forward.reindex(pos.index)
            turnover = pos.diff().abs()
            turnover.iloc[0] = abs(pos.iloc[0])
            turnover.iloc[-1] += abs(pos.iloc[-1])
            pnl = pos * returns - .0002 * turnover
            reverse = -pos * returns - .0002 * turnover
            print(start, end, name, 'active_days', int(pos.ne(0).sum()),
                  'net_compounded_pct', round(100*((1+pnl).prod()-1),2),
                  'reverse_pct', round(100*((1+reverse).prod()-1),2))


if __name__ == '__main__':
    main()

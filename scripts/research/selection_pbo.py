"""Conditional selection-overfitting diagnostic on a frozen panel of daily returns."""
from itertools import combinations
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import rankdata

from scripts.research.market_atlas import ROOT, OUT, sha

INPUT_KEY = "7132368ef74b14883d2a84045c37f158db70a97e38d7a728486845d942baa3cf"


def selection_pbo(values, blocks=10):
    panel = np.asarray(values, dtype=float)
    if (panel.ndim != 2 or panel.shape[1] < 2 or blocks < 2 or blocks % 2
            or len(panel) < 2*blocks or not np.isfinite(panel).all()):
        raise ValueError("Require a finite panel and an even number of contiguous blocks")
    size = len(panel) // blocks
    groups = np.repeat(np.arange(blocks), size)
    common = panel[:len(groups)]
    splits = []
    for train in combinations(range(blocks), blocks//2):
        mask = np.isin(groups, train)
        a, b = common[mask], common[~mask]
        if np.any(a.std(axis=0, ddof=1)==0) or np.any(b.std(axis=0, ddof=1)==0):
            splits.append({"train_blocks":train, "defined":False})
            continue
        sr_train = a.mean(axis=0)/a.std(axis=0, ddof=1)
        sr_test = b.mean(axis=0)/b.std(axis=0, ddof=1)
        winners = np.flatnonzero(sr_train==sr_train.max())
        percentile = rankdata(sr_test, method="average")[winners]/(panel.shape[1]+1)
        logit = np.log(percentile/(1-percentile))
        splits.append(dict(train_blocks=train, defined=True, winners=winners.tolist(),
                           pbo_vote=float(np.mean(percentile<=.5)), test_loss_vote=float(np.mean(sr_test[winners]<0)),
                           mean_logit=float(logit.mean())))
    valid = [s for s in splits if s["defined"]]
    return dict(block_size=size, unused_tail_rows=len(panel)-len(groups), total_splits=len(splits),
                defined_splits=len(valid), pbo=float(np.mean([s["pbo_vote"] for s in valid])) if valid else None,
                negative_test_fraction=float(np.mean([s["test_loss_vote"] for s in valid])) if valid else None,
                split_logit_quantiles=np.quantile([s["mean_logit"] for s in valid],[.1,.5,.9]).tolist() if valid else None,
                splits=splits)


def main():
    source = ROOT/"research/data/selection_inputs"/(INPUT_KEY+".csv")
    if sha(source) != INPUT_KEY:
        raise ValueError("Input panel content changed")
    panel = pd.read_csv(source, index_col=0, parse_dates=True)
    if (panel.index.has_duplicates or not panel.index.is_monotonic_increasing or panel.columns.has_duplicates
            or len(panel.columns)!=16 or panel.index.max()>=pd.Timestamp("2026-11-01",tz="UTC")):
        raise ValueError("Unexpected panel dates or candidate universe")
    result = selection_pbo(panel.to_numpy())
    result.update(source_sha256=INPUT_KEY, code_sha256=sha(Path(__file__)), columns=list(panel.columns),
                  start=str(panel.index[0]), last_used=str(panel.index[result["block_size"]*10-1]),
                  source="https://escholarship.org/uc/item/4w1110bb")
    (OUT/"selection_pbo.json").write_text(json.dumps(result,indent=2,allow_nan=False),encoding="utf-8")
    print({k:v for k,v in result.items() if k!="splits"})


if __name__=="__main__":
    main()

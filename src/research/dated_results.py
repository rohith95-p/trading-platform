"""Dated cash P&L for comparison across explicitly covered research intervals."""
import hashlib
import json
import os
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd


def save_result(name, pnl, start, end, *, specification, runner, output_root=None):
    """Save closed P&L with explicit coverage. End date is inclusive.

    Missing rows within coverage mean zero realized P&L. Dates outside coverage
    remain unknown when results are aligned. This is not mark-to-market equity.
    """
    series = pd.Series(pnl, dtype=float).copy()
    if not isinstance(series.index, pd.DatetimeIndex):
        series.index = pd.to_datetime(series.index, utc=True)
    else:
        series.index = pd.to_datetime(series.index, utc=True)
    if not np.isfinite(series.to_numpy()).all():
        raise ValueError("Non-finite research P&L")
    series.index = series.index.normalize()
    series = series.groupby(level=0).sum().sort_index()
    lo, hi = pd.Timestamp(start, tz='UTC'), pd.Timestamp(end, tz='UTC')
    if hi < lo or ((series.index < lo) | (series.index > hi)).any():
        raise ValueError("Research P&L falls outside declared coverage")
    spec = Path(specification)
    source = Path(runner)
    from src.backtesting.costs import SCENARIOS
    record = dict(schema_version=1, name=name, start=str(lo.date()), end=str(hi.date()),
                  observation='realized_cash_pnl', capital_reference=5000.,
                  specification=spec.read_text(encoding='utf-8-sig'),
                  runner_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                  costs=SCENARIOS['realistic_ecn'].descriptor(),
                  series={str(date.date()):float(value) for date,value in series.items()})
    encoded = json.dumps(record, sort_keys=True, allow_nan=False).encode()
    key = hashlib.sha256(encoded).hexdigest()
    root = Path(output_root or 'research/dated_results')
    root.mkdir(parents=True, exist_ok=True)
    path = root/(key+'.json')
    if not path.exists():
        handle, temporary = tempfile.mkstemp(dir=root, suffix='.tmp')
        try:
            with os.fdopen(handle,'wb') as stream:
                stream.write(encoded)
            os.replace(temporary,path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    return path


def align_results(records, start, end):
    """Calendar alignment retains unknown values beyond each run's coverage."""
    index = pd.date_range(start,end,freq='D',tz='UTC')
    columns = {}
    for key, record in records.items():
        if record['observation'] != 'realized_cash_pnl':
            raise ValueError("Incompatible observation basis")
        values = pd.Series(record['series'],dtype=float)
        values.index = pd.to_datetime(values.index,utc=True)
        aligned = values.reindex(index,fill_value=0.)
        covered = (index>=pd.Timestamp(record['start'],tz='UTC')) & (index<=pd.Timestamp(record['end'],tz='UTC'))
        columns[key] = aligned.where(covered)
    return pd.DataFrame(columns,index=index)

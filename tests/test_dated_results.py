import json
import numpy as np
import pandas as pd
import pytest
from src.research.dated_results import align_results, save_result


def test_calendar_alignment_preserves_nonoverlap():
    def record(start,end,values):
        return dict(observation='realized_cash_pnl',start=start,end=end,series=values)
    a=record('2020-01-01','2020-01-02',{'2020-01-01':1.})
    b=record('2020-01-03','2020-01-04',{'2020-01-03':1.})
    matrix=align_results({'a':a,'b':b},'2020-01-01','2020-01-04')
    assert matrix.a.iloc[1]==0
    assert np.isnan(matrix.a.iloc[2])
    assert matrix.dropna().empty


def test_immutable_results_preserve_revisions(tmp_path):
    spec=tmp_path/'spec.md'
    runner=tmp_path/'runner.py'
    spec.write_text('fixed rule')
    runner.write_text('version one')
    pnl=pd.Series([3.,-1.],index=pd.to_datetime(['2020-01-01','2020-01-01'],utc=True))
    kwargs=dict(specification=spec,runner=runner,output_root=tmp_path/'results')
    first=save_result('candidate',pnl,'2020-01-01','2020-01-03',**kwargs)
    assert json.loads(first.read_text())['series']=={'2020-01-01':2.}
    assert save_result('candidate',pnl,'2020-01-01','2020-01-03',**kwargs)==first
    runner.write_text('version two')
    assert save_result('candidate',pnl,'2020-01-01','2020-01-03',**kwargs)!=first
    with pytest.raises(ValueError):
        save_result('candidate',pnl,'2020-01-02','2020-01-03',**kwargs)

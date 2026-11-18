import json
import pytest
from scripts.validation.full_metric_suite import ratios


@pytest.mark.parametrize('pnl',[[-6000.],[-6000.,7000.],[]])
def test_no_invalid_cagr_or_json_after_exhaustion(pnl):
    result = ratios(pnl,7)
    json.dumps(result,allow_nan=False)
    if pnl:
        assert result['closed_balance_nonpositive']
        assert result['first_nonpositive_after_trade']==1
        assert result['annualised_return_pct'] is None
        assert result['calmar_ratio'] is None

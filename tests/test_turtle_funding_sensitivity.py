import numpy as np
import pytest
from scripts.validation.turtle_funding_sensitivity import maximum_charge,profit_factor


def test_funding_threshold_solves_fixed_path_pf():
    p = np.array([10.,-5.])
    nights = np.array([2.,1.])
    # (10-2c)/(5+c)=1.3 => c=3.5/3.3.
    limit = maximum_charge(p,nights)
    assert limit==pytest.approx(3.5/3.3)
    assert profit_factor(p-limit*nights)==pytest.approx(1.3)
    assert maximum_charge(np.array([1.,-2.]),nights) is None

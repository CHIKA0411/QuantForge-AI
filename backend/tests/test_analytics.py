import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.analytics import calculate_max_pain


def _option(strike, option_type, open_interest):
    return {
        "strike_price": float(strike),
        "option_type": option_type,
        "open_interest": float(open_interest),
    }


def test_max_pain_uses_near_atm_strikes_when_spot_price_is_available():
    options = [
        _option(23750, "CE", 100),
        _option(23750, "PE", 1000),
        _option(23800, "CE", 100),
        _option(23800, "PE", 1000),
        _option(23850, "CE", 100),
        _option(23850, "PE", 1000),
        _option(23900, "CE", 100),
        _option(23900, "PE", 1000),
        _option(23950, "CE", 100),
        _option(23950, "PE", 1000),
        _option(24000, "CE", 500),
        _option(24000, "PE", 500),
        _option(24050, "CE", 1000),
        _option(24050, "PE", 100),
        _option(24100, "CE", 1000),
        _option(24100, "PE", 100),
        _option(24150, "CE", 1000),
        _option(24150, "PE", 100),
        _option(24200, "CE", 1000),
        _option(24200, "PE", 100),
        _option(24250, "CE", 1000),
        _option(24250, "PE", 100),
        _option(24300, "CE", 100000),
        _option(24300, "PE", 1),
    ]

    assert calculate_max_pain(options, spot_price=24000, num_strikes=2) == 24000.0

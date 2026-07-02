import datetime
import os
import sys

import pytest

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.nse_client import NSEClient
from app.config import settings
from app.routes.market import _get_live_market_snapshot


def test_get_market_data_does_not_fallback_to_simulation_when_live_fetch_fails(monkeypatch):
    client = NSEClient()
    monkeypatch.setattr(settings, "NSE_SIMULATE", False)
    monkeypatch.setattr(client, "fetch_live_data", lambda symbol: None)

    with pytest.raises(RuntimeError):
        client.get_market_data("NIFTY")


def test_get_live_market_snapshot_prefers_live_data(monkeypatch):
    monkeypatch.setattr("app.routes.market.nse_client.get_market_data", lambda symbol: {"spot_price": 24005.85, "options": [{"strike_price": 24000, "option_type": "CE"}]})

    data = _get_live_market_snapshot("NIFTY")

    assert data is not None
    assert data["spot_price"] == 24005.85
    assert data["options"][0]["strike_price"] == 24000


def test_parse_nse_json_supports_unwrapped_live_payload():
    client = NSEClient()
    payload = {
        "data": [
            {
                "expiryDates": "07-Jul-2026",
                "CE": {
                    "strikePrice": 21350,
                    "openInterest": 1000,
                    "changeinOpenInterest": 50,
                    "totalTradedVolume": 200,
                    "impliedVolatility": 25.5,
                    "lastPrice": 100.0,
                    "buyPrice1": 99.0,
                    "sellPrice1": 101.0,
                },
                "PE": {
                    "strikePrice": 21350,
                    "openInterest": 900,
                    "changeinOpenInterest": 40,
                    "totalTradedVolume": 180,
                    "impliedVolatility": 24.0,
                    "lastPrice": 80.0,
                    "buyPrice1": 79.0,
                    "sellPrice1": 81.0,
                },
                "strikePrice": 21350,
            }
        ],
        "timestamp": "07-Jul-2026 15:30:00",
        "underlyingValue": 24005.85,
        "expiryDates": ["07-Jul-2026"],
    }

    parsed = client.parse_nse_json("NIFTY", payload)

    assert parsed["spot_price"] == 24005.85
    assert parsed["expiry_date"] == datetime.date(2026, 7, 7)
    assert len(parsed["options"]) == 2
    assert parsed["options"][0]["option_type"] == "CE"
    assert parsed["options"][1]["option_type"] == "PE"

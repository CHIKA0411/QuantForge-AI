import sys
import os
from fastapi.testclient import TestClient

# Add backend directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app
from app.db import init_db

def test_all_endpoints():
    print("Initializing test database...")
    init_db()  # Will default to SQLite fallback since no PG credentials
    
    client = TestClient(app)
    
    print("\nTesting GET /api/health...")
    response = client.get("/api/health")
    print(f"Status: {response.status_code}, Body: {response.json()}")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
    
    print("\nTesting GET /api/market/spot...")
    response = client.get("/api/market/spot?symbol=NIFTY")
    assert response.status_code == 200
    body = response.json()
    print(f"Status: {response.status_code}, Spot: {body['price']}")
    assert body["symbol"] == "NIFTY"
    assert "price" in body
    assert "trend" in body
    
    print("\nTesting GET /api/market/option-chain...")
    response = client.get("/api/market/option-chain?symbol=NIFTY")
    assert response.status_code == 200
    body = response.json()
    print(f"Status: {response.status_code}, Options count: {len(body['options'])}")
    assert len(body["options"]) > 0
    assert "strike_price" in body["options"][0]
    assert "delta" in body["options"][0]
    
    print("\nTesting GET /api/market/vix...")
    response = client.get("/api/market/vix")
    assert response.status_code == 200
    body = response.json()
    print(f"Status: {response.status_code}, VIX Value: {body['value']}")
    assert "value" in body
    
    print("\nTesting GET /api/analytics/summary...")
    response = client.get("/api/analytics/summary?symbol=NIFTY")
    assert response.status_code == 200
    body = response.json()
    print(f"Status: {response.status_code}, Net GEX: {body['total_gex']}, Flip Level: {body['gamma_flip_level']}")
    assert "total_gex" in body
    assert "gamma_flip_level" in body
    assert "support_resistance" in body
    
    print("\nTesting GET /api/analytics/dealer-positioning...")
    response = client.get("/api/analytics/dealer-positioning?symbol=NIFTY")
    assert response.status_code == 200
    body = response.json()
    print(f"Status: {response.status_code}, Strikes detailed: {len(body['strikes'])}")
    assert len(body["strikes"]) > 0
    assert "net_gex" in body["strikes"][0]
    
    print("\nTesting GET /api/analytics/gex-profile...")
    response = client.get("/api/analytics/gex-profile?symbol=NIFTY")
    assert response.status_code == 200
    body = response.json()
    print(f"Status: {response.status_code}, Profile points: {len(body['profile'])}")
    assert len(body["profile"]) > 0
    
    print("\nTesting GET /api/analytics/volatility-smile...")
    response = client.get("/api/analytics/volatility-smile?symbol=NIFTY")
    assert response.status_code == 200
    body = response.json()
    print(f"Status: {response.status_code}, Smile points: {len(body['smile'])}")
    assert len(body["smile"]) > 0
    
    print("\nTesting GET /api/signals/forecast...")
    response = client.get("/api/signals/forecast?symbol=NIFTY")
    assert response.status_code == 200
    body = response.json()
    print(f"Status: {response.status_code}, Forecast Signal: {body['forecast']['signal']}, Confidence: {body['forecast']['confidence']}")
    assert "features" in body
    assert "forecast" in body
    assert "signal" in body["forecast"]
    
    print("\nTesting GET /api/signals/backtest...")
    response = client.get("/api/signals/backtest?symbol=NIFTY")
    assert response.status_code == 200
    body = response.json()
    print(f"Status: {response.status_code}, Backtest CAGR: {body['results']['metrics']['cagr']}%, Sharpe: {body['results']['metrics']['sharpe']}")
    assert "results" in body
    assert "metrics" in body["results"]
    assert "equity_curve" in body["results"]

    print("\nAll integration API tests passed successfully!")

if __name__ == "__main__":
    test_all_endpoints()

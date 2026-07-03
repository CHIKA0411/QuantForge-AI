from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
import datetime
from app.db import get_db, SpotPrice, OptionChain, VixData, FuturePrice, FiiDiiActivity
from app.nse_client import nse_client
from app.config import settings

router = APIRouter(prefix="/market", tags=["market"])


def _get_live_market_snapshot(symbol: str) -> Optional[Dict[str, Any]]:
    try:
        data = nse_client.get_market_data(symbol)
        if isinstance(data, dict) and data.get("spot_price") is not None:
            return data
    except Exception:
        return None
    return None


@router.get("/spot")
def get_spot_price(symbol: str = Query(default="NIFTY", description="Symbol name (NIFTY/BANKNIFTY)"), db: Session = Depends(get_db)):
    """Get the latest spot price of the index and past 30 points trend."""
    # Find latest in DB
    latest = db.query(SpotPrice).filter(SpotPrice.symbol == symbol).order_by(SpotPrice.timestamp.desc()).first()

    if not latest:
        live_data = _get_live_market_snapshot(symbol)
        if live_data:
            return {
                "symbol": symbol,
                "price": live_data["spot_price"],
                "timestamp": live_data["timestamp"],
                "trend": [{"timestamp": live_data["timestamp"], "price": live_data["spot_price"]}],
                "change_pct": 0.0,
            }

        raise HTTPException(status_code=502, detail=f"Unable to fetch live market data for {symbol}")
        
    # Get recent trend
    trend_records = db.query(SpotPrice).filter(SpotPrice.symbol == symbol).order_by(SpotPrice.timestamp.desc()).limit(30).all()
    trend_records.reverse()
    
    trend = [{"timestamp": record.timestamp.strftime("%H:%M:%S"), "price": record.price} for record in trend_records]
    
    # Calculate % change
    change_pct = 0.0
    if len(trend) > 1:
        prev = trend[0]["price"]
        curr = trend[-1]["price"]
        change_pct = ((curr - prev) / prev) * 100
        
    return {
        "symbol": symbol,
        "price": latest.price,
        "timestamp": latest.timestamp,
        "change_pct": round(change_pct, 2),
        "trend": trend
    }

@router.get("/option-chain")
def get_option_chain(symbol: str = Query(default="NIFTY"), db: Session = Depends(get_db)):
    """Get the latest option chain data with Greeks."""
    live_data = _get_live_market_snapshot(symbol)
    if live_data and live_data.get("options"):
        expiry_dt = datetime.datetime.combine(live_data["expiry_date"], datetime.time(15, 30))
        dt_diff = expiry_dt - live_data["timestamp"]
        time_to_expiry_seconds = max(1.0, dt_diff.total_seconds())
        T = time_to_expiry_seconds / (365.0 * 86400.0)

        import numpy as np
        from app.greeks import calculate_greeks_vectorized
        options = live_data["options"]
        strikes = np.array([opt["strike_price"] for opt in options])
        ivs = np.array([opt["implied_volatility"] for opt in options])
        types = np.array([opt["option_type"] for opt in options])

        deltas, gammas, vegas, thetas = calculate_greeks_vectorized(
            live_data["spot_price"], strikes, T, settings.RISK_FREE_RATE, ivs, types
        )

        response_options = []
        for i, opt in enumerate(options):
            opt_copy = opt.copy()
            opt_copy["delta"] = float(deltas[i])
            opt_copy["gamma"] = float(gammas[i])
            opt_copy["vega"] = float(vegas[i])
            opt_copy["theta"] = float(thetas[i])
            response_options.append(opt_copy)

        return {
            "symbol": symbol,
            "spot_price": live_data["spot_price"],
            "timestamp": live_data["timestamp"],
            "expiry_date": live_data["expiry_date"],
            "options": response_options
        }

    # Find the latest timestamp in OptionChain for this symbol
    latest_record = db.query(OptionChain).filter(OptionChain.symbol == symbol).order_by(OptionChain.timestamp.desc()).first()
    
    if not latest_record:
        raise HTTPException(status_code=502, detail=f"Unable to fetch live option chain data for {symbol}")
        
    latest_ts = latest_record.timestamp
    expiry_date = latest_record.expiry_date
    
    # Query all options at this latest timestamp
    options_db = db.query(OptionChain).filter(
        OptionChain.symbol == symbol,
        OptionChain.timestamp == latest_ts
    ).all()
    
    # Fetch current spot
    spot_rec = db.query(SpotPrice).filter(SpotPrice.symbol == symbol, SpotPrice.timestamp == latest_ts).first()
    spot_price = spot_rec.price if spot_rec else 0.0
    
    options = []
    for opt in options_db:
        options.append({
            "strike_price": opt.strike_price,
            "option_type": opt.option_type,
            "open_interest": opt.open_interest,
            "change_in_oi": opt.change_in_oi,
            "volume": opt.volume,
            "implied_volatility": opt.implied_volatility,
            "last_price": opt.last_price,
            "bid_price": opt.bid_price,
            "ask_price": opt.ask_price,
            "delta": opt.delta,
            "gamma": opt.gamma,
            "vega": opt.vega,
            "theta": opt.theta
        })
        
    return {
        "symbol": symbol,
        "spot_price": spot_price,
        "timestamp": latest_ts,
        "expiry_date": expiry_date,
        "options": options
    }

@router.get("/vix")
def get_vix(db: Session = Depends(get_db)):
    """Get the latest India VIX value and historical VIX trend."""
    latest = db.query(VixData).order_by(VixData.timestamp.desc()).first()
    
    if not latest:
        v = nse_client.generate_simulated_data("NIFTY")["vix"]
        return {
            "value": v,
            "timestamp": datetime.datetime.now().isoformat(),
            "trend": []
        }
        
    trend_records = db.query(VixData).order_by(VixData.timestamp.desc()).limit(30).all()
    trend_records.reverse()
    
    trend = [{"timestamp": record.timestamp.strftime("%H:%M:%S"), "vix": record.value} for record in trend_records]
    
    return {
        "value": latest.value,
        "timestamp": latest.timestamp,
        "trend": trend
    }

@router.get("/futures")
def get_futures_price(symbol: str = Query(default="NIFTY"), db: Session = Depends(get_db)):
    """Get the latest futures price of the index and past 30 points trend."""
    latest = db.query(FuturePrice).filter(FuturePrice.symbol == symbol).order_by(FuturePrice.timestamp.desc()).first()
    if not latest:
        try:
            data = nse_client.get_market_data(symbol)
            fut_price = data.get("futures_price", data["spot_price"])
            return {
                "symbol": symbol,
                "price": fut_price,
                "timestamp": data["timestamp"],
                "trend": [{"timestamp": data["timestamp"].strftime("%H:%M:%S"), "price": fut_price}],
                "change_pct": 0.0
            }
        except Exception:
            raise HTTPException(status_code=502, detail=f"Unable to fetch live futures data for {symbol}")
            
    trend_records = db.query(FuturePrice).filter(FuturePrice.symbol == symbol).order_by(FuturePrice.timestamp.desc()).limit(30).all()
    trend_records.reverse()
    trend = [{"timestamp": record.timestamp.strftime("%H:%M:%S"), "price": record.price} for record in trend_records]
    
    change_pct = 0.0
    if len(trend) > 1:
        prev = trend[0]["price"]
        curr = trend[-1]["price"]
        change_pct = ((curr - prev) / prev) * 100
        
    return {
        "symbol": symbol,
        "price": latest.price,
        "timestamp": latest.timestamp,
        "change_pct": round(change_pct, 2),
        "trend": trend
    }

@router.get("/fii-dii")
def get_fii_dii_data(db: Session = Depends(get_db)):
    """Get latest FII/DII flow activities."""
    latest = db.query(FiiDiiActivity).order_by(FiiDiiActivity.timestamp.desc()).first()
    if not latest:
        return {
            "timestamp": datetime.datetime.now().isoformat(),
            "fii_net": 1250.0,
            "dii_net": -450.0,
            "trend": []
        }
        
    trend_records = db.query(FiiDiiActivity).order_by(FiiDiiActivity.timestamp.desc()).limit(30).all()
    trend_records.reverse()
    trend = [
        {
            "timestamp": r.timestamp.strftime("%H:%M:%S"),
            "fii_net": r.fii_net,
            "dii_net": r.dii_net
        }
        for r in trend_records
    ]
    return {
        "timestamp": latest.timestamp,
        "fii_net": latest.fii_net,
        "dii_net": latest.dii_net,
        "trend": trend
    }

@router.get("/usdinr")
def get_usdinr_data(db: Session = Depends(get_db)):
    """Get latest USDINR spot and future rates."""
    latest_spot = db.query(SpotPrice).filter(SpotPrice.symbol == "USDINR").order_by(SpotPrice.timestamp.desc()).first()
    latest_fut = db.query(FuturePrice).filter(FuturePrice.symbol == "USDINR").order_by(FuturePrice.timestamp.desc()).first()
    
    spot_val = latest_spot.price if latest_spot else 83.55
    fut_val = latest_fut.price if latest_fut else 83.63
    ts = latest_spot.timestamp if latest_spot else datetime.datetime.now()
    
    return {
        "timestamp": ts,
        "spot": spot_val,
        "futures": fut_val
    }

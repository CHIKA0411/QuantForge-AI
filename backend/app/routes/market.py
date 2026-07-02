from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import List, Dict, Any
import datetime
from app.db import get_db, SpotPrice, OptionChain, VixData
from app.nse_client import nse_client
from app.config import settings

router = APIRouter(prefix="/market", tags=["market"])

@router.get("/spot")
def get_spot_price(symbol: str = Query(default="NIFTY", description="Symbol name (NIFTY/BANKNIFTY)"), db: Session = Depends(get_db)):
    """Get the latest spot price of the index and past 30 points trend."""
    # Find latest in DB
    latest = db.query(SpotPrice).filter(SpotPrice.symbol == symbol).order_by(SpotPrice.timestamp.desc()).first()
    
    if not latest:
        # Fallback to direct client
        data = nse_client.get_market_data(symbol)
        return {
            "symbol": symbol,
            "price": data["spot_price"],
            "timestamp": data["timestamp"],
            "trend": [{"timestamp": data["timestamp"], "price": data["spot_price"]}]
        }
        
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
    # Find the latest timestamp in OptionChain for this symbol
    latest_record = db.query(OptionChain).filter(OptionChain.symbol == symbol).order_by(OptionChain.timestamp.desc()).first()
    
    if not latest_record:
        # Fallback to direct simulation/scrape
        data = nse_client.get_market_data(symbol)
        # Compute Greeks on the fly for the response if DB is empty
        # Expiry datetime
        expiry_dt = datetime.datetime.combine(data["expiry_date"], datetime.time(15, 30))
        dt_diff = expiry_dt - data["timestamp"]
        time_to_expiry_seconds = max(1.0, dt_diff.total_seconds())
        T = time_to_expiry_seconds / (365.0 * 86400.0)
        
        # Vectorized Greeks
        import numpy as np
        from app.greeks import calculate_greeks_vectorized
        options = data["options"]
        strikes = np.array([opt["strike_price"] for opt in options])
        ivs = np.array([opt["implied_volatility"] for opt in options])
        types = np.array([opt["option_type"] for opt in options])
        
        deltas, gammas, vegas, thetas = calculate_greeks_vectorized(
            data["spot_price"], strikes, T, settings.RISK_FREE_RATE, ivs, types
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
            "spot_price": data["spot_price"],
            "timestamp": data["timestamp"],
            "expiry_date": data["expiry_date"],
            "options": response_options
        }
        
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
            "timestamp": datetime.datetime.now(),
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

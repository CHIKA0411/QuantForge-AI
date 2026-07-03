from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, Any, List, Tuple
import datetime
import numpy as np

from app.db import get_db, SpotPrice, OptionChain, VixData
from app.nse_client import nse_client
from app.config import settings

# Quantitative Engines
from app.analytics import calculate_pcr, calculate_max_pain, calculate_support_resistance, calculate_oi_analytics, calculate_max_pain_with_shift
from app.dealer import calculate_dealer_exposures, find_gamma_flip_level, generate_gex_profile
from app.volatility import get_volatility_smile, calculate_iv_skew, classify_volatility_regime, get_volatility_surface, calculate_historical_volatility, calculate_iv_rank_and_percentile, calculate_expected_moves

router = APIRouter(prefix="/analytics", tags=["analytics"])

def get_current_options_data(symbol: str, db: Session) -> Tuple[float, float, datetime.date, float, List[Dict[str, Any]]]:
    """Helper to query options chain and parameters from DB or fallback simulator."""
    latest_record = db.query(OptionChain).filter(OptionChain.symbol == symbol).order_by(OptionChain.timestamp.desc()).first()
    
    if not latest_record:
        # Prefer the live NSE snapshot when available.
        try:
            data = nse_client.get_market_data(symbol)
            if isinstance(data, dict) and data.get("options"):
                spot_price = data["spot_price"]
                vix_val = data["vix"]
                expiry_date = data["expiry_date"]
                options = data["options"]
                timestamp = data["timestamp"]

                expiry_dt = datetime.datetime.combine(expiry_date, datetime.time(15, 30))
                dt_diff = expiry_dt - timestamp
                time_to_expiry_seconds = max(1.0, dt_diff.total_seconds())
                T = time_to_expiry_seconds / (365.0 * 86400.0)

                return spot_price, vix_val, expiry_date, T, options
        except Exception:
            pass

        data = nse_client.get_market_data(symbol)
        spot_price = data["spot_price"]
        vix_val = data["vix"]
        expiry_date = data["expiry_date"]
        options = data["options"]
        timestamp = data["timestamp"]
        
        # Expiry datetime
        expiry_dt = datetime.datetime.combine(expiry_date, datetime.time(15, 30))
        dt_diff = expiry_dt - timestamp
        time_to_expiry_seconds = max(1.0, dt_diff.total_seconds())
        T = time_to_expiry_seconds / (365.0 * 86400.0)
        
        return spot_price, vix_val, expiry_date, T, options
        
    latest_ts = latest_record.timestamp
    expiry_date = latest_record.expiry_date
    
    # Query spot price at that timestamp
    spot_rec = db.query(SpotPrice).filter(SpotPrice.symbol == symbol, SpotPrice.timestamp == latest_ts).first()
    spot_price = spot_rec.price if spot_rec else 0.0
    
    # Query VIX
    vix_rec = db.query(VixData).filter(VixData.timestamp <= latest_ts).order_by(VixData.timestamp.desc()).first()
    vix_val = vix_rec.value if vix_rec else 13.5
    
    # Expiry datetime
    expiry_dt = datetime.datetime.combine(expiry_date, datetime.time(15, 30))
    dt_diff = expiry_dt - latest_ts
    time_to_expiry_seconds = max(1.0, dt_diff.total_seconds())
    T = time_to_expiry_seconds / (365.0 * 86400.0)

    # Query all options
    options_db = db.query(OptionChain).filter(
        OptionChain.symbol == symbol,
        OptionChain.timestamp == latest_ts
    ).all()
    
    options = [
        {
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
        }
        for opt in options_db
    ]
    
    return spot_price, vix_val, expiry_date, T, options

@router.get("/summary")
def get_analytics_summary(symbol: str = Query(default="NIFTY"), db: Session = Depends(get_db)):
    """Return a single summary package containing basic and advanced metrics."""
    sym = symbol.upper()
    spot_price, vix_val, expiry_date, T, options = get_current_options_data(sym, db)
    
    pcr = calculate_pcr(options, spot_price)
    max_pain_data = calculate_max_pain_with_shift(options, spot_price, db, sym)
    sr = calculate_support_resistance(options, spot_price)
    
    # Lot size selector
    if sym == "NIFTY":
        lot_size = settings.LOT_SIZE_NIFTY
    elif sym == "BANKNIFTY":
        lot_size = settings.LOT_SIZE_BANKNIFTY
    elif sym == "SENSEX":
        lot_size = settings.LOT_SIZE_SENSEX
    elif sym == "BANKEX":
        lot_size = settings.LOT_SIZE_BANKEX
    else:
        lot_size = 50
        
    exposures = calculate_dealer_exposures(options, spot_price, lot_size, T, settings.RISK_FREE_RATE)
    flip_level = find_gamma_flip_level(options, spot_price, lot_size, T, settings.RISK_FREE_RATE)
    skew = calculate_iv_skew(options, spot_price)
    regime = classify_volatility_regime(vix_val)

    # Volatility metrics
    hist_vol = calculate_historical_volatility(db, sym)
    iv_rank, iv_pct = calculate_iv_rank_and_percentile(db, sym, vix_val)
    expected_moves = calculate_expected_moves(spot_price, vix_val, expiry_date)

    return {
        "symbol": sym,
        "spot_price": spot_price,
        "expiry_date": expiry_date,
        "time_to_expiry_years": round(T, 5),
        "pcr": pcr,
        "max_pain": max_pain_data["current_max_pain"],
        "max_pain_shift": max_pain_data["shift"],
        "support_resistance": sr,
        "total_gex": round(exposures["total_gex"], 2),
        "total_dex": round(exposures["total_dex"], 2),
        "gamma_flip_level": flip_level,
        "iv_skew": skew,
        "volatility_regime": regime,
        "volatility_metrics": {
            "historical_volatility": hist_vol,
            "implied_volatility": vix_val,
            "iv_rank": iv_rank,
            "iv_percentile": iv_pct
        },
        "expected_move": expected_moves
    }

@router.get("/pcr")
def get_pcr_data(
    symbol: str = Query(default="NIFTY"),
    num_strikes: int = Query(default=5, ge=1, le=20, description="Number of strikes above and below ATM"),
    db: Session = Depends(get_db)
):
    """
    Detailed Put-Call Ratio using N strikes above and below ATM.
    Returns OI-based PCR, Volume-based PCR, ATM strike, totals, and per-strike breakdown.
    """
    spot_price, _, _, _, options = get_current_options_data(symbol, db)
    pcr = calculate_pcr(options, spot_price, num_strikes)
    return {
        "symbol": symbol,
        "spot_price": spot_price,
        **pcr
    }

@router.get("/dealer-positioning")
def get_dealer_positioning(symbol: str = Query(default="NIFTY"), db: Session = Depends(get_db)):
    """Get strike-by-strike dealer Gamma and Delta exposures, and the Gamma Flip level."""
    sym = symbol.upper()
    spot_price, _, _, T, options = get_current_options_data(sym, db)
    
    if sym == "NIFTY":
        lot_size = settings.LOT_SIZE_NIFTY
    elif sym == "BANKNIFTY":
        lot_size = settings.LOT_SIZE_BANKNIFTY
    elif sym == "SENSEX":
        lot_size = settings.LOT_SIZE_SENSEX
    elif sym == "BANKEX":
        lot_size = settings.LOT_SIZE_BANKEX
    else:
        lot_size = 50
        
    exposures = calculate_dealer_exposures(options, spot_price, lot_size, T, settings.RISK_FREE_RATE)
    flip_level = find_gamma_flip_level(options, spot_price, lot_size, T, settings.RISK_FREE_RATE)
    
    # Filter strikes close to spot for clean charting (e.g. within 6% of spot)
    filtered_strikes = []
    for strike in exposures["strikes"]:
        k = strike["strike"]
        if abs(k - spot_price) / spot_price <= 0.06:
            # Round calculations for charting JSON size
            strike_copy = strike.copy()
            for key in ["call_gex", "put_gex", "net_gex", "call_dex", "put_dex", "net_dex"]:
                strike_copy[key] = round(strike_copy[key], 2)
            filtered_strikes.append(strike_copy)

    return {
        "symbol": sym,
        "spot_price": spot_price,
        "gamma_flip_level": flip_level,
        "total_gex": round(exposures["total_gex"], 2),
        "total_dex": round(exposures["total_dex"], 2),
        "strikes": filtered_strikes
    }

@router.get("/gex-profile")
def get_gex_profile_data(symbol: str = Query(default="NIFTY"), db: Session = Depends(get_db)):
    """Get Net GEX vs Spot Price profile curve data points."""
    sym = symbol.upper()
    spot_price, _, _, T, options = get_current_options_data(sym, db)
    
    if sym == "NIFTY":
        lot_size = settings.LOT_SIZE_NIFTY
    elif sym == "BANKNIFTY":
        lot_size = settings.LOT_SIZE_BANKNIFTY
    elif sym == "SENSEX":
        lot_size = settings.LOT_SIZE_SENSEX
    elif sym == "BANKEX":
        lot_size = settings.LOT_SIZE_BANKEX
    else:
        lot_size = 50
        
    profile = generate_gex_profile(options, spot_price, lot_size, T, settings.RISK_FREE_RATE)
    flip_level = find_gamma_flip_level(options, spot_price, lot_size, T, settings.RISK_FREE_RATE)
    
    return {
        "symbol": sym,
        "spot_price": spot_price,
        "gamma_flip_level": flip_level,
        "profile": profile
    }

@router.get("/volatility-smile")
def get_vol_smile(symbol: str = Query(default="NIFTY"), db: Session = Depends(get_db)):
    """Get implied volatility smile curve (Strike vs IV)."""
    spot_price, _, _, _, options = get_current_options_data(symbol, db)
    
    # Filter strikes within 5% of spot for the smile plot
    smile_full = get_volatility_smile(options)
    smile = [s for s in smile_full if abs(s["strike"] - spot_price) / spot_price <= 0.05]
    
    return {
        "symbol": symbol,
        "spot_price": spot_price,
        "smile": smile
    }

@router.get("/volatility-surface")
def get_vol_surface(symbol: str = Query(default="NIFTY"), db: Session = Depends(get_db)):
    """Get implied volatility surface points."""
    spot_price, _, _, _, options = get_current_options_data(symbol, db)
    surface = get_volatility_surface(options, spot_price)
    
    # Limit coordinates around spot
    filtered_surface = [s for s in surface if abs(s["strike"] - spot_price) / spot_price <= 0.05]
    
    return {
        "symbol": symbol,
        "spot_price": spot_price,
        "surface": filtered_surface
    }

@router.get("/oi")
def get_oi_analytics(symbol: str = Query(default="NIFTY"), db: Session = Depends(get_db)):
    """Get detailed Open Interest analytics (Highest Call/Put, writing, unwinding, heatmap, walls)."""
    sym = symbol.upper()
    spot_price, _, _, _, options = get_current_options_data(sym, db)
    oi_data = calculate_oi_analytics(options)
    return {
        "symbol": sym,
        "spot_price": spot_price,
        **oi_data
    }

@router.get("/maxpain")
def get_max_pain(symbol: str = Query(default="NIFTY"), db: Session = Depends(get_db)):
    """Get the latest Max Pain level and shift from previous session."""
    sym = symbol.upper()
    spot_price, _, _, _, options = get_current_options_data(sym, db)
    max_pain_data = calculate_max_pain_with_shift(options, spot_price, db, sym)
    return {
        "symbol": sym,
        "spot_price": spot_price,
        "max_pain": max_pain_data["current_max_pain"],
        "shift": max_pain_data["shift"]
    }

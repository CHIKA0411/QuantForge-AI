import logging
from typing import List, Dict, Any
from math import sin as math_sin, cos as math_cos
import datetime
import random
import pandas as pd
import numpy as np
from sqlalchemy.orm import Session
from app.db import SpotPrice, OptionChain, VixData
from app.analytics import calculate_pcr, calculate_max_pain, calculate_support_resistance
from app.dealer import calculate_dealer_exposures
from app.volatility import calculate_iv_skew
from app.config import settings

logger = logging.getLogger("quantforge.ml.features")

def build_feature_record(
    spot_price: float,
    vix_value: float,
    options: List[Dict[str, Any]],
    symbol: str
) -> dict:
    """Helper to compute features for a single point in time."""
    # Compute base metrics
    pcr_dict = calculate_pcr(options)
    max_pain = calculate_max_pain(options)
    sr_dict = calculate_support_resistance(options, spot_price, limit=1)
    
    # Calculate GEX / DEX
    # Assume 7 days to expiry (0.019 years) if not calculated exactly
    T = 7.0 / 365.0
    lot_size = settings.LOT_SIZE_NIFTY if symbol == "NIFTY" else settings.LOT_SIZE_BANKNIFTY
    exposure_dict = calculate_dealer_exposures(options, spot_price, lot_size, T, settings.RISK_FREE_RATE)
    
    skew = calculate_iv_skew(options, spot_price)

    # Distances
    max_pain_dist = (spot_price - max_pain) / spot_price
    
    support = sr_dict["supports"][0]["strike"] if sr_dict["supports"] else spot_price
    resistance = sr_dict["resistances"][0]["strike"] if sr_dict["resistances"] else spot_price
    
    support_dist = (spot_price - support) / spot_price
    resistance_dist = (resistance - spot_price) / spot_price
    
    # Imbalances
    pe_oi = sum(opt["open_interest"] for opt in options if opt["option_type"] == "PE")
    ce_oi = sum(opt["open_interest"] for opt in options if opt["option_type"] == "CE")
    oi_imbalance = (pe_oi - ce_oi) / (pe_oi + ce_oi) if (pe_oi + ce_oi) > 0 else 0.0

    pe_vol = sum(opt["volume"] for opt in options if opt["option_type"] == "PE")
    ce_vol = sum(opt["volume"] for opt in options if opt["option_type"] == "CE")
    vol_imbalance = (pe_vol - ce_vol) / (pe_vol + ce_vol) if (pe_vol + ce_vol) > 0 else 0.0

    return {
        "pcr_oi": pcr_dict["pcr_oi"],
        "pcr_vol": pcr_dict["pcr_volume"],
        "vix": vix_value,
        "net_gex": exposure_dict["total_gex"],
        "net_dex": exposure_dict["total_dex"],
        "skew": skew,
        "max_pain_dist": max_pain_dist,
        "support_dist": support_dist,
        "resistance_dist": resistance_dist,
        "oi_imbalance": oi_imbalance,
        "vol_imbalance": vol_imbalance
    }

def get_historical_features(db: Session, symbol: str, limit: int = 500) -> pd.DataFrame:
    """
    Query the database to build a historical DataFrame of features.
    If database records are sparse, generates a realistic synthetic history for bootstrapping.
    """
    logger.info(f"Building historical features for {symbol} (limit: {limit})...")
    
    # Query timestamps from spot prices
    spot_records = db.query(SpotPrice).filter(SpotPrice.symbol == symbol).order_by(SpotPrice.timestamp.desc()).limit(limit).all()
    spot_records.reverse()  # chronological order
    
    if len(spot_records) < 15:
        logger.info("Insufficient database records for training. Generating synthetic history dataset...")
        return generate_synthetic_history(symbol, limit)

    feature_list = []
    
    for spot in spot_records:
        ts = spot.timestamp
        # Find corresponding options and vix
        options_db = db.query(OptionChain).filter(
            OptionChain.symbol == symbol,
            OptionChain.timestamp == ts
        ).all()
        
        vix_db = db.query(VixData).filter(VixData.timestamp <= ts).order_by(VixData.timestamp.desc()).first()
        vix_val = vix_db.value if vix_db else 13.5
        
        if not options_db:
            continue
            
        options = [
            {
                "strike_price": opt.strike_price,
                "option_type": opt.option_type,
                "open_interest": opt.open_interest,
                "volume": opt.volume,
                "implied_volatility": opt.implied_volatility,
                "last_price": opt.last_price,
                "bid_price": opt.bid_price,
                "ask_price": opt.ask_price
            }
            for opt in options_db
        ]
        
        feats = build_feature_record(spot.price, vix_val, options, symbol)
        feats["timestamp"] = ts
        feats["spot_price"] = spot.price
        feature_list.append(feats)

    df = pd.DataFrame(feature_list)
    
    # Calculate target label (next return direction, e.g. 15 intervals forward)
    # We will simulate targets if historical dataset is short
    if not df.empty and len(df) > 10:
        # 15-period return
        df["future_return"] = df["spot_price"].shift(-15) - df["spot_price"]
        df["target"] = np.where(df["future_return"] > (df["spot_price"] * 0.0015), 1, 0) # Up
        df.loc[df["future_return"] < -(df["spot_price"] * 0.0015), "target"] = 2 # Down
        df["target"] = df["target"].fillna(0).astype(int) # 0 is Neutral
        df = df.dropna()
    else:
        return generate_synthetic_history(symbol, limit)
        
    return df

def generate_synthetic_history(symbol: str, count: int) -> pd.DataFrame:
    """Generate realistic synthetic feature history for training/inference booting."""
    np.random.seed(42)
    
    base_spot = 24000.0 if symbol == "NIFTY" else 52000.0
    start_time = datetime.datetime.now() - datetime.timedelta(days=10)
    
    timestamps = [start_time + datetime.timedelta(minutes=i) for i in range(count)]
    
    # Generate spot random walk
    spots = [base_spot]
    for _ in range(count - 1):
        spots.append(spots[-1] * (1.0 + random.normalvariate(0.0, 0.0008)))
        
    vixes = [13.5]
    for _ in range(count - 1):
        vixes.append(max(9.0, vixes[-1] + random.normalvariate(0.0, 0.05)))

    features = []
    for i in range(count):
        s = spots[i]
        v = vixes[i]
        
        # PCR cycles around 0.8 - 1.2
        pcr_oi = 1.0 + 0.15 * math_sin(i/20.0) + random.normalvariate(0, 0.05)
        pcr_vol = 1.0 + 0.20 * math_sin(i/15.0) + random.normalvariate(0, 0.08)
        
        # GEX peaks/valleys
        net_gex = 5000000.0 * math_sin(i/30.0) + random.normalvariate(0, 1000000)
        net_dex = 15000000.0 * math_cos(i/25.0) + random.normalvariate(0, 3000000)
        
        skew = 4.0 + 1.2 * math_sin(i/40.0) + random.normalvariate(0, 0.3)
        
        max_pain_dist = 0.005 * math_sin(i/10.0) + random.normalvariate(0, 0.002)
        support_dist = 0.015 + 0.005 * math_cos(i/12.0)
        resistance_dist = 0.015 - 0.005 * math_cos(i/12.0)
        
        oi_imbalance = 0.1 * math_sin(i/20.0)
        vol_imbalance = 0.15 * math_sin(i/15.0)

        features.append({
            "timestamp": timestamps[i],
            "spot_price": s,
            "pcr_oi": pcr_oi,
            "pcr_vol": pcr_vol,
            "vix": v,
            "net_gex": net_gex,
            "net_dex": net_dex,
            "skew": skew,
            "max_pain_dist": max_pain_dist,
            "support_dist": support_dist,
            "resistance_dist": resistance_dist,
            "oi_imbalance": oi_imbalance,
            "vol_imbalance": vol_imbalance
        })
        
    df = pd.DataFrame(features)
    
    # Set targets
    df["future_return"] = df["spot_price"].shift(-15) - df["spot_price"]
    
    # 0 = Neutral, 1 = Up, 2 = Down
    df["target"] = np.where(df["future_return"] > (df["spot_price"] * 0.0012), 1, 0)
    df.loc[df["future_return"] < -(df["spot_price"] * 0.0012), "target"] = 2
    df["target"] = df["target"].fillna(0).astype(int)
    
    # Clean up future return column so we don't cheat
    df = df.drop(columns=["future_return"])
    df = df.dropna()
    
    return df


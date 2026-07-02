from typing import List, Dict, Any, Tuple
import numpy as np

def calculate_pcr(options: List[Dict[str, Any]]) -> Dict[str, float]:
    """Calculate Put-Call Ratio based on Open Interest and Volume."""
    pe_oi = 0.0
    ce_oi = 0.0
    pe_vol = 0.0
    ce_vol = 0.0
    
    for opt in options:
        oi = opt.get("open_interest", 0.0)
        vol = opt.get("volume", 0.0)
        if opt.get("option_type") == "PE":
            pe_oi += oi
            pe_vol += vol
        elif opt.get("option_type") == "CE":
            ce_oi += oi
            ce_vol += vol
            
    pcr_oi = pe_oi / ce_oi if ce_oi > 0 else 0.0
    pcr_vol = pe_vol / ce_vol if ce_vol > 0 else 0.0
    
    return {
        "pcr_oi": round(pcr_oi, 4),
        "pcr_volume": round(pcr_vol, 4)
    }

def calculate_max_pain(options: List[Dict[str, Any]]) -> float:
    """
    Calculate the Max Pain level.
    Max Pain is the strike price where the sum of the value of all CE and PE options is minimized.
    """
    if not options:
        return 0.0
        
    strikes = sorted(list(set(opt["strike_price"] for opt in options)))
    
    min_pain = float("inf")
    max_pain_strike = strikes[0] if strikes else 0.0
    
    for test_strike in strikes:
        total_pain = 0.0
        for opt in options:
            oi = opt.get("open_interest", 0.0)
            strike = opt["strike_price"]
            opt_type = opt["option_type"]
            
            if opt_type == "CE":
                # Calls are worth max(0, expiry_price - strike)
                total_pain += max(0.0, test_strike - strike) * oi
            elif opt_type == "PE":
                # Puts are worth max(0, strike - expiry_price)
                total_pain += max(0.0, strike - test_strike) * oi
                
        if total_pain < min_pain:
            min_pain = total_pain
            max_pain_strike = test_strike
            
    return float(max_pain_strike)

def calculate_support_resistance(options: List[Dict[str, Any]], spot_price: float, limit: int = 3) -> Dict[str, List[Dict[str, Any]]]:
    """
    Identify support and resistance levels.
    Support: Strike prices with the highest PE Open Interest.
    Resistance: Strike prices with the highest CE Open Interest.
    """
    ce_strikes = []
    pe_strikes = []
    
    for opt in options:
        strike = opt["strike_price"]
        oi = opt.get("open_interest", 0.0)
        opt_type = opt["option_type"]
        
        if opt_type == "CE":
            ce_strikes.append({"strike": strike, "oi": oi})
        elif opt_type == "PE":
            pe_strikes.append({"strike": strike, "oi": oi})
            
    # Sort descending by OI
    ce_sorted = sorted(ce_strikes, key=lambda x: x["oi"], reverse=True)
    pe_sorted = sorted(pe_strikes, key=lambda x: x["oi"], reverse=True)
    
    # Take top levels
    resistances = ce_sorted[:limit]
    supports = pe_sorted[:limit]
    
    # Sort by strike for logical ordered display (optional, but sorting by OI is primary)
    return {
        "supports": sorted(supports, key=lambda x: x["strike"]),
        "resistances": sorted(resistances, key=lambda x: x["strike"])
    }

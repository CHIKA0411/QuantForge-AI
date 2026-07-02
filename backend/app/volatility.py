from typing import List, Dict, Any
import numpy as np

def get_volatility_smile(options: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Get Strike vs IV for Calls and Puts for the nearest expiry.
    Returns a sorted list of dicts for plotting.
    """
    smile_data = {}
    for opt in options:
        strike = opt["strike_price"]
        opt_type = opt["option_type"]
        iv = opt.get("implied_volatility", 0.0)
        
        if strike not in smile_data:
            smile_data[strike] = {"strike": strike, "call_iv": None, "put_iv": None}
            
        if opt_type == "CE":
            smile_data[strike]["call_iv"] = round(iv * 100, 2)  # Convert to percent
        elif opt_type == "PE":
            smile_data[strike]["put_iv"] = round(iv * 100, 2)
            
    # Sort by strike and filter out entries with no IV
    sorted_smile = sorted(list(smile_data.values()), key=lambda x: x["strike"])
    return sorted_smile

def calculate_iv_skew(options: List[Dict[str, Any]], spot_price: float) -> float:
    """
    Calculate the Implied Volatility Skew.
    Defined here as: OTM Put IV (95% moneyness) - OTM Call IV (105% moneyness)
    """
    if not options:
        return 0.0

    put_options = [opt for opt in options if opt["option_type"] == "PE"]
    call_options = [opt for opt in options if opt["option_type"] == "CE"]
    
    if not put_options or not call_options:
        return 0.0

    # Target strikes
    put_target = spot_price * 0.95
    call_target = spot_price * 1.05
    
    # Find closest strikes
    closest_put_opt = min(put_options, key=lambda x: abs(x["strike_price"] - put_target))
    closest_call_opt = min(call_options, key=lambda x: abs(x["strike_price"] - call_target))
    
    put_iv = closest_put_opt.get("implied_volatility", 0.0)
    call_iv = closest_call_opt.get("implied_volatility", 0.0)
    
    skew = put_iv - call_iv
    return float(round(skew * 100, 2))  # Express in percentage points

def classify_volatility_regime(vix_value: float) -> Dict[str, Any]:
    """
    Classify the current market volatility regime based on VIX.
    """
    if vix_value < 12.0:
        regime = "Low Volatility"
        description = "Market is in an expansionary, low-hedging phase. Risk-on assets are generally favored, and option premiums are cheap."
        color = "emerald"
    elif vix_value < 16.0:
        regime = "Normal / Balanced"
        description = "Typical volatility environment. Stable dealer hedging pressures. Option prices reflect standard market expectations."
        color = "blue"
    elif vix_value < 22.0:
        regime = "Elevated Risk"
        description = "Increasing market uncertainty. Option premiums are expanding. Gamma flip zones should be closely watched as dealer hedging may accelerate swings."
        color = "amber"
    else:
        regime = "Extreme Volatility"
        description = "High panic/hedging regime. Dealers are likely short gamma, leading to high correlation and rapid price adjustments. Option buying is expensive."
        color = "rose"

    return {
        "vix": vix_value,
        "regime": regime,
        "description": description,
        "color": color
    }

def get_volatility_surface(options: List[Dict[str, Any]], spot_price: float) -> List[Dict[str, Any]]:
    """
    Generate data points representing the Implied Volatility Surface.
    Specifically: Strike (Moneyness %) vs Expiry/Distance vs IV.
    """
    surface_points = []
    for opt in options:
        strike = opt["strike_price"]
        iv = opt.get("implied_volatility", 0.0)
        opt_type = opt["option_type"]
        
        # We only plot options with valid IVs
        if iv <= 0:
            continue
            
        moneyness = (strike / spot_price) * 100
        
        # Filter for OTM options for surface calculation to represent cleaner smile structure
        is_otm = (opt_type == "CE" and strike >= spot_price) or (opt_type == "PE" and strike <= spot_price)
        if not is_otm:
            continue
            
        surface_points.append({
            "strike": strike,
            "moneyness": round(moneyness, 1),
            "option_type": opt_type,
            "iv": round(iv * 100, 2)
        })
        
    return sorted(surface_points, key=lambda x: x["strike"])

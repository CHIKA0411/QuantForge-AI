from typing import List, Dict, Any, Tuple
import numpy as np

def calculate_pcr(options: List[Dict[str, Any]], spot_price: float = 0.0, num_strikes: int = 5) -> Dict[str, Any]:
    """
    Calculate Put-Call Ratio based on Open Interest and Volume.
    
    Uses only `num_strikes` strikes above and below the ATM strike for a focused,
    near-the-money PCR that filters out far OTM noise — the standard institutional approach.
    
    Args:
        options: List of option contract dicts with strike_price, option_type, open_interest, volume.
        spot_price: Current spot/underlying price used to determine ATM strike.
        num_strikes: Number of strikes to include above and below ATM (default 5).
    
    Returns:
        Dict with pcr_oi, pcr_volume, atm_strike, selected strikes detail, and totals.
    """
    if not options or spot_price <= 0:
        # Fallback: use all strikes (legacy behavior)
        pe_oi = sum(o.get("open_interest", 0.0) for o in options if o.get("option_type") == "PE")
        ce_oi = sum(o.get("open_interest", 0.0) for o in options if o.get("option_type") == "CE")
        pe_vol = sum(o.get("volume", 0.0) for o in options if o.get("option_type") == "PE")
        ce_vol = sum(o.get("volume", 0.0) for o in options if o.get("option_type") == "CE")
        pcr_oi = pe_oi / ce_oi if ce_oi > 0 else 0.0
        pcr_vol = pe_vol / ce_vol if ce_vol > 0 else 0.0
        return {
            "pcr_oi": round(pcr_oi, 4),
            "pcr_volume": round(pcr_vol, 4),
            "atm_strike": 0.0,
            "strikes_used": 0,
            "total_pe_oi": round(pe_oi, 0),
            "total_ce_oi": round(ce_oi, 0),
            "total_pe_volume": round(pe_vol, 0),
            "total_ce_volume": round(ce_vol, 0),
            "strike_details": []
        }

    # 1. Collect all unique strikes sorted
    all_strikes = sorted(set(o["strike_price"] for o in options))

    # 2. Identify ATM strike (closest to spot)
    atm_strike = min(all_strikes, key=lambda s: abs(s - spot_price))

    # 3. Separate strikes into below-ATM and above-ATM (excluding ATM itself initially)
    strikes_below = [s for s in all_strikes if s < atm_strike]
    strikes_above = [s for s in all_strikes if s > atm_strike]

    # Take the nearest `num_strikes` on each side
    # Below: take last N from the sorted-ascending list (closest to ATM)
    selected_below = strikes_below[-num_strikes:] if len(strikes_below) >= num_strikes else strikes_below
    # Above: take first N from the sorted-ascending list (closest to ATM)
    selected_above = strikes_above[:num_strikes] if len(strikes_above) >= num_strikes else strikes_above

    selected_strikes = set(selected_below + [atm_strike] + selected_above)

    # 4. Aggregate OI and Volume for selected strikes only
    pe_oi = 0.0
    ce_oi = 0.0
    pe_vol = 0.0
    ce_vol = 0.0

    # Build per-strike detail
    strike_ce_map: Dict[float, Dict[str, float]] = {}
    strike_pe_map: Dict[float, Dict[str, float]] = {}

    for opt in options:
        strike = opt["strike_price"]
        if strike not in selected_strikes:
            continue

        oi = opt.get("open_interest", 0.0)
        vol = opt.get("volume", 0.0)
        opt_type = opt.get("option_type")

        if opt_type == "PE":
            pe_oi += oi
            pe_vol += vol
            strike_pe_map[strike] = {"oi": oi, "volume": vol}
        elif opt_type == "CE":
            ce_oi += oi
            ce_vol += vol
            strike_ce_map[strike] = {"oi": oi, "volume": vol}

    pcr_oi = pe_oi / ce_oi if ce_oi > 0 else 0.0
    pcr_vol = pe_vol / ce_vol if ce_vol > 0 else 0.0

    # 5. Build ordered strike details for frontend display
    strike_details = []
    for strike in sorted(selected_strikes):
        ce_data = strike_ce_map.get(strike, {"oi": 0, "volume": 0})
        pe_data = strike_pe_map.get(strike, {"oi": 0, "volume": 0})
        strike_details.append({
            "strike": strike,
            "ce_oi": ce_data["oi"],
            "pe_oi": pe_data["oi"],
            "ce_volume": ce_data["volume"],
            "pe_volume": pe_data["volume"],
            "is_atm": strike == atm_strike
        })

    return {
        "pcr_oi": round(pcr_oi, 4),
        "pcr_volume": round(pcr_vol, 4),
        "atm_strike": atm_strike,
        "strikes_used": len(selected_strikes),
        "num_strikes_each_side": num_strikes,
        "total_pe_oi": round(pe_oi, 0),
        "total_ce_oi": round(ce_oi, 0),
        "total_pe_volume": round(pe_vol, 0),
        "total_ce_volume": round(ce_vol, 0),
        "strike_details": strike_details
    }

def calculate_max_pain(options: List[Dict[str, Any]], spot_price: float = 0.0, num_strikes: int = 5) -> float:
    """
    Calculate the Max Pain level.
    Max Pain is the strike price where the sum of the value of all CE and PE options is minimized.
    """
    if not options:
        return 0.0
        
    all_strikes = sorted(list(set(opt["strike_price"] for opt in options)))
    
    if spot_price > 0:
        atm_strike = min(all_strikes, key=lambda s: abs(s - spot_price))
        strikes_below = [s for s in all_strikes if s < atm_strike]
        strikes_above = [s for s in all_strikes if s > atm_strike]
        
        selected_below = strikes_below[-num_strikes:] if len(strikes_below) >= num_strikes else strikes_below
        selected_above = strikes_above[:num_strikes] if len(strikes_above) >= num_strikes else strikes_above
        selected_strikes = set(selected_below + [atm_strike] + selected_above)
        
        options = [opt for opt in options if opt["strike_price"] in selected_strikes]
        strikes = sorted(list(selected_strikes))
    else:
        strikes = all_strikes
    
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

def calculate_oi_analytics(options: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Calculate OI breakdown, writing/unwinding trends, strike heatmap, and walls.
    """
    ce_options = [opt for opt in options if opt["option_type"] == "CE"]
    pe_options = [opt for opt in options if opt["option_type"] == "PE"]
    
    # Walls
    call_wall = max(ce_options, key=lambda x: x["open_interest"]) if ce_options else {"strike_price": 0.0, "open_interest": 0}
    put_wall = max(pe_options, key=lambda x: x["open_interest"]) if pe_options else {"strike_price": 0.0, "open_interest": 0}
    
    # Heatmap (top 10 by OI)
    top_calls = sorted(ce_options, key=lambda x: x["open_interest"], reverse=True)[:10]
    top_puts = sorted(pe_options, key=lambda x: x["open_interest"], reverse=True)[:10]
    
    # Writing (highest positive change in OI)
    ce_writing = sorted([opt for opt in ce_options if opt.get("change_in_oi", 0) > 0], key=lambda x: x["change_in_oi"], reverse=True)[:3]
    pe_writing = sorted([opt for opt in pe_options if opt.get("change_in_oi", 0) > 0], key=lambda x: x["change_in_oi"], reverse=True)[:3]
    
    # Unwinding (highest negative change in OI)
    ce_unwinding = sorted([opt for opt in ce_options if opt.get("change_in_oi", 0) < 0], key=lambda x: x["change_in_oi"])[:3]
    pe_unwinding = sorted([opt for opt in pe_options if opt.get("change_in_oi", 0) < 0], key=lambda x: x["change_in_oi"])[:3]
    
    def _format_strike_list(opts):
        return [{"strike": o["strike_price"], "oi": o["open_interest"], "change_oi": o.get("change_in_oi", 0.0)} for o in opts]
        
    return {
        "call_wall": {"strike": call_wall.get("strike_price", 0.0), "oi": call_wall.get("open_interest", 0.0)},
        "put_wall": {"strike": put_wall.get("strike_price", 0.0), "oi": put_wall.get("open_interest", 0.0)},
        "strike_heatmap": {
            "calls": _format_strike_list(top_calls),
            "puts": _format_strike_list(top_puts)
        },
        "writing": {
            "calls": _format_strike_list(ce_writing),
            "puts": _format_strike_list(pe_writing)
        },
        "unwinding": {
            "calls": _format_strike_list(ce_unwinding),
            "puts": _format_strike_list(pe_unwinding)
        }
    }

def calculate_max_pain_with_shift(
    options: List[Dict[str, Any]], 
    spot_price: float, 
    db: Any = None, 
    symbol: str = "",
    num_strikes: int = 5
) -> Dict[str, Any]:
    """Calculate current max pain level and the shift difference compared to previous session."""
    current_max_pain = calculate_max_pain(options, spot_price, num_strikes)
    
    if not db or not symbol:
        return {"current_max_pain": current_max_pain, "shift": 0.0}
        
    try:
        from app.db import OptionChain
        # Get last 2 distinct timestamps in options database
        timestamps = db.query(OptionChain.timestamp).filter(OptionChain.symbol == symbol).distinct().order_by(OptionChain.timestamp.desc()).limit(2).all()
        if len(timestamps) >= 2:
            prev_ts = timestamps[1][0]
            prev_options_db = db.query(OptionChain).filter(OptionChain.symbol == symbol, OptionChain.timestamp == prev_ts).all()
            if prev_options_db:
                prev_options = [
                    {
                        "strike_price": opt.strike_price,
                        "option_type": opt.option_type,
                        "open_interest": opt.open_interest,
                        "volume": opt.volume
                    }
                    for opt in prev_options_db
                ]
                prev_max_pain = calculate_max_pain(prev_options, 0.0, num_strikes)
                shift = current_max_pain - prev_max_pain
                return {"current_max_pain": current_max_pain, "shift": shift}
    except Exception:
        pass
        
    return {"current_max_pain": current_max_pain, "shift": 0.0}

from typing import List, Dict, Any, Tuple
import numpy as np
from app.greeks import calculate_greeks_vectorized

def calculate_dealer_exposures(
    options: List[Dict[str, Any]],
    spot_price: float,
    lot_size: int,
    T: float,
    r: float
) -> Dict[str, Any]:
    """
    Calculate Gamma Exposure (GEX) and Delta Exposure (DEX) for each option contract,
    as well as aggregate metrics.
    
    Formula:
    Call GEX = OI * Gamma * Lot Size * Spot * 0.01
    Put GEX  = -OI * Gamma * Lot Size * Spot * 0.01 (assuming dealers are short puts to retail buyers)
    Call DEX = OI * Delta * Lot Size
    Put DEX  = OI * Delta * Lot Size (signed Delta)
    """
    if not options:
        return {"total_gex": 0.0, "total_dex": 0.0, "strikes": {}}

    # Extract vectors for Greeks calculation
    strikes = np.array([opt["strike_price"] for opt in options])
    ivs = np.array([opt["implied_volatility"] for opt in options])
    types = np.array([opt["option_type"] for opt in options])
    ois = np.array([opt["open_interest"] for opt in options])

    # Calculate Greeks
    deltas, gammas, _, _ = calculate_greeks_vectorized(spot_price, strikes, T, r, ivs, types)

    # Compute GEX and DEX
    # Call GEX is positive, Put GEX is negative
    gex_multipliers = np.where(types == "CE", 1.0, -1.0)
    gex_values = ois * gammas * lot_size * spot_price * 0.01 * gex_multipliers
    
    # Delta exposure uses signed Delta (Call Delta is positive, Put Delta is negative)
    dex_values = ois * deltas * lot_size

    total_gex = float(np.sum(gex_values))
    total_dex = float(np.sum(dex_values))

    # Group by strike price for dashboard representation
    strike_data = {}
    for i, opt in enumerate(options):
        strike = opt["strike_price"]
        opt_type = opt["option_type"]
        gex = float(gex_values[i])
        dex = float(dex_values[i])
        
        if strike not in strike_data:
            strike_data[strike] = {"strike": strike, "call_gex": 0.0, "put_gex": 0.0, "net_gex": 0.0, "call_dex": 0.0, "put_dex": 0.0, "net_dex": 0.0}
            
        if opt_type == "CE":
            strike_data[strike]["call_gex"] += gex
            strike_data[strike]["call_dex"] += dex
        else:
            strike_data[strike]["put_gex"] += gex
            strike_data[strike]["put_dex"] += dex
            
        strike_data[strike]["net_gex"] += gex
        strike_data[strike]["net_dex"] += dex

    # Convert to sorted list of strikes
    sorted_strikes = sorted(list(strike_data.values()), key=lambda x: x["strike"])

    return {
        "total_gex": total_gex,
        "total_dex": total_dex,
        "strikes": sorted_strikes
    }

def find_gamma_flip_level(
    options: List[Dict[str, Any]],
    current_spot: float,
    lot_size: int,
    T: float,
    r: float
) -> float:
    """
    Find the Gamma Flip level by evaluating Net GEX across a grid of spot prices
    around the current spot price.
    """
    if not options:
        return current_spot

    # Extract vectors
    strikes = np.array([opt["strike_price"] for opt in options])
    ivs = np.array([opt["implied_volatility"] for opt in options])
    types = np.array([opt["option_type"] for opt in options])
    ois = np.array([opt["open_interest"] for opt in options])
    gex_multipliers = np.where(types == "CE", 1.0, -1.0)

    # Helper function to compute Net GEX for a given spot price
    def get_net_gex_for_spot(test_spot: float) -> float:
        _, gammas, _, _ = calculate_greeks_vectorized(test_spot, strikes, T, r, ivs, types)
        gex_vals = ois * gammas * lot_size * test_spot * 0.01 * gex_multipliers
        return float(np.sum(gex_vals))

    # Define spot price grid: +/- 10% around current spot, 60 points
    spot_min = current_spot * 0.90
    spot_max = current_spot * 1.10
    spot_grid = np.linspace(spot_min, spot_max, 60)
    
    gex_grid = []
    for test_spot in spot_grid:
        gex_grid.append(get_net_gex_for_spot(test_spot))
        
    gex_grid = np.array(gex_grid)

    # Find where GEX crosses zero (sign change)
    for i in range(len(spot_grid) - 1):
        if gex_grid[i] * gex_grid[i+1] <= 0:
            # Linear interpolation to find the exact zero crossing point
            s0, s1 = spot_grid[i], spot_grid[i+1]
            g0, g1 = gex_grid[i], gex_grid[i+1]
            if g1 - g0 == 0:
                return float(s0)
            flip_level = s0 - g0 * (s1 - s0) / (g1 - g0)
            return float(round(flip_level, 2))

    # If no flip level found in +/-10% range, return the current spot as default
    return current_spot

def generate_gex_profile(
    options: List[Dict[str, Any]],
    current_spot: float,
    lot_size: int,
    T: float,
    r: float
) -> List[Dict[str, Any]]:
    """
    Generate Net GEX values across a grid of spot prices to plot the GEX profile curve
    on the dashboard.
    """
    if not options:
        return []

    strikes = np.array([opt["strike_price"] for opt in options])
    ivs = np.array([opt["implied_volatility"] for opt in options])
    types = np.array([opt["option_type"] for opt in options])
    ois = np.array([opt["open_interest"] for opt in options])
    gex_multipliers = np.where(types == "CE", 1.0, -1.0)

    # 40 points in a +/- 5% range
    spot_min = current_spot * 0.95
    spot_max = current_spot * 1.05
    spot_grid = np.linspace(spot_min, spot_max, 40)
    
    profile = []
    for test_spot in spot_grid:
        _, gammas, _, _ = calculate_greeks_vectorized(test_spot, strikes, T, r, ivs, types)
        gex_vals = ois * gammas * lot_size * test_spot * 0.01 * gex_multipliers
        net_gex = float(np.sum(gex_vals))
        profile.append({
            "spot_price": round(float(test_spot), 2),
            "net_gex": round(net_gex, 2)
        })
        
    return profile

import sys
import os
import numpy as np

# Add backend directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.greeks import calculate_greeks_vectorized

def test_greeks():
    print("Testing options Greeks calculations...")
    
    # Inputs: spot=24000, strike=24000 (ATM), T=0.05 (~18 days), r=0.07, IV=15%, Call & Put
    S = 24000.0
    K = np.array([24000.0, 24000.0])
    T = 0.05
    r = 0.07
    sigma = np.array([0.15, 0.15])
    option_type = np.array(["CE", "PE"])
    
    deltas, gammas, vegas, thetas = calculate_greeks_vectorized(S, K, T, r, sigma, option_type)
    
    print(f"ATM Call Delta: {deltas[0]:.4f} (Expected: ~0.53)")
    print(f"ATM Put Delta: {deltas[1]:.4f} (Expected: ~-0.47)")
    print(f"Gamma: {gammas[0]:.8f} (Expected: positive)")
    print(f"Vega: {vegas[0]:.4f} (Expected: positive)")
    print(f"Call Theta (Daily): {thetas[0]:.4f} (Expected: negative)")
    print(f"Put Theta (Daily): {thetas[1]:.4f} (Expected: negative)")
    
    # Assertions
    assert 0.45 < deltas[0] < 0.60, f"Unexpected Call Delta: {deltas[0]}"
    assert -0.55 < deltas[1] < -0.40, f"Unexpected Put Delta: {deltas[1]}"
    assert gammas[0] > 0, "Gamma must be positive"
    assert gammas[0] == gammas[1], "Call and Put Gamma must be identical"
    assert vegas[0] > 0, "Vega must be positive"
    assert vegas[0] == vegas[1], "Call and Put Vega must be identical"
    assert thetas[0] < 0, "Call Theta must be negative"
    assert thetas[1] < 0, "Put Theta must be negative"
    
    # Test expiration edge case
    print("\nTesting Greeks at expiration (T=0)...")
    deltas_exp, gammas_exp, vegas_exp, thetas_exp = calculate_greeks_vectorized(
        S, np.array([23800.0, 24200.0]), 0.0, r, sigma, np.array(["CE", "PE"])
    )
    # 23800 Call is ITM at spot 24000 -> Delta should be 1
    # 24200 Put is ITM at spot 24000 -> Delta should be -1
    print(f"ITM Call Delta at Expiry: {deltas_exp[0]:.1f} (Expected: 1.0)")
    print(f"ITM Put Delta at Expiry: {deltas_exp[1]:.1f} (Expected: -1.0)")
    
    assert deltas_exp[0] == 1.0, "ITM Call Delta at expiry should be 1"
    assert deltas_exp[1] == -1.0, "ITM Put Delta at expiry should be -1"
    assert gammas_exp[0] == 0.0, "Gamma at expiry should be 0"
    assert vegas_exp[0] == 0.0, "Vega at expiry should be 0"
    assert thetas_exp[0] == 0.0, "Theta at expiry should be 0"

    print("\nAll Greeks tests passed successfully!")

if __name__ == "__main__":
    test_greeks()

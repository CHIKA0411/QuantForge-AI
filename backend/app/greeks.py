import numpy as np
from scipy.stats import norm

def calculate_greeks_vectorized(
    S: float,
    K: np.ndarray,
    T: float,
    r: float,
    sigma: np.ndarray,
    option_type: np.ndarray
):
    """
    Vectorized BSM Greeks calculation.
    
    Parameters:
    S (float): Spot price
    K (np.ndarray): Array of strike prices
    T (float): Time to maturity in years (fraction of 365 days)
    r (float): Risk-free interest rate
    sigma (np.ndarray): Array of implied volatilities (decimal, e.g. 0.15)
    option_type (np.ndarray): Array of 'CE' or 'PE' strings
    
    Returns:
    Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]: (delta, gamma, vega, theta)
    """
    K = np.array(K, dtype=float)
    sigma = np.array(sigma, dtype=float)
    option_type = np.array(option_type)
    
    # Pre-allocate output arrays
    delta = np.zeros_like(K, dtype=float)
    gamma = np.zeros_like(K, dtype=float)
    vega = np.zeros_like(K, dtype=float)
    theta = np.zeros_like(K, dtype=float)
    
    # Avoid division by zero by filtering for T > 0 and IV > 0
    valid_mask = (T > 0) & (sigma > 0)
    
    if np.any(valid_mask):
        K_val = K[valid_mask]
        sig_val = sigma[valid_mask]
        opt_val = option_type[valid_mask]
        
        # Intermediate d1 and d2 calculations
        d1 = (np.log(S / K_val) + (r + 0.5 * sig_val**2) * T) / (sig_val * np.sqrt(T))
        d2 = d1 - sig_val * np.sqrt(T)
        
        # Normal CDF and PDF
        N_d1 = norm.cdf(d1)
        N_d2 = norm.cdf(d2)
        N_minus_d1 = norm.cdf(-d1)
        N_minus_d2 = norm.cdf(-d2)
        n_prime_d1 = norm.pdf(d1)
        
        # Gamma and Vega (identical for Calls and Puts)
        gamma[valid_mask] = n_prime_d1 / (S * sig_val * np.sqrt(T))
        vega[valid_mask] = S * n_prime_d1 * np.sqrt(T) * 0.01  # normalized for a 1% (0.01) change in IV
        
        is_call = (opt_val == "CE")
        
        # Delta
        delta[valid_mask] = np.where(is_call, N_d1, N_d1 - 1.0)
        
        # Theta (annual theta divided by 365 to get daily decay)
        theta_call = -(S * n_prime_d1 * sig_val) / (2 * np.sqrt(T)) - r * K_val * np.exp(-r * T) * N_d2
        theta_put = -(S * n_prime_d1 * sig_val) / (2 * np.sqrt(T)) + r * K_val * np.exp(-r * T) * N_minus_d2
        
        theta[valid_mask] = np.where(is_call, theta_call, theta_put) / 365.0
        
    # Handle expiration day (T = 0)
    invalid_mask = ~valid_mask
    if np.any(invalid_mask):
        K_invalid = K[invalid_mask]
        option_type_invalid = option_type[invalid_mask]
        is_call = (option_type_invalid == "CE")
        
        # Delta at expiry is 1.0 (Call) or -1.0 (Put) if in-the-money
        delta[invalid_mask] = np.where(
            is_call,
            np.where(S > K_invalid, 1.0, 0.0),
            np.where(S < K_invalid, -1.0, 0.0)
        )
        gamma[invalid_mask] = 0.0
        vega[invalid_mask] = 0.0
        theta[invalid_mask] = 0.0
        
    return delta, gamma, vega, theta

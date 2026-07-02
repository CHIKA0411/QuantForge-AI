import time
import random
import logging
import requests
import datetime
from typing import Dict, Any, List, Optional
from app.config import settings

logger = logging.getLogger("quantforge.nse")
logging.basicConfig(level=logging.INFO)

# Global variables to simulate running spot prices (so they drift over time)
_sim_spot_prices = {
    "NIFTY": 24250.0,
    "BANKNIFTY": 52100.0
}
_sim_vix = 13.6

class NSEClient:
    def __init__(self):
        self.session = requests.Session()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Host': 'www.nseindia.com',
            'Referer': 'https://www.nseindia.com/option-chain',
            'Connection': 'keep-alive'
        }
        self.cookies_loaded = False
        self.last_cookie_time = 0

    def _load_cookies(self) -> bool:
        """Prime the session by visiting the home/option-chain page to obtain cookies."""
        try:
            logger.info("Initializing NSE website session cookies...")
            self.session.cookies.clear()
            # Visit option-chain page
            response = self.session.get("https://www.nseindia.com/option-chain", headers=self.headers, timeout=5)
            if response.status_code == 200:
                self.cookies_loaded = True
                self.last_cookie_time = time.time()
                logger.info("NSE session cookies acquired successfully.")
                return True
            else:
                logger.warning(f"Failed to get NSE cookies. Status: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"Error fetching NSE cookies: {e}")
            return False

    def fetch_live_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Fetch raw option chain JSON directly from NSE API."""
        # Refresh cookies every 10 minutes
        if not self.cookies_loaded or (time.time() - self.last_cookie_time > 600):
            self._load_cookies()

        url = f"https://www.nseindia.com/api/option-chain-indices?symbol={symbol}"
        try:
            logger.info(f"Scraping live NSE Option Chain for {symbol}...")
            response = self.session.get(url, headers=self.headers, timeout=5)
            
            # Handle rate-limiting (401/403) by retrying with fresh cookies once
            if response.status_code in [401, 403]:
                logger.warning("Session expired or blocked. Refreshing cookies and retrying...")
                self._load_cookies()
                response = self.session.get(url, headers=self.headers, timeout=5)

            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"NSE API returned status {response.status_code} for {symbol}")
                return None
        except Exception as e:
            logger.error(f"Network error when calling NSE API for {symbol}: {e}")
            return None

    def get_market_data(self, symbol: str) -> Dict[str, Any]:
        """
        Public API to fetch market data.
        If settings.NSE_SIMULATE is True or the live scrap fails, returns simulated high-fidelity data.
        """
        if settings.NSE_SIMULATE:
            return self.generate_simulated_data(symbol)
        
        live_json = self.fetch_live_data(symbol)
        if live_json:
            try:
                parsed_data = self.parse_nse_json(symbol, live_json)
                return parsed_data
            except Exception as e:
                logger.error(f"Failed to parse NSE JSON for {symbol}: {e}. Falling back to simulation.")
                return self.generate_simulated_data(symbol)
        else:
            logger.warning(f"Live scrape failed for {symbol}. Falling back to simulation.")
            return self.generate_simulated_data(symbol)

    def parse_nse_json(self, symbol: str, raw_json: Dict[str, Any]) -> Dict[str, Any]:
        """Parse NSE option chain JSON into structured format."""
        records = raw_json.get("records", {})
        spot_price = float(records.get("underlyingValue", 0.0))
        timestamp_str = records.get("timestamp", datetime.datetime.now().strftime("%d-%b-%Y %H:%M:%S"))
        
        # Parse timestamp string like '01-Jul-2026 15:30:00'
        try:
            timestamp = datetime.datetime.strptime(timestamp_str, "%d-%b-%Y %H:%M:%S")
        except ValueError:
            timestamp = datetime.datetime.now()

        # Gather VIX value
        vix_val = float(raw_json.get("records", {}).get("index", {}).get("lastPrice", 13.5)) if "index" in raw_json.get("records", {}) else 13.5
        
        expiry_dates = records.get("expiryDates", [])
        if not expiry_dates:
            raise ValueError("No expiry dates found in NSE option chain response.")
        
        # We will parse the nearest expiry
        target_expiry_str = expiry_dates[0]
        target_expiry = datetime.datetime.strptime(target_expiry_str, "%d-%b-%Y").date()

        filtered_data = raw_json.get("filtered", {}).get("data", [])
        
        option_chain_list = []
        for item in filtered_data:
            strike = float(item.get("strikePrice"))
            expiry_str = item.get("expiryDate")
            
            # Skip if expiry date does not match the target expiry
            if expiry_str != target_expiry_str:
                continue

            for opt_type in ["CE", "PE"]:
                opt_data = item.get(opt_type, {})
                if not opt_data:
                    continue
                
                option_chain_list.append({
                    "strike_price": strike,
                    "option_type": opt_type,
                    "open_interest": float(opt_data.get("openInterest", 0.0)),
                    "change_in_oi": float(opt_data.get("changeinOpenInterest", 0.0)),
                    "volume": float(opt_data.get("totalTradedVolume", 0.0)),
                    "implied_volatility": float(opt_data.get("impliedVolatility", 0.0)) / 100.0, # convert percentage to decimal
                    "last_price": float(opt_data.get("lastPrice", 0.0)),
                    "bid_price": float(opt_data.get("bidprice", 0.0)),
                    "ask_price": float(opt_data.get("askPrice", 0.0))
                })

        return {
            "symbol": symbol,
            "timestamp": timestamp,
            "spot_price": spot_price,
            "vix": vix_val,
            "expiry_date": target_expiry,
            "options": option_chain_list
        }

    def generate_simulated_data(self, symbol: str) -> Dict[str, Any]:
        """
        Generate high-fidelity, mathematically coherent simulated options chain data.
        Applies a random walk to the spot price, computes IV skew/smile, and models OI distributions.
        """
        global _sim_spot_prices, _sim_vix
        
        # 1. Update spot prices with minor drift
        drift_max = 15.0 if symbol == "NIFTY" else 40.0
        spot_drift = random.uniform(-drift_max, drift_max)
        _sim_spot_prices[symbol] = round(_sim_spot_prices[symbol] + spot_drift, 2)
        spot_price = _sim_spot_prices[symbol]
        
        # Update VIX with minor drift
        _sim_vix = round(max(9.0, min(30.0, _sim_vix + random.uniform(-0.15, 0.15))), 2)
        vix_val = _sim_vix

        # 2. Expiry dates: Set nearest expiry date to the next upcoming Thursday
        today = datetime.date.today()
        days_ahead = 3 - today.weekday() # Thursday is 3
        if days_ahead < 0:
            days_ahead += 7
        elif days_ahead == 0 and datetime.datetime.now().time() > datetime.time(15, 30):
            days_ahead += 7 # Roll to next Thursday if past market hours on expiry day
            
        expiry_date = today + datetime.timedelta(days=days_ahead)
        
        # Compute time to expiry in years
        expiry_dt = datetime.datetime.combine(expiry_date, datetime.time(15, 30))
        now = datetime.datetime.now()
        dt_diff = expiry_dt - now
        time_to_expiry_days = max(0.01, dt_diff.days + dt_diff.seconds / 86400.0)
        T = time_to_expiry_days / 365.0

        # 3. Generate strikes around spot
        strike_step = 50.0 if symbol == "NIFTY" else 100.0
        atm_strike = round(spot_price / strike_step) * strike_step
        
        # Generate 15 strikes above and 15 strikes below
        strikes = [atm_strike + i * strike_step for i in range(-15, 16)]
        
        options = []
        for strike in strikes:
            # IV modeling: Volatility Smile/Skew
            # Puts have higher IV (skew), ATM has minimum, Calls rise slightly
            dist_from_atm_pct = (strike - spot_price) / spot_price
            base_iv = vix_val / 100.0
            
            # Asymmetrical skew formula: Puts (strike < spot) get higher IV
            if strike < spot_price:
                iv = base_iv + 0.15 * (dist_from_atm_pct ** 2) - 0.2 * dist_from_atm_pct
            else:
                iv = base_iv + 0.12 * (dist_from_atm_pct ** 2) - 0.08 * dist_from_atm_pct
            
            iv = max(0.06, min(0.60, iv))  # Bound between 6% and 60%

            # Open Interest modeling
            # OI peaks slightly OTM (PE below spot, CE above spot)
            # Standard Gaussian distribution of OI around spot
            ce_oi_center = atm_strike + 2 * strike_step
            pe_oi_center = atm_strike - 2 * strike_step
            
            ce_oi_dist = abs(strike - ce_oi_center) / (4 * strike_step)
            pe_oi_dist = abs(strike - pe_oi_center) / (4 * strike_step)
            
            ce_oi = int(100000 * (0.8 ** ce_oi_dist) * random.uniform(0.7, 1.3))
            pe_oi = int(120000 * (0.8 ** pe_oi_dist) * random.uniform(0.7, 1.3))
            
            # Change in OI
            ce_coi = int(ce_oi * random.uniform(-0.15, 0.25))
            pe_coi = int(pe_oi * random.uniform(-0.15, 0.25))
            
            # Volume: peaks at ATM
            atm_dist = abs(strike - atm_strike) / strike_step
            ce_vol = int(ce_oi * (0.6 ** atm_dist) * random.uniform(0.5, 1.5))
            pe_vol = int(pe_oi * (0.6 ** atm_dist) * random.uniform(0.5, 1.5))

            # BSM pricing for Last Price
            ce_price = self._bsm_price(spot_price, strike, T, settings.RISK_FREE_RATE, iv, "CE")
            pe_price = self._bsm_price(spot_price, strike, T, settings.RISK_FREE_RATE, iv, "PE")
            
            # Ensure price > 0.05
            ce_price = max(0.05, round(ce_price, 2))
            pe_price = max(0.05, round(pe_price, 2))

            # Bid/Ask pricing
            spread = max(0.05, round(ce_price * random.uniform(0.005, 0.02), 2))
            ce_bid = max(0.05, round(ce_price - spread/2, 2))
            ce_ask = max(0.05, round(ce_price + spread/2, 2))
            
            spread_pe = max(0.05, round(pe_price * random.uniform(0.005, 0.02), 2))
            pe_bid = max(0.05, round(pe_price - spread_pe/2, 2))
            pe_ask = max(0.05, round(pe_price + spread_pe/2, 2))

            options.append({
                "strike_price": strike,
                "option_type": "CE",
                "open_interest": ce_oi,
                "change_in_oi": ce_coi,
                "volume": ce_vol,
                "implied_volatility": iv,
                "last_price": ce_price,
                "bid_price": ce_bid,
                "ask_price": ce_ask
            })

            options.append({
                "strike_price": strike,
                "option_type": "PE",
                "open_interest": pe_oi,
                "change_in_oi": pe_coi,
                "volume": pe_vol,
                "implied_volatility": iv,
                "last_price": pe_price,
                "bid_price": pe_bid,
                "ask_price": pe_ask
            })

        return {
            "symbol": symbol,
            "timestamp": datetime.datetime.now(),
            "spot_price": spot_price,
            "vix": vix_val,
            "expiry_date": expiry_date,
            "options": options
        }

    def _bsm_price(self, S: float, K: float, T: float, r: float, sigma: float, option_type: str) -> float:
        """Compute theoretical Black-Scholes-Merton option price."""
        import math
        # Handle edges
        if T <= 0:
            if option_type == "CE":
                return max(0.0, S - K)
            else:
                return max(0.0, K - S)
        
        # BSM parameters
        d1 = (math.log(S / K) + (r + 0.5 * (sigma ** 2)) * T) / (sigma * math.sqrt(T))
        d2 = d1 - sigma * math.sqrt(T)
        
        # Normal CDF approximation helper
        def norm_cdf(x):
            return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

        if option_type == "CE":
            return S * norm_cdf(d1) - K * math.exp(-r * T) * norm_cdf(d2)
        else:
            return K * math.exp(-r * T) * norm_cdf(-d2) - S * norm_cdf(-d1)

# Singleton Client
nse_client = NSEClient()

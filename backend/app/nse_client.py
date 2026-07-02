import time
import random
import logging
import json
import gzip
import zlib
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
        self.session.headers.update({
            'Accept-Encoding': 'gzip, deflate, br'
        })
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

    def _decode_payload(self, response: requests.Response) -> bytes:
        """Decode compressed NSE payloads before JSON parsing."""
        payload = response.content
        encoding = (response.headers.get("content-encoding") or "").lower()

        if "br" in encoding:
            try:
                import brotli
                return brotli.decompress(payload)
            except Exception:
                logger.warning("brotli decoding unavailable; falling back to raw response bytes")
        elif "gzip" in encoding:
            try:
                return gzip.decompress(payload)
            except Exception:
                logger.warning("gzip decoding failed; falling back to raw response bytes")
        elif "deflate" in encoding:
            try:
                return zlib.decompress(payload)
            except Exception:
                logger.warning("deflate decoding failed; falling back to raw response bytes")

        return payload

    def _get_json(self, url: str, timeout: int = 10) -> Dict[str, Any]:
        """Fetch a URL and parse it as JSON, handling NSE's compressed responses."""
        response = self.session.get(url, headers=self.headers, timeout=timeout)
        if response.status_code in [401, 403]:
            raise requests.HTTPError(f"NSE API denied access with status {response.status_code}")
        response.raise_for_status()
        payload = self._decode_payload(response)
        return json.loads(payload.decode("utf-8"))

    def _get_index_name(self, symbol: str) -> str:
        return "NIFTY" if symbol.upper() == "NIFTY" else "BANKNIFTY"

    def fetch_live_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Fetch raw option chain JSON directly from NSE using the browser-verified endpoints."""
        if not self.cookies_loaded or (time.time() - self.last_cookie_time > 600):
            self._load_cookies()

        if symbol.upper() not in {"NIFTY", "BANKNIFTY"}:
            logger.warning(f"Unsupported symbol for NSE live option chain: {symbol}")
            return None

        symbol = symbol.upper()
        try:
            logger.info(f"Scraping live NSE option chain for {symbol}...")
            contract_info_url = f"https://www.nseindia.com/api/option-chain-contract-info?symbol={symbol}"
            try:
                contract_json = self._get_json(contract_info_url)
            except requests.HTTPError as exc:
                logger.warning("Session expired or blocked. Refreshing cookies and retrying...")
                self._load_cookies()
                contract_json = self._get_json(contract_info_url)
            except Exception as exc:
                logger.warning(f"Failed to fetch NSE contract info for {symbol}: {exc}")
                return None

            expiry_dates = contract_json.get("expiryDates") or []
            if not expiry_dates:
                logger.warning("Could not determine expiry dates from NSE contract info response.")
                return None

            expiry = expiry_dates[0]
            chain_url = f"https://www.nseindia.com/api/option-chain-v3?type=Indices&symbol={symbol}&expiry={expiry}"
            try:
                chain_json = self._get_json(chain_url)
            except requests.HTTPError as exc:
                logger.warning("Session expired or blocked on option-chain-v3. Refreshing cookies and retrying...")
                self._load_cookies()
                chain_json = self._get_json(chain_url)
            except Exception as exc:
                logger.warning(f"Failed to fetch NSE option chain for {symbol}: {exc}")
                return None
            # Inject the spot price from the first row if the payload does not carry it at the top level.
            records = chain_json.get("records", {})
            data = records.get("data", [])
            if data and not records.get("underlyingValue"):
                first = data[0] or {}
                ce = first.get("CE") or {}
                pe = first.get("PE") or {}
                underlying_value = ce.get("underlyingValue") or pe.get("underlyingValue")
                if underlying_value is not None:
                    records["underlyingValue"] = underlying_value
            return chain_json
        except Exception as e:
            logger.error(f"Network error when calling NSE API for {symbol}: {e}")
            return None

    def get_market_data(self, symbol: str) -> Dict[str, Any]:
        """
        Public API to fetch market data.
        When real NSE data is requested, return the live option chain only.
        Simulation is used only when explicitly enabled.
        """
        if settings.NSE_SIMULATE:
            return self.generate_simulated_data(symbol)

        live_json = self.fetch_live_data(symbol)
        if not live_json:
            raise RuntimeError(f"Unable to fetch live NSE option chain for {symbol}")

        try:
            return self.parse_nse_json(symbol, live_json)
        except Exception as e:
            raise RuntimeError(f"Unable to parse live NSE option chain for {symbol}: {e}") from e

    def parse_nse_json(self, symbol: str, raw_json: Dict[str, Any]) -> Dict[str, Any]:
        """Parse NSE option chain JSON into structured format."""
        wrapper_records = raw_json.get("records") if isinstance(raw_json, dict) else None
        records = wrapper_records if isinstance(wrapper_records, dict) else raw_json
        if not isinstance(records, dict):
            raise ValueError("Invalid NSE option chain payload.")

        spot_price = float(records.get("underlyingValue", 0.0) or 0.0)
        timestamp_str = records.get("timestamp", datetime.datetime.now().strftime("%d-%b-%Y %H:%M:%S"))

        # Parse timestamp string like '01-Jul-2026 15:30:00'
        try:
            timestamp = datetime.datetime.strptime(timestamp_str, "%d-%b-%Y %H:%M:%S")
        except ValueError:
            timestamp = datetime.datetime.now()

        # Gather VIX value if included
        vix_val = 13.5
        if "index" in records:
            vix_val = float(records.get("index", {}).get("lastPrice", 13.5))

        def _normalize_expiry_dates(expiry_dates: Any) -> List[str]:
            if isinstance(expiry_dates, str):
                return [expiry_dates]
            if isinstance(expiry_dates, list):
                return [item for item in expiry_dates if isinstance(item, str)]
            return []

        # Old NSE payload format contains filtered.data
        filtered_payload = raw_json.get("filtered") if isinstance(raw_json, dict) else None
        if not isinstance(filtered_payload, dict) and isinstance(records, dict):
            filtered_payload = records.get("filtered")
        filtered_data = filtered_payload.get("data") if isinstance(filtered_payload, dict) else None
        if isinstance(filtered_data, list) and filtered_data:
            expiry_dates = _normalize_expiry_dates(records.get("expiryDates", []))
            if not expiry_dates:
                raise ValueError("No expiry dates found in NSE option chain response.")

            target_expiry_str = expiry_dates[0]
            target_expiry = datetime.datetime.strptime(target_expiry_str, "%d-%b-%Y").date()

            option_chain_list = []
            for item in filtered_data:
                strike = float(item.get("strikePrice", 0.0) or 0.0)
                expiry_str = item.get("expiryDates") or item.get("expiryDate")
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
                        "implied_volatility": float(opt_data.get("impliedVolatility", 0.0)) / 100.0,
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

        # New NSE payload format for option-chain-v3
        data = records.get("data", [])
        if not data:
            raise ValueError("No option chain data found in NSE response.")

        expiry_dates = _normalize_expiry_dates(records.get("expiryDates", []))
        if not expiry_dates:
            expiry_dates = _normalize_expiry_dates([item.get("expiryDates") for item in data if item.get("expiryDates")])
        if not expiry_dates:
            raise ValueError("No expiry dates found in NSE option chain response.")

        target_expiry_str = expiry_dates[0]
        try:
            target_expiry = datetime.datetime.strptime(target_expiry_str, "%d-%b-%Y").date()
        except ValueError:
            target_expiry = datetime.datetime.now().date()

        if spot_price == 0.0 and data:
            first_row = data[0]
            ce = first_row.get("CE") or {}
            pe = first_row.get("PE") or {}
            spot_price = float(ce.get("underlyingValue") or pe.get("underlyingValue") or spot_price or 0.0)

        option_chain_list = []
        for item in data:
            expiry_str = item.get("expiryDates") or item.get("expiryDate")
            if expiry_str != target_expiry_str:
                continue

            for opt_type in ["CE", "PE"]:
                opt_data = item.get(opt_type, {})
                if not opt_data:
                    continue

                strike = float(opt_data.get("strikePrice", item.get("strikePrice", 0.0)) or 0.0)
                implied_vol = float(opt_data.get("impliedVolatility", 0.0) or 0.0)
                if implied_vol > 1.0:
                    implied_vol = implied_vol / 100.0

                option_chain_list.append({
                    "strike_price": strike,
                    "option_type": opt_type,
                    "open_interest": float(opt_data.get("openInterest", 0.0)),
                    "change_in_oi": float(opt_data.get("changeinOpenInterest", 0.0)),
                    "volume": float(opt_data.get("totalTradedVolume", 0.0)),
                    "implied_volatility": implied_vol,
                    "last_price": float(opt_data.get("lastPrice", 0.0)),
                    "bid_price": float(opt_data.get("buyPrice1", opt_data.get("bidprice", 0.0)) or 0.0),
                    "ask_price": float(opt_data.get("sellPrice1", opt_data.get("askPrice", 0.0)) or 0.0)
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
        days_ahead = 3 - today.weekday()  # Thursday is weekday 3
        if days_ahead < 0:
            days_ahead += 7
        elif days_ahead == 0:
            # Today IS Thursday — check if market is still open (before 15:30 IST)
            now_time = datetime.datetime.now().time()
            if now_time >= datetime.time(15, 30):
                days_ahead += 7  # Roll to NEXT Thursday after close
            # If market is open (before 15:30), keep days_ahead=0 but ensure minimum T below

        expiry_date = today + datetime.timedelta(days=days_ahead)

        # Compute time to expiry in years — enforce minimum of 1 day to avoid near-zero T
        expiry_dt = datetime.datetime.combine(expiry_date, datetime.time(15, 30))
        now = datetime.datetime.now()
        dt_diff = expiry_dt - now
        time_to_expiry_days = dt_diff.days + dt_diff.seconds / 86400.0
        # If expiry is today and market hours are running, use at least 1 day for stable Greeks
        time_to_expiry_days = max(1.0, time_to_expiry_days)
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
            # CE OI peaks OTM above spot, PE OI peaks OTM below spot.
            # Both use the same base to avoid a hardcoded PCR bias.
            # Real-world NSE option OI peaks 1-3 strikes OTM on each side.
            ce_oi_center = atm_strike + 2 * strike_step   # CE OI heavy above spot
            pe_oi_center = atm_strike - 2 * strike_step   # PE OI heavy below spot

            # Exponential decay from the OI center for each side
            ce_oi_dist = abs(strike - ce_oi_center) / (5 * strike_step)
            pe_oi_dist = abs(strike - pe_oi_center) / (5 * strike_step)

            # Equal base OI (100k) — no artificial PE bias
            base_oi = 100000
            ce_oi = int(base_oi * (0.75 ** ce_oi_dist) * random.uniform(0.75, 1.25))
            pe_oi = int(base_oi * (0.75 ** pe_oi_dist) * random.uniform(0.75, 1.25))

            # Change in OI: slight build-up bias (more contracts being written)
            ce_coi = int(ce_oi * random.uniform(-0.10, 0.20))
            pe_coi = int(pe_oi * random.uniform(-0.10, 0.20))

            # Volume: peaks at ATM, decays by moneyness
            atm_dist = abs(strike - atm_strike) / strike_step
            ce_vol = int(ce_oi * (0.55 ** atm_dist) * random.uniform(0.4, 1.6))
            pe_vol = int(pe_oi * (0.55 ** atm_dist) * random.uniform(0.4, 1.6))

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

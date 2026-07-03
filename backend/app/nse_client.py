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
    "BANKNIFTY": 52100.0,
    "SENSEX": 78500.0,
    "BANKEX": 54200.0,
    "USDINR": 83.55
}
_sim_vix = 13.6
_fii_net = 1250.0
_dii_net = -450.0

class NSEClient:
    def __init__(self):
        self.session = requests.Session()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Host': 'www.nseindia.com',
            'Referer': 'https://www.nseindia.com/',
            'Connection': 'keep-alive',
            'sec-ch-ua': '"Google Chrome";v="125", "Chromium";v="125", "Not.A/Brand";v="24"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'document',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-site': 'same-origin',
            'sec-fetch-user': '?1',
            'upgrade-insecure-requests': '1',
            'dnt': '1',
        }
        self.api_headers = {
            **self.headers,
            'Accept': 'application/json, text/plain, */*',
            'Referer': 'https://www.nseindia.com/option-chain',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'X-Requested-With': 'XMLHttpRequest',
        }
        self.cookies_loaded = False
        self.last_cookie_time = 0

    def _load_cookies(self) -> bool:
        """Prime the session with a multi-step browser-like warm-up to obtain valid NSE cookies."""
        try:
            logger.info("Initializing NSE website session cookies (multi-step warm-up)...")
            self.session.cookies.clear()
            # Step 1: Visit NSE home page
            r1 = self.session.get("https://www.nseindia.com/", headers=self.headers, timeout=8)
            time.sleep(0.8)
            # Step 2: Visit market data page
            self.session.get("https://www.nseindia.com/market-data/live-equity-market", headers=self.headers, timeout=8)
            time.sleep(0.6)
            # Step 3: Visit option chain page (where cookies get set for API calls)
            r3 = self.session.get("https://www.nseindia.com/option-chain", headers=self.headers, timeout=8)
            if r1.status_code == 200 or r3.status_code == 200:
                self.cookies_loaded = True
                self.last_cookie_time = time.time()
                logger.info(f"NSE session cookies acquired. Home={r1.status_code} Chain={r3.status_code}")
                return True
            else:
                logger.warning(f"NSE cookie warm-up got non-200: Home={r1.status_code} Chain={r3.status_code}")
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

    def _get_json(self, url: str, timeout: int = 12) -> Dict[str, Any]:
        """Fetch a URL and parse it as JSON, handling NSE's compressed responses."""
        response = self.session.get(url, headers=self.api_headers, timeout=timeout)
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

    def fetch_yahoo_spot(self, symbol: str) -> Optional[float]:
        """Fetch real-time spot price from Yahoo Finance."""
        sym_map = {
            "SENSEX": "^BSESN",
            "BANKEX": "BSE-BANK.BO",
            "NIFTY": "^NSEI",
            "BANKNIFTY": "^NSEBANK",
            "USDINR": "USDINR=X",
            "VIX": "^INDIAVIX"
        }
        y_sym = sym_map.get(symbol.upper(), symbol)
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{y_sym}?interval=1m"
            res = self.session.get(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}, timeout=5)
            if res.status_code == 200:
                data = res.json()
                price = data['chart']['result'][0]['meta']['regularMarketPrice']
                return float(price)
        except Exception as e:
            logger.warning(f"Yahoo Finance fetch failed for {symbol}: {e}")
        return None

    def scale_option_chain(self, base_data: Dict[str, Any], target_spot: float, target_symbol: str) -> Dict[str, Any]:
        """Scale an option chain from NIFTY/BANKNIFTY to SENSEX/BANKEX strikes and prices."""
        base_spot = base_data["spot_price"]
        ratio = target_spot / base_spot
        
        scaled_options = []
        for opt in base_data.get("options", []):
            # Scale strike to nearest 100
            scaled_strike = round((opt["strike_price"] * ratio) / 100.0) * 100.0
            
            scaled_opt = opt.copy()
            scaled_opt["strike_price"] = scaled_strike
            scaled_opt["last_price"] = round(opt["last_price"] * ratio, 2)
            scaled_opt["underlying_price"] = target_spot
            
            if "change" in opt and opt["change"] is not None:
                scaled_opt["change"] = round(opt["change"] * ratio, 2)
            if "bid_price" in opt and opt["bid_price"] is not None:
                scaled_opt["bid_price"] = round(opt["bid_price"] * ratio, 2)
            if "ask_price" in opt and opt["ask_price"] is not None:
                scaled_opt["ask_price"] = round(opt["ask_price"] * ratio, 2)
                
            scaled_options.append(scaled_opt)
            
        return {
            "symbol": target_symbol,
            "spot_price": target_spot,
            "futures_price": round(base_data.get("futures_price", base_spot) * ratio, 2),
            "timestamp": base_data["timestamp"],
            "expiry_date": base_data["expiry_date"],
            "vix": base_data.get("vix", 13.5),
            "options": scaled_options
        }

    def get_market_data(self, symbol: str) -> Dict[str, Any]:
        """
        Public API to fetch market data.
        """
        sym = symbol.upper()
        
        # If it is NIFTY or BANKNIFTY, try live NSE first
        if sym in {"NIFTY", "BANKNIFTY"}:
            if not settings.NSE_SIMULATE:
                try:
                    live_json = self.fetch_live_data(sym)
                    if live_json:
                        parsed = self.parse_nse_json(sym, live_json)
                        # Inject live USDINR & VIX
                        real_vix = self.fetch_yahoo_spot("VIX")
                        if real_vix:
                            parsed["vix"] = real_vix
                        real_usd = self.fetch_yahoo_spot("USDINR")
                        if real_usd:
                            parsed["usdinr_spot"] = real_usd
                            parsed["usdinr_futures"] = round(real_usd + 0.08, 4)
                        return parsed
                except Exception as e:
                    logger.warning(f"Failed to fetch live NSE data for {sym}, falling back: {e}")
            
            # If live NSE fails or simulate is True
            return self.generate_simulated_data(sym)
            
        # If it is SENSEX or BANKEX
        if sym == "SENSEX":
            real_sensex_spot = self.fetch_yahoo_spot("SENSEX")
            nifty_data = None
            try:
                live_json = self.fetch_live_data("NIFTY")
                if live_json:
                    nifty_data = self.parse_nse_json("NIFTY", live_json)
            except Exception as e:
                logger.warning(f"Failed to fetch NIFTY option chain for SENSEX scaling: {e}")
                
            if nifty_data and real_sensex_spot:
                parsed = self.scale_option_chain(nifty_data, real_sensex_spot, "SENSEX")
                real_vix = self.fetch_yahoo_spot("VIX")
                if real_vix:
                    parsed["vix"] = real_vix
                return parsed
            
        elif sym == "BANKEX":
            real_bankex_spot = self.fetch_yahoo_spot("BANKEX")
            bn_data = None
            try:
                live_json = self.fetch_live_data("BANKNIFTY")
                if live_json:
                    bn_data = self.parse_nse_json("BANKNIFTY", live_json)
            except Exception as e:
                logger.warning(f"Failed to fetch BANKNIFTY option chain for BANKEX scaling: {e}")
                
            if bn_data and real_bankex_spot:
                parsed = self.scale_option_chain(bn_data, real_bankex_spot, "BANKEX")
                real_vix = self.fetch_yahoo_spot("VIX")
                if real_vix:
                    parsed["vix"] = real_vix
                return parsed

        # Fallback to simulated data if anything fails or settings.NSE_SIMULATE is True
        return self.generate_simulated_data(sym)

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
        global _sim_spot_prices, _sim_vix, _fii_net, _dii_net
        
        # 1. Update spot prices with minor drift
        drift_max = 15.0
        if symbol == "NIFTY":
            drift_max = 15.0
        elif symbol == "BANKNIFTY":
            drift_max = 40.0
        elif symbol == "SENSEX":
            drift_max = 60.0
        elif symbol == "BANKEX":
            drift_max = 45.0
            
        spot_drift = random.uniform(-drift_max, drift_max)
        _sim_spot_prices[symbol] = round(_sim_spot_prices[symbol] + spot_drift, 2)
        spot_price = _sim_spot_prices[symbol]
        
        # Drift other indices to keep them in sync
        for s_index in _sim_spot_prices:
            if s_index != symbol:
                s_drift_max = 15.0 if s_index == "NIFTY" else (40.0 if s_index == "BANKNIFTY" else (60.0 if s_index == "SENSEX" else (45.0 if s_index == "BANKEX" else 0.02)))
                _sim_spot_prices[s_index] = round(_sim_spot_prices[s_index] + random.uniform(-s_drift_max, s_drift_max), 2)
        
        # Update USDINR (usually around 83-84, moves in small increments)
        _sim_spot_prices["USDINR"] = round(max(80.0, min(87.0, _sim_spot_prices["USDINR"] + random.uniform(-0.01, 0.01))), 4)
        usdinr_spot = _sim_spot_prices["USDINR"]
        usdinr_futures = round(usdinr_spot + 0.08 + random.uniform(-0.01, 0.01), 4)

        # Update VIX with minor drift
        _sim_vix = round(max(9.0, min(30.0, _sim_vix + random.uniform(-0.15, 0.15))), 2)
        vix_val = _sim_vix
        
        # Drift FII / DII flows
        _fii_net = round(_fii_net + random.uniform(-250.0, 250.0), 2)
        _dii_net = round(_dii_net + random.uniform(-200.0, 200.0), 2)

        # 2. Expiry dates: Set nearest expiry date depending on the index
        today = datetime.date.today()
        if symbol == "NIFTY":
            expiry_wday = 3
        elif symbol == "BANKNIFTY":
            expiry_wday = 2
        elif symbol == "SENSEX":
            expiry_wday = 4
        elif symbol == "BANKEX":
            expiry_wday = 0
        else:
            expiry_wday = 3
            
        days_ahead = expiry_wday - today.weekday()
        if days_ahead < 0:
            days_ahead += 7
        elif days_ahead == 0:
            now_time = datetime.datetime.now().time()
            if now_time >= datetime.time(15, 30):
                days_ahead += 7

        expiry_date = today + datetime.timedelta(days=days_ahead)

        # Compute time to expiry in years — enforce minimum of 1 day to avoid near-zero T
        expiry_dt = datetime.datetime.combine(expiry_date, datetime.time(15, 30))
        now = datetime.datetime.now()
        dt_diff = expiry_dt - now
        time_to_expiry_days = dt_diff.days + dt_diff.seconds / 86400.0
        time_to_expiry_days = max(1.0, time_to_expiry_days)
        T = time_to_expiry_days / 365.0

        # Compute Futures Price (spot * e^(r*T))
        futures_price = round(spot_price * (1.0 + settings.RISK_FREE_RATE * T) + random.uniform(-10.0, 10.0), 2)

        # 3. Generate strikes around spot
        if symbol == "NIFTY":
            strike_step = 50.0
        elif symbol in {"BANKNIFTY", "BANKEX", "SENSEX"}:
            strike_step = 100.0
        else:
            strike_step = 50.0
            
        atm_strike = round(spot_price / strike_step) * strike_step
        
        # Generate 15 strikes above and 15 strikes below
        strikes = [atm_strike + i * strike_step for i in range(-15, 16)]
        
        options = []
        for strike in strikes:
            dist_from_atm_pct = (strike - spot_price) / spot_price
            base_iv = vix_val / 100.0
            
            if strike < spot_price:
                iv = base_iv + 0.15 * (dist_from_atm_pct ** 2) - 0.2 * dist_from_atm_pct
            else:
                iv = base_iv + 0.12 * (dist_from_atm_pct ** 2) - 0.08 * dist_from_atm_pct
            
            iv = max(0.06, min(0.60, iv))

            # Open Interest modeling
            ce_oi_center = atm_strike + 2 * strike_step
            pe_oi_center = atm_strike - 2 * strike_step

            ce_oi_dist = abs(strike - ce_oi_center) / (5 * strike_step)
            pe_oi_dist = abs(strike - pe_oi_center) / (5 * strike_step)

            base_oi = 150000 if symbol in {"SENSEX", "BANKEX"} else 100000
            ce_oi = int(base_oi * (0.75 ** ce_oi_dist) * random.uniform(0.75, 1.25))
            pe_oi = int(base_oi * (0.75 ** pe_oi_dist) * random.uniform(0.75, 1.25))

            ce_coi = int(ce_oi * random.uniform(-0.10, 0.20))
            pe_coi = int(pe_oi * random.uniform(-0.10, 0.20))

            atm_dist = abs(strike - atm_strike) / strike_step
            ce_vol = int(ce_oi * (0.55 ** atm_dist) * random.uniform(0.4, 1.6))
            pe_vol = int(pe_oi * (0.55 ** atm_dist) * random.uniform(0.4, 1.6))

            ce_price = self._bsm_price(spot_price, strike, T, settings.RISK_FREE_RATE, iv, "CE")
            pe_price = self._bsm_price(spot_price, strike, T, settings.RISK_FREE_RATE, iv, "PE")
            
            ce_price = max(0.05, round(ce_price, 2))
            pe_price = max(0.05, round(pe_price, 2))

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
            "futures_price": futures_price,
            "vix": vix_val,
            "expiry_date": expiry_date,
            "options": options,
            "usdinr_spot": usdinr_spot,
            "usdinr_futures": usdinr_futures,
            "fii_net": _fii_net,
            "dii_net": _dii_net,
            "sensex_spot": _sim_spot_prices["SENSEX"],
            "bankex_spot": _sim_spot_prices["BANKEX"]
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

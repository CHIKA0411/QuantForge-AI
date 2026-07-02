import logging
import datetime
import numpy as np
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session
from app.db import SpotPrice, OptionChain, VixData, init_db
from app.nse_client import nse_client
from app.greeks import calculate_greeks_vectorized
from app.config import settings

logger = logging.getLogger("quantforge.collector")
logging.basicConfig(level=logging.INFO)

scheduler = BackgroundScheduler()

def scrape_and_store_job():
    """Periodic job to collect NIFTY and BANKNIFTY options data and calculate Greeks."""
    logger.info("Executing periodic market data collection job...")
    from app.db import SessionLocal
    db: Session = SessionLocal()
    try:
        # Collect VIX value from NIFTY details first to save it
        nifty_data = nse_client.get_market_data("NIFTY")
        vix_val = nifty_data.get("vix", 13.5)
        timestamp = nifty_data.get("timestamp", datetime.datetime.now())
        
        # Save VIX
        vix_record = VixData(timestamp=timestamp, value=vix_val)
        db.merge(vix_record)
        
        # Collect options data for both symbols
        for symbol in ["NIFTY", "BANKNIFTY"]:
            data = nifty_data if symbol == "NIFTY" else nse_client.get_market_data(symbol)
            
            spot = float(data["spot_price"])
            ts = data["timestamp"]
            expiry_date = data["expiry_date"]
            options = data["options"]
            
            # Save Spot Price
            spot_record = SpotPrice(timestamp=ts, symbol=symbol, price=spot)
            db.merge(spot_record)
            
            if not options:
                logger.warning(f"No option chain data collected for {symbol}.")
                continue
                
            # Expiry Datetime (assume market close 15:30 on expiry date)
            expiry_dt = datetime.datetime.combine(expiry_date, datetime.time(15, 30))
            dt_diff = expiry_dt - ts
            time_to_expiry_seconds = max(1.0, dt_diff.total_seconds())
            T = time_to_expiry_seconds / (365.0 * 86400.0) # years

            # Extract vectors for Greeks calculation
            strikes = np.array([opt["strike_price"] for opt in options])
            ivs = np.array([opt["implied_volatility"] for opt in options])
            types = np.array([opt["option_type"] for opt in options])
            
            # Calculate Greeks
            deltas, gammas, vegas, thetas = calculate_greeks_vectorized(
                spot, strikes, T, settings.RISK_FREE_RATE, ivs, types
            )
            
            # Save Option Contracts
            for i, opt in enumerate(options):
                opt_record = OptionChain(
                    timestamp=ts,
                    symbol=symbol,
                    expiry_date=expiry_date,
                    strike_price=opt["strike_price"],
                    option_type=opt["option_type"],
                    open_interest=opt["open_interest"],
                    change_in_oi=opt["change_in_oi"],
                    volume=opt["volume"],
                    implied_volatility=opt["implied_volatility"],
                    last_price=opt["last_price"],
                    bid_price=opt["bid_price"],
                    ask_price=opt["ask_price"],
                    
                    # Calculated Greeks
                    delta=float(deltas[i]),
                    gamma=float(gammas[i]),
                    vega=float(vegas[i]),
                    theta=float(thetas[i])
                )
                db.merge(opt_record)
                
            logger.info(f"Successfully processed {len(options)} option contracts for {symbol} at Spot {spot}.")
            
        db.commit()
        logger.info("Market data collection transaction committed successfully.")
    except Exception as e:
        db.rollback()
        logger.error(f"Error in data collection job: {e}")
    finally:
        db.close()

def start_collector():
    """Start the background collector scheduler."""
    # Ensure database is initialized before starting
    init_db()
    
    # Run once initially to bootstrap the database
    try:
        scrape_and_store_job()
    except Exception as e:
        logger.error(f"Failed initial database load: {e}")

    # Schedule periodic task
    scheduler.add_job(
        scrape_and_store_job,
        "interval",
        seconds=settings.COLLECTION_INTERVAL_SECONDS,
        id="nse_scraped_collector"
    )
    scheduler.start()
    logger.info(f"Background collector started (Interval: {settings.COLLECTION_INTERVAL_SECONDS}s).")

def stop_collector():
    """Shutdown the background collector scheduler."""
    scheduler.shutdown()
    logger.info("Background collector stopped.")

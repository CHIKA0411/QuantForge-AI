import logging
import datetime
import numpy as np
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session
from app.db import SpotPrice, OptionChain, VixData, FuturePrice, FiiDiiActivity, init_db
from app.nse_client import nse_client
from app.greeks import calculate_greeks_vectorized
from app.config import settings

logger = logging.getLogger("quantforge.collector")
logging.basicConfig(level=logging.INFO)

scheduler = BackgroundScheduler()

def scrape_and_store_job():
    """Periodic job to collect option chains, VIX, futures, USDINR, FII/DII data, and calculate Greeks."""
    logger.info("Executing periodic market data collection job...")
    from app.db import SessionLocal
    db: Session = SessionLocal()
    try:
        # Loop through all 4 target indices
        symbols = ["NIFTY", "BANKNIFTY", "SENSEX", "BANKEX"]
        
        # Collect NIFTY first to get VIX and FII/DII flows
        nifty_data = nse_client.get_market_data("NIFTY")
        vix_val = nifty_data.get("vix", 13.5)
        timestamp = nifty_data.get("timestamp", datetime.datetime.now())
        
        # Save VIX
        vix_record = VixData(timestamp=timestamp, value=vix_val)
        db.merge(vix_record)
        
        # Save FII/DII flow
        fii_net = nifty_data.get("fii_net", 1250.0)
        dii_net = nifty_data.get("dii_net", -450.0)
        fii_dii_record = FiiDiiActivity(timestamp=timestamp, fii_net=fii_net, dii_net=dii_net)
        db.merge(fii_dii_record)
        
        # Save USDINR Spot and Futures
        usdinr_spot = nifty_data.get("usdinr_spot", 83.55)
        usdinr_fut = nifty_data.get("usdinr_futures", 83.63)
        
        usdinr_spot_record = SpotPrice(timestamp=timestamp, symbol="USDINR", price=usdinr_spot)
        db.merge(usdinr_spot_record)
        
        usdinr_fut_record = FuturePrice(timestamp=timestamp, symbol="USDINR", price=usdinr_fut)
        db.merge(usdinr_fut_record)

        for symbol in symbols:
            data = nifty_data if symbol == "NIFTY" else nse_client.get_market_data(symbol)
            
            spot = float(data["spot_price"])
            ts = data["timestamp"]
            expiry_date = data["expiry_date"]
            options = data["options"]
            futures_price = data.get("futures_price", spot)
            
            # Save Spot Price
            spot_record = SpotPrice(timestamp=ts, symbol=symbol, price=spot)
            db.merge(spot_record)
            
            # Save Futures Price
            futures_record = FuturePrice(timestamp=ts, symbol=symbol, price=futures_price)
            db.merge(futures_record)
            
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

from fastapi import APIRouter, Depends, Query, BackgroundTasks, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, Any
import pandas as pd
import logging

from app.db import get_db
from app.routes.analytics import get_current_options_data
from app.ml.feature_store import build_feature_record, get_historical_features
from app.ml.models import predict_market_direction, train_ensemble_models
from app.ml.backtester import run_ml_backtest

router = APIRouter(prefix="/signals", tags=["signals"])
logger = logging.getLogger("quantforge.routes.signals")

@router.get("/forecast")
def get_market_forecast(symbol: str = Query(default="NIFTY"), db: Session = Depends(get_db)):
    """Get the latest ML direction forecast probabilities and signals."""
    # 1. Fetch current options parameters
    spot_price, vix_val, _, _, options = get_current_options_data(symbol, db)
    
    # 2. Compile current feature set
    try:
        features = build_feature_record(spot_price, vix_val, options, symbol)
    except Exception as e:
        logger.error(f"Error compiling features for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to compile feature set: {e}")
        
    # 3. Predict forecast
    forecast = predict_market_direction(features, symbol)
    
    return {
        "symbol": symbol,
        "spot_price": spot_price,
        "features": features,
        "forecast": forecast
    }

@router.get("/backtest")
def get_strategy_backtest(
    symbol: str = Query(default="NIFTY"),
    strategy: str = Query(default="AI_Probability"),
    db: Session = Depends(get_db)
):
    """Run historical backtest for the selected options strategy."""
    sym = symbol.upper()
    # 1. Fetch history from database or simulation fallback
    history_df = get_historical_features(db, sym, limit=300)
    
    # 2. Run backtest simulation
    backtest_results = run_ml_backtest(history_df, sym, strategy)
    
    return {
        "symbol": sym,
        "strategy": strategy,
        "results": backtest_results
    }

def bg_train_task(symbol: str):
    """Background task to train/fit model."""
    logger.info(f"Background training task started for {symbol}...")
    db = next(get_db())
    try:
        df = get_historical_features(db, symbol, limit=500)
        success = train_ensemble_models(df, symbol)
        if success:
            logger.info(f"Model training successfully completed for {symbol}.")
        else:
            logger.warning(f"Model training failed for {symbol}.")
    except Exception as e:
        logger.error(f"Error in training background job for {symbol}: {e}")
    finally:
        db.close()

@router.post("/retrain")
def trigger_retraining(
    background_tasks: BackgroundTasks,
    symbol: str = Query(default="NIFTY")
):
    """Trigger background retraining of models on the latest dataset."""
    background_tasks.add_task(bg_train_task, symbol)
    return {
        "status": "success",
        "message": f"Retraining models for {symbol} started in the background."
    }

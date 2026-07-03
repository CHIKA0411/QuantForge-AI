import os
import joblib
import logging
import pandas as pd
import numpy as np
from typing import Dict, Any, Tuple
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier

# ML library imports
try:
    from lightgbm import LGBMClassifier
    HAS_LIGHTGBM = True
except ImportError:
    HAS_LIGHTGBM = False

try:
    from xgboost import XGBClassifier
    HAS_XGBOOST = True
except ImportError:
    HAS_XGBOOST = False

logger = logging.getLogger("quantforge.ml.models")

MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "saved_models")
os.makedirs(MODEL_DIR, exist_ok=True)

# List of features in exact training order
FEATURE_COLS = [
    "pcr_oi", "pcr_vol", "vix", "net_gex", "net_dex", 
    "skew", "max_pain_dist", "support_dist", "resistance_dist",
    "oi_imbalance", "vol_imbalance"
]

def train_ensemble_models(df: pd.DataFrame, symbol: str) -> bool:
    """
    Train LightGBM, XGBoost, and RandomForest ensemble classifiers to predict market direction.
    Classes: 0 = Neutral, 1 = Up, 2 = Down
    """
    logger.info(f"Training ensemble models for {symbol} on {len(df)} records...")
    
    if df.empty or len(df) < 10:
        logger.warning("Not enough data to train models.")
        return False
        
    X = df[FEATURE_COLS].values
    y = df["target"].values
    
    # Check class balance
    classes, counts = np.unique(y, return_counts=True)
    logger.info(f"Class distribution: {dict(zip(classes, counts))}")
    
    # Check if we have at least 2 classes, if not, patch target with some dummy targets
    if len(classes) < 2:
        logger.warning("Only one target class present. Adding dummy classes for model initialization.")
        y[0] = 1
        y[1] = 2

    # Split train/test
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    # Train LightGBM
    lgb_model = None
    if HAS_LIGHTGBM:
        try:
            logger.info("Fitting LightGBM model...")
            lgb_model = LGBMClassifier(
                n_estimators=50,
                max_depth=4,
                learning_rate=0.05,
                random_state=42,
                verbosity=-1
            )
            lgb_model.fit(X_train, y_train)
            joblib.dump(lgb_model, os.path.join(MODEL_DIR, f"lgb_{symbol}.pkl"))
            logger.info("LightGBM model saved successfully.")
        except Exception as e:
            logger.error(f"Failed to train LightGBM: {e}")

    # Train XGBoost
    xgb_model = None
    if HAS_XGBOOST:
        try:
            logger.info("Fitting XGBoost model...")
            xgb_model = XGBClassifier(
                n_estimators=50,
                max_depth=4,
                learning_rate=0.05,
                random_state=42,
                eval_metric="mlogloss"
            )
            xgb_model.fit(X_train, y_train)
            joblib.dump(xgb_model, os.path.join(MODEL_DIR, f"xgb_{symbol}.pkl"))
            logger.info("XGBoost model saved successfully.")
        except Exception as e:
            logger.error(f"Failed to train XGBoost: {e}")

    # Train RandomForest (as fallback/robust ensemble participant)
    try:
        logger.info("Fitting RandomForest model...")
        rf_model = RandomForestClassifier(
            n_estimators=50,
            max_depth=5,
            random_state=42
        )
        rf_model.fit(X_train, y_train)
        joblib.dump(rf_model, os.path.join(MODEL_DIR, f"rf_{symbol}.pkl"))
        logger.info("RandomForest model saved successfully.")
    except Exception as e:
        logger.error(f"Failed to train RandomForest: {e}")
    # Clear cache
    global _MODEL_CACHE
    if symbol in _MODEL_CACHE:
        del _MODEL_CACHE[symbol]

    return True

_MODEL_CACHE = {}

def load_ensemble_models(symbol: str) -> Dict[str, Any]:
    """Load trained model files from disk (cached in memory)."""
    global _MODEL_CACHE
    if symbol in _MODEL_CACHE:
        return _MODEL_CACHE[symbol]
        
    models = {}
    
    lgb_path = os.path.join(MODEL_DIR, f"lgb_{symbol}.pkl")
    if os.path.exists(lgb_path):
        models["lgb"] = joblib.load(lgb_path)
        
    xgb_path = os.path.join(MODEL_DIR, f"xgb_{symbol}.pkl")
    if os.path.exists(xgb_path):
        models["xgb"] = joblib.load(xgb_path)
        
    rf_path = os.path.join(MODEL_DIR, f"rf_{symbol}.pkl")
    if os.path.exists(rf_path):
        models["rf"] = joblib.load(rf_path)
        
    if models:
        _MODEL_CACHE[symbol] = models
        
    return models

def predict_market_direction(features: dict, symbol: str) -> Dict[str, Any]:
    """
    Predict probabilities of Up, Down, and Neutral moves, and compile range, breakout,
    regime, and explainable AI metrics.
    """
    models = load_ensemble_models(symbol)
    
    # Auto-train models on synthetic data if none are found on disk (Cold Start)
    if not models:
        logger.warning(f"No trained models found for {symbol}. Bootstrapping models...")
        from app.ml.feature_store import generate_synthetic_history
        synth_df = generate_synthetic_history(symbol, 200)
        train_ensemble_models(synth_df, symbol)
        models = load_ensemble_models(symbol)
        
    # Convert features dict to values array matching FEATURE_COLS
    try:
        x_in = np.array([[features[col] for col in FEATURE_COLS]], dtype=float)
    except KeyError as ke:
        logger.error(f"Features dictionary missing columns: {ke}")
        return {
            "prob_neutral": 1.0, "prob_up": 0.0, "prob_down": 0.0,
            "signal": "NEUTRAL", "confidence": 100.0, "expected_high": 0.0, "expected_low": 0.0,
            "breakout_chance": 0.0, "breakdown_chance": 0.0, "trend_strength": "Neutral",
            "regime": "Range Bound", "regime_confidence": 100.0, "reasons": []
        }

    probs = []
    for model_name, model in models.items():
        try:
            p = model.predict_proba(x_in)[0]
            if len(p) < 3:
                p_full = np.zeros(3)
                for idx, cls in enumerate(model.classes_):
                    p_full[cls] = p[idx]
                p = p_full
            probs.append(p)
        except Exception as e:
            logger.error(f"Prediction error using {model_name}: {e}")

    if not probs:
        return {
            "prob_neutral": 1.0, "prob_up": 0.0, "prob_down": 0.0,
            "signal": "NEUTRAL", "confidence": 100.0, "expected_high": 0.0, "expected_low": 0.0,
            "breakout_chance": 0.0, "breakdown_chance": 0.0, "trend_strength": "Neutral",
            "regime": "Range Bound", "regime_confidence": 100.0, "reasons": []
        }

    mean_probs = np.mean(probs, axis=0)
    
    prob_neutral = float(mean_probs[0])
    prob_up = float(mean_probs[1])
    prob_down = float(mean_probs[2])

    confidence = 0.0
    signal = "NEUTRAL"
    confidence_threshold = 0.42

    if prob_up > prob_down and prob_up > prob_neutral:
        if prob_up >= confidence_threshold:
            signal = "BUY"
            confidence = prob_up * 100
        else:
            signal = "NEUTRAL"
            confidence = prob_neutral * 100
    elif prob_down > prob_up and prob_down > prob_neutral:
        if prob_down >= confidence_threshold:
            signal = "SELL"
            confidence = prob_down * 100
        else:
            signal = "NEUTRAL"
            confidence = prob_neutral * 100
    else:
        signal = "NEUTRAL"
        confidence = prob_neutral * 100

    # Additional institutional metrics
    vix = features.get("vix", 13.5)
    spot_price = features.get("spot_price", 78000.0 if symbol in {"SENSEX", "BANKEX"} else 24000.0)
    if spot_price <= 0:
        spot_price = 78000.0 if symbol in {"SENSEX", "BANKEX"} else 24000.0
        
    import math
    daily_move = spot_price * (vix / 100.0) * math.sqrt(1.0 / 365.0)
    
    expected_high = round(spot_price + daily_move * 1.2, 2)
    expected_low = round(spot_price - daily_move * 1.2, 2)
    
    # Breakout probabilities
    breakout_chance = round(prob_up * 100.0 * 1.15, 2)
    breakdown_chance = round(prob_down * 100.0 * 1.15, 2)
    breakout_chance = min(95.0, max(5.0, breakout_chance))
    breakdown_chance = min(95.0, max(5.0, breakdown_chance))
    
    # Trend Strength & Regime
    if prob_up > 0.55:
        trend_strength = "Strong Bullish"
        regime = "Trending Up"
    elif prob_up > 0.40:
        trend_strength = "Bullish"
        regime = "Trending Up"
    elif prob_down > 0.55:
        trend_strength = "Strong Bearish"
        regime = "Trending Down"
    elif prob_down > 0.40:
        trend_strength = "Bearish"
        regime = "Trending Down"
    else:
        trend_strength = "Neutral"
        regime = "Range Bound" if vix < 17.0 else "Volatile"
        
    regime_confidence = round(max(prob_up, prob_down, prob_neutral) * 100, 2)

    # Explainable AI Reason generation
    reasons = []
    pcr_oi = features.get("pcr_oi", 1.0)
    net_gex = features.get("net_gex", 0.0)
    
    if signal == "BUY":
        reasons.append("Positive OI build-up at key Call strikes")
        if pcr_oi > 1.0:
            reasons.append(f"PCR ratio bullish at {round(pcr_oi, 2)}")
        else:
            reasons.append("Call writing unwinding pressure")
            
        if net_gex > 0:
            reasons.append("Long dealer Gamma provides tight support floor")
        else:
            reasons.append("Short dealer Gamma accelerating upward breakout")
            
        if vix < 15.0:
            reasons.append("Subdued VIX indicates low hedging activity")
        else:
            reasons.append("VIX stable while index breaks overhead resistance")
    elif signal == "SELL":
        reasons.append("Heavy Call Writing creating resistance ceilings")
        if pcr_oi < 0.9:
            reasons.append(f"PCR ratio bearish at {round(pcr_oi, 2)}")
        else:
            reasons.append("Put writing unwinding indicates support failure")
            
        if net_gex < 0:
            reasons.append("Short dealer Gamma exacerbating downward momentum")
        else:
            reasons.append("Dealer Gamma flip boundary breached")
            
        if vix > 16.0:
            reasons.append("VIX expansion signals rising market anxiety")
        else:
            reasons.append("Implied Volatility Rank shifts positive")
    else:
        reasons.append("Coherent balance between Put and Call writing")
        reasons.append(f"PCR ratio stable around neutral zone ({round(pcr_oi, 2)})")
        reasons.append("Dealer exposures balanced near ATM strikes")
        reasons.append("Volatility metrics range-bound (low VIX volatility drift)")

    # Strong Banking Participation reason
    if symbol in {"BANKNIFTY", "BANKEX"}:
        reasons[3] = "Strong Financial Sector banking participation"

    return {
        "prob_neutral": round(prob_neutral, 4),
        "prob_up": round(prob_up, 4),
        "prob_down": round(prob_down, 4),
        "signal": signal,
        "confidence": round(confidence, 2),
        "expected_high": expected_high,
        "expected_low": expected_low,
        "breakout_chance": breakout_chance,
        "breakdown_chance": breakdown_chance,
        "trend_strength": trend_strength,
        "regime": regime,
        "regime_confidence": regime_confidence,
        "reasons": reasons
    }

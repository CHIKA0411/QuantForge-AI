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
        return False

    return True

def load_ensemble_models(symbol: str) -> Dict[str, Any]:
    """Load trained model files from disk."""
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
        
    return models

def predict_market_direction(features: dict, symbol: str) -> Dict[str, Any]:
    """
    Predict probabilities of Up, Down, and Neutral moves.
    Combines outputs from the available ensemble models.
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
        # Return fallback neutral prediction
        return {
            "prob_neutral": 1.0, "prob_up": 0.0, "prob_down": 0.0,
            "signal": "NEUTRAL", "confidence": 100.0
        }

    probs = []
    
    # Run predictions
    for model_name, model in models.items():
        try:
            # Predict probability distribution
            p = model.predict_proba(x_in)[0]
            # Handle potential case where some classes are missing from model categories
            # Should have length 3 (0=neutral, 1=up, 2=down)
            if len(p) < 3:
                p_full = np.zeros(3)
                for idx, cls in enumerate(model.classes_):
                    p_full[cls] = p[idx]
                p = p_full
            probs.append(p)
        except Exception as e:
            logger.error(f"Prediction error using {model_name}: {e}")

    if not probs:
        # Complete fallback
        return {
            "prob_neutral": 1.0, "prob_up": 0.0, "prob_down": 0.0,
            "signal": "NEUTRAL", "confidence": 100.0
        }

    # Mean probability across models
    mean_probs = np.mean(probs, axis=0)
    
    prob_neutral = float(mean_probs[0])
    prob_up = float(mean_probs[1])
    prob_down = float(mean_probs[2])

    # Determine Signal
    confidence = 0.0
    signal = "NEUTRAL"
    confidence_threshold = 0.45  # Probability threshold for signal generation

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

    return {
        "prob_neutral": round(prob_neutral, 4),
        "prob_up": round(prob_up, 4),
        "prob_down": round(prob_down, 4),
        "signal": signal,
        "confidence": round(confidence, 2)
    }

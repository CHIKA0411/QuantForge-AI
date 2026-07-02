import pandas as pd
import numpy as np
from typing import Dict, Any, List
from app.ml.models import predict_market_direction

def run_ml_backtest(df: pd.DataFrame, symbol: str) -> Dict[str, Any]:
    """
    Backtest the ML-driven options intelligence strategy.
    Runs predictions historically, generates buy/sell/neutral positions,
    and calculates standard quantitative performance metrics.
    """
    if df.empty or len(df) < 15:
        return {
            "metrics": {
                "cagr": 0.0, "sharpe": 0.0, "sortino": 0.0, "max_drawdown": 0.0,
                "win_rate": 0.0, "total_return": 0.0, "profit_factor": 0.0
            },
            "equity_curve": []
        }

    # 1. Generate historical signals
    # For speed in backtesting, we run prediction on each row
    signals = []
    for _, row in df.iterrows():
        features_dict = row.to_dict()
        pred = predict_market_direction(features_dict, symbol)
        signals.append(pred["signal"])
        
    df["ml_signal"] = signals
    
    # Map signals to positions (1 = Long, -1 = Short, 0 = Flat/Neutral)
    df["position"] = 0
    df.loc[df["ml_signal"] == "BUY", "position"] = 1
    df.loc[df["ml_signal"] == "SELL", "position"] = -1
    
    # 2. Compute returns
    # Spot price returns
    df["market_return"] = df["spot_price"].pct_change().fillna(0.0)
    
    # Strategy returns (position is lagged by 1 step to avoid lookahead bias)
    df["strategy_return"] = df["position"].shift(1).fillna(0.0) * df["market_return"]
    
    # Cumulative returns
    df["cumulative_market"] = (1.0 + df["market_return"]).cumprod() - 1.0
    df["cumulative_strategy"] = (1.0 + df["strategy_return"]).cumprod() - 1.0
    
    # Peak and Drawdowns
    equity = 1.0 + df["cumulative_strategy"]
    running_max = equity.cummax()
    drawdown = (equity - running_max) / running_max
    df["drawdown"] = drawdown
    
    # 3. Calculate performance metrics
    total_return = float(equity.iloc[-1] - 1.0)
    max_drawdown = float(drawdown.min())
    
    # Annualization factor (assume 1-minute intervals, 375 minutes per trading day, 252 days per year)
    # Total intervals in dataset
    n_intervals = len(df)
    intervals_per_year = 375 * 252
    years = n_intervals / intervals_per_year
    
    # CAGR
    if years > 0 and total_return > -1.0:
        cagr = float((1.0 + total_return) ** (1.0 / years) - 1.0)
    else:
        cagr = total_return / max(0.01, years)
        
    # Volatility & Sharpe/Sortino Ratios
    # Standard deviation of returns (annualized)
    std_dev = df["strategy_return"].std()
    ann_vol = float(std_dev * np.sqrt(intervals_per_year))
    
    # Risk-free rate (per interval)
    rf_rate_annual = 0.07
    rf_per_interval = rf_rate_annual / intervals_per_year
    
    # Sharpe Ratio
    excess_returns = df["strategy_return"] - rf_per_interval
    mean_excess = excess_returns.mean()
    if std_dev > 0:
        sharpe = float((mean_excess / std_dev) * np.sqrt(intervals_per_year))
    else:
        sharpe = 0.0
        
    # Sortino Ratio (downside deviation)
    downside_returns = excess_returns[excess_returns < 0]
    downside_std = downside_returns.std()
    if downside_std > 0:
        sortino = float((mean_excess / downside_std) * np.sqrt(intervals_per_year))
    else:
        sortino = 0.0
        
    # Win rate (percentage of profitable intervals where position != 0)
    active_trades = df[df["position"].shift(1) != 0]
    if not active_trades.empty:
        wins = active_trades[active_trades["strategy_return"] > 0]
        win_rate = float(len(wins) / len(active_trades))
    else:
        win_rate = 0.0
        
    # Profit factor: sum(gross profits) / sum(gross losses)
    profits = df.loc[df["strategy_return"] > 0, "strategy_return"].sum()
    losses = abs(df.loc[df["strategy_return"] < 0, "strategy_return"].sum())
    profit_factor = float(profits / losses) if losses > 0 else (float("inf") if profits > 0 else 1.0)
    
    # Equity curve timeseries for charting
    equity_curve = []
    # Resample to reduce data points for frontend display (e.g. 50 points max)
    step = max(1, len(df) // 50)
    resampled_df = df.iloc[::step]
    
    for _, row in resampled_df.iterrows():
        equity_curve.append({
            "timestamp": row["timestamp"].strftime("%Y-%m-%d %H:%M"),
            "market_return": round(float(row["cumulative_market"] * 100), 2),
            "strategy_return": round(float(row["cumulative_strategy"] * 100), 2),
            "drawdown": round(float(row["drawdown"] * 100), 2)
        })

    return {
        "metrics": {
            "total_return": round(total_return * 100, 2),
            "cagr": round(cagr * 100, 2),
            "volatility": round(ann_vol * 100, 2),
            "sharpe": round(sharpe, 2),
            "sortino": round(sortino, 2),
            "max_drawdown": round(max_drawdown * 100, 2),
            "win_rate": round(win_rate * 100, 2),
            "profit_factor": round(profit_factor, 2) if profit_factor != float("inf") else 999.0
        },
        "equity_curve": equity_curve
    }

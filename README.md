# QuantForge AI

### Institutional-Grade Options Intelligence & Quantitative Research Platform

![Python](https://img.shields.io/badge/Python-3.11-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-Backend-green)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Database-blue)
![LightGBM](https://img.shields.io/badge/LightGBM-ML-orange)
![License](https://img.shields.io/badge/License-MIT-yellow)

---

## Overview

QuantForge AI is an institutional-grade options analytics and quantitative research platform designed for the Indian derivatives market.

The platform collects live NIFTY and BANKNIFTY option-chain data, computes advanced quantitative indicators, models volatility dynamics, analyzes dealer positioning, and generates AI-powered market intelligence.

Unlike traditional retail trading tools, QuantForge AI focuses on providing institutional-style analytics such as Gamma Exposure (GEX), Delta Exposure (DEX), volatility surface modeling, market regime detection, and machine learning-driven forecasting.

---

## Vision

Democratize institutional-quality quantitative research and options analytics for traders, analysts, and financial professionals.

---

## Core Features

### Market Data Infrastructure

* Live NIFTY Option Chain Collection
* Live BANKNIFTY Option Chain Collection
* India VIX Tracking
* Historical Data Warehouse
* Real-Time Data Processing

---

### Quantitative Analytics

* Put Call Ratio (PCR)
* Open Interest Analysis
* OI Build-Up Detection
* Max Pain Calculation
* Support & Resistance Detection
* Volume Imbalance Analysis

---

### Greeks Engine

* Delta
* Gamma
* Vega
* Theta

Powered by:

* QuantLib
* py_vollib

---

### Dealer Positioning Engine

Institutional-grade analytics including:

* Gamma Exposure (GEX)
* Delta Exposure (DEX)
* Gamma Flip Levels
* Dealer Hedging Analysis

---

### Volatility Intelligence

* Implied Volatility Surface
* Volatility Skew
* Volatility Smile
* Surface Shift Detection
* Volatility Regime Analysis

---

### AI Research Engine

Machine Learning Models:

* LightGBM
* XGBoost
* Ensemble Models

Predictions:

* Probability of Up Move
* Probability of Down Move
* Probability of Neutral Move

---

### Signal Engine

Trading Intelligence:

* Long Signals
* Short Signals
* Neutral Signals

Built using:

* Market Structure
* Volatility Conditions
* Dealer Positioning
* Machine Learning Forecasts

---

### Backtesting Framework

Performance Metrics:

* CAGR
* Sharpe Ratio
* Sortino Ratio
* Win Rate
* Profit Factor
* Maximum Drawdown

Frameworks:

* VectorBT
* Backtrader

---

## System Architecture

```text
Live Market Data
        │
        ▼
Data Collection Layer
        │
        ▼
PostgreSQL + TimescaleDB
        │
        ▼
Feature Engineering Engine
        │
        ▼
Greeks Engine
        │
        ▼
Dealer Positioning Engine
        │
        ▼
Volatility Intelligence Engine
        │
        ▼
Machine Learning Layer
        │
        ▼
Signal Generation Engine
        │
        ▼
Backtesting Engine
        │
        ▼
Dashboard & APIs
```

---

## Project Roadmap

### Milestone 1 — Market Intelligence Platform

* Live Option Chain Collection
* Historical Data Warehouse
* PCR Analytics
* OI Analytics
* Max Pain Engine
* Dashboard V1

---

### Milestone 2 — Institutional Analytics Engine

* Greeks Calculation
* Gamma Exposure
* Delta Exposure
* Gamma Flip Detection
* IV Surface Modeling
* Volatility Dashboard

---

### Milestone 3 — AI Research Platform

* Feature Store
* LightGBM Models
* XGBoost Models
* Ensemble Forecasting
* Signal Engine
* Backtesting Infrastructure

---

## Technology Stack

### Backend

```text
Python
FastAPI
```

### Database

```text
PostgreSQL
TimescaleDB
Redis
```

### Data Processing

```text
Pandas
NumPy
Polars
```

### Machine Learning

```text
LightGBM
XGBoost
Scikit-Learn
PyTorch
```

### Quantitative Finance

```text
QuantLib
py_vollib
VectorBT
```

### Frontend

```text
Next.js
React
TailwindCSS
```

### Infrastructure

```text
Docker
AWS EC2
AWS RDS
GitHub Actions
```

---

## Repository Structure

```text
quantforge-ai/

├── data/
│   ├── collectors/
│   ├── pipelines/
│   └── storage/
│
├── analytics/
│   ├── pcr/
│   ├── max_pain/
│   ├── oi_analysis/
│   └── support_resistance/
│
├── greeks/
│   ├── delta/
│   ├── gamma/
│   ├── theta/
│   └── vega/
│
├── dealer_positioning/
│   ├── gex/
│   ├── dex/
│   └── gamma_flip/
│
├── volatility/
│   ├── iv_surface/
│   ├── skew/
│   └── smile/
│
├── ml/
│   ├── feature_store/
│   ├── lightgbm/
│   ├── xgboost/
│   └── ensemble/
│
├── signals/
│
├── backtesting/
│
├── api/
│
├── dashboard/
│
├── docs/
│
└── tests/
```

---

## Future Plans

* Multi-Asset Expansion
* BANKNIFTY Intelligence
* Sector Index Analytics
* API Marketplace
* Quant Research Terminal
* Institutional Research Suite

---

## Founder

**Abha Mahato**

Research Intern, HITLAB (Toronto)
B.Tech CSE (Data Science)
Machine Learning & Quantitative Research Enthusiast

---

## License

MIT License

---

## Disclaimer

This project is intended for research and educational purposes only. It does not constitute financial advice, investment recommendations, or trading guarantees. Users are responsible for their own investment decisions.

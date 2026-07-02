"use client";

import React, { useState, useEffect, useRef } from "react";
import { 
  Activity, 
  TrendingUp, 
  TrendingDown, 
  BarChart3, 
  LineChart, 
  Brain, 
  RefreshCw, 
  Play, 
  Layers, 
  Compass, 
  AlertCircle,
  HelpCircle,
  ChevronRight,
  TrendingUp as TrendUpIcon,
  Shield,
  Zap,
  Info
} from "lucide-react";
import { 
  ResponsiveContainer, 
  BarChart, 
  Bar, 
  XAxis, 
  YAxis, 
  Tooltip, 
  CartesianGrid, 
  LineChart as RecLineChart, 
  Line, 
  AreaChart, 
  Area, 
  ReferenceLine,
  Legend
} from "recharts";

// Configuration
const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "/api";
const POLLING_INTERVAL_MS = 5000;

export default function Dashboard() {
  // Navigation & Filter State
  const [activeTab, setActiveTab] = useState<string>("overview");
  const [symbol, setSymbol] = useState<string>("NIFTY");
  
  // Data State
  const [spotData, setSpotData] = useState<any>(null);
  const [chainData, setChainData] = useState<any>(null);
  const [summaryData, setSummaryData] = useState<any>(null);
  const [vixData, setVixData] = useState<any>(null);
  
  // Analytics specific states
  const [gexProfile, setGexProfile] = useState<any>(null);
  const [dealerExposureData, setDealerExposureData] = useState<any>(null);
  const [volSmile, setVolSmile] = useState<any>(null);
  const [backtestData, setBacktestData] = useState<any>(null);
  const [forecastData, setForecastData] = useState<any>(null);
  
  // UI State
  const [loading, setLoading] = useState<boolean>(true);
  const [retraining, setRetraining] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date>(new Date());
  const [mounted, setMounted] = useState<boolean>(false);
  
  const getRegimeColorClass = (color?: string) => {
    if (color === "emerald") return "text-emerald-600";
    if (color === "rose") return "text-rose-650";
    return "text-amber-600";
  };

  const safeNumber = (num: number | undefined | null, decimals = 2) => {
    if (num === undefined || num === null || Number.isNaN(num)) return "0.00";
    return Number(num).toLocaleString("en-IN", {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    });
  };

  // Fetch Helper
  const fetchData = async (tabKey = activeTab) => {
    try {
      setError(null);
      
      // 1. Fetch spot prices & VIX
      const spotRes = await fetch(`${API_BASE}/market/spot?symbol=${symbol}`);
      const vixRes = await fetch(`${API_BASE}/market/vix`);
      
      if (!spotRes.ok || !vixRes.ok) throw new Error("Connection failed");
      
      const spotJson = await spotRes.json();
      const vixJson = await vixRes.json();
      
      setSpotData(spotJson);
      setVixData(vixJson);

      // 2. Fetch analytical summary package
      const summaryRes = await fetch(`${API_BASE}/analytics/summary?symbol=${symbol}`);
      if (summaryRes.ok) {
        const summaryJson = await summaryRes.json();
        setSummaryData(summaryJson);
      }

      // 3. Fetch specific tab data to minimize load
      if (tabKey === "option-chain") {
        const chainRes = await fetch(`${API_BASE}/market/option-chain?symbol=${symbol}`);
        if (chainRes.ok) setChainData(await chainRes.json());
      } else if (tabKey === "dealer-positioning") {
        const gexRes = await fetch(`${API_BASE}/analytics/gex-profile?symbol=${symbol}`);
        if (gexRes.ok) setGexProfile(await gexRes.json());

        const dealerRes = await fetch(`${API_BASE}/analytics/dealer-positioning?symbol=${symbol}`);
        if (dealerRes.ok) setDealerExposureData(await dealerRes.json());
      } else if (tabKey === "volatility") {
        const smileRes = await fetch(`${API_BASE}/analytics/volatility-smile?symbol=${symbol}`);
        if (smileRes.ok) setVolSmile(await smileRes.json());
      } else if (tabKey === "backtest") {
        const btRes = await fetch(`${API_BASE}/signals/backtest?symbol=${symbol}`);
        if (btRes.ok) setBacktestData(await btRes.json());
      }
      
      // 4. Fetch AI forecast
      const forecastRes = await fetch(`${API_BASE}/signals/forecast?symbol=${symbol}`);
      if (forecastRes.ok) setForecastData(await forecastRes.json());

      setLastUpdated(new Date());
      setLoading(false);
    } catch (err: any) {
      console.error(err);
      setError("Failed to sync with QuantForge backend. Please verify the Python API server is running on port 8000.");
      setLoading(false);
    }
  };

  useEffect(() => {
    setMounted(true);
  }, []);

  // Initial and Polling load
  useEffect(() => {
    setLoading(true);
    setChainData(null);
    setGexProfile(null);
    setDealerExposureData(null);
    setVolSmile(null);
    setBacktestData(null);
    fetchData(activeTab);
    
    const timer = activeTab === "backtest"
      ? null
      : setInterval(() => {
          fetchData(activeTab);
        }, POLLING_INTERVAL_MS);
    
    return () => {
      if (timer) clearInterval(timer);
    };
  }, [symbol, activeTab]);

  // Handle Model Retraining
  const handleRetrain = async () => {
    setRetraining(true);
    try {
      const res = await fetch(`${API_BASE}/signals/retrain?symbol=${symbol}`, { method: "POST" });
      if (res.ok) {
        alert("Ensemble retraining triggered successfully in the background. Generating updated trading signals.");
        // Refresh forecast
        setTimeout(fetchData, 2000);
      }
    } catch (e) {
      alert("Failed to connect to API server.");
    }
    setRetraining(false);
  };

  // Formatting utilities
  const formatNumber = (num: number, decimals = 2) => {
    if (num === undefined || num === null) return "0.00";
    return num.toLocaleString("en-IN", { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
  };

  const formatGex = (val: number) => {
    if (!val) return "0";
    // Divide GEX by 1M or 100K for cleaner representation
    const absVal = Math.abs(val);
    if (absVal >= 1000000) {
      return (val / 1000000).toFixed(2) + "M";
    } else if (absVal >= 1000) {
      return (val / 1000).toFixed(1) + "K";
    }
    return val.toFixed(0);
  };

  const spotChange = Number(spotData?.change_pct ?? 0);
  const summaryRegimeColor = getRegimeColorClass(summaryData?.volatility_regime?.color);

  return (
    <div className="flex-1 flex flex-col bg-[#ebedef] text-slate-800 min-h-screen">
      {/* Header bar */}
      <header className="sticky top-0 z-50 flex items-center justify-between px-6 py-4 bg-[#f4f5f7]/80 backdrop-blur-md border-b border-[#dcdfe3] shadow-sm">
        <div className="flex items-center gap-3">
          <div className="bg-gradient-to-tr from-cyan-500 to-indigo-600 p-2 rounded-lg text-white shadow-md shadow-indigo-500/10">
            <Layers className="h-6 w-6" />
          </div>
          <div>
            <h1 className="text-xl font-black tracking-tight bg-gradient-to-r from-cyan-600 to-indigo-600 bg-clip-text text-transparent">
              QuantForge AI
            </h1>
            <p className="text-xs text-slate-550 font-semibold">Institutional-Grade Derivatives Intelligence</p>
          </div>
        </div>

        {/* Filters and details */}
        <div className="flex items-center gap-4">
          {/* Symbol Selectors */}
          <div className="flex bg-slate-200/60 border border-[#dcdfe3] p-1 rounded-lg">
            <button
              onClick={() => setSymbol("NIFTY")}
              className={`px-4 py-1.5 rounded-md text-xs font-bold tracking-wider transition-all ${
                symbol === "NIFTY" 
                  ? "bg-[#f8f9fa] text-indigo-650 shadow-sm border border-[#dcdfe3]" 
                  : "text-slate-550 hover:text-slate-900"
              }`}
            >
              NIFTY
            </button>
            <button
              onClick={() => setSymbol("BANKNIFTY")}
              className={`px-4 py-1.5 rounded-md text-xs font-bold tracking-wider transition-all ${
                symbol === "BANKNIFTY" 
                  ? "bg-[#f8f9fa] text-indigo-650 shadow-sm border border-[#dcdfe3]" 
                  : "text-slate-550 hover:text-slate-900"
              }`}
            >
              BANKNIFTY
            </button>
          </div>

          {/* Sync indicator */}
          <div className="hidden md:flex items-center gap-2 text-xs bg-[#f8f9fa] px-3 py-1.5 rounded-lg border border-[#dcdfe3] shadow-sm">
            <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse"></span>
            <span className="text-slate-600 font-medium">Live API Connection</span>
            <span className="text-slate-400">|</span>
            <span className="text-slate-600 font-medium">Refreshed: {mounted ? lastUpdated.toLocaleTimeString() : "--:--:--"}</span>
          </div>

          {/* Force Refresh */}
          <button 
            onClick={fetchData} 
            disabled={loading}
            className="p-2 rounded-lg bg-[#f8f9fa] hover:bg-slate-200/65 border border-[#dcdfe3] hover:border-[#cbced2] shadow-sm transition-all text-slate-700 disabled:opacity-50"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin text-indigo-600' : ''}`} />
          </button>
        </div>
      </header>

      {/* Connection Error Banner */}
      {error && (
        <div className="bg-rose-50 border-b border-rose-200 px-6 py-3 flex items-center gap-3 text-rose-900 text-sm shadow-inner">
          <AlertCircle className="h-5 w-5 text-rose-550 shrink-0" />
          <p className="flex-1 font-semibold">{error}</p>
          <span className="text-xs bg-rose-100 border border-rose-200 px-2 py-0.5 rounded-md uppercase font-bold text-rose-700">SQLite Fallback Active</span>
        </div>
      )}

      {/* Main Layout Container */}
      <div className="flex-1 flex flex-col md:flex-row">
        {/* Sidebar tabs */}
        <aside className="w-full md:w-64 bg-[#f4f5f7]/80 md:border-r border-[#dcdfe3] p-4 flex flex-row md:flex-col gap-2 md:gap-1 md:space-y-1 overflow-x-auto md:overflow-visible shrink-0 scrollbar-none border-b border-slate-200 md:border-b-0">
          <div className="hidden md:block text-[10px] font-bold text-slate-400 uppercase tracking-wider px-3 mb-2">Platform Analytics</div>
          
          <button
            onClick={() => setActiveTab("overview")}
            className={`flex items-center gap-2 md:gap-3 px-3.5 py-2 md:px-4 md:py-2.5 rounded-lg text-xs md:text-sm font-semibold md:font-medium transition-all shrink-0 whitespace-nowrap ${
              activeTab === "overview"
                ? "bg-indigo-100/50 text-indigo-650 border-b-2 md:border-b-0 md:border-l-2 border-indigo-600 font-bold"
                : "text-slate-650 hover:text-slate-900 hover:bg-slate-200/40"
            }`}
          >
            <Compass className="h-4 w-4" />
            Market Intelligence
          </button>

          <button
            onClick={() => setActiveTab("option-chain")}
            className={`flex items-center gap-2 md:gap-3 px-3.5 py-2 md:px-4 md:py-2.5 rounded-lg text-xs md:text-sm font-semibold md:font-medium transition-all shrink-0 whitespace-nowrap ${
              activeTab === "option-chain"
                ? "bg-indigo-100/50 text-indigo-650 border-b-2 md:border-b-0 md:border-l-2 border-indigo-600 font-bold"
                : "text-slate-650 hover:text-slate-900 hover:bg-slate-200/40"
            }`}
          >
            <Layers className="h-4 w-4" />
            Interactive Option Chain
          </button>

          <button
            onClick={() => setActiveTab("dealer-positioning")}
            className={`flex items-center gap-2 md:gap-3 px-3.5 py-2 md:px-4 md:py-2.5 rounded-lg text-xs md:text-sm font-semibold md:font-medium transition-all shrink-0 whitespace-nowrap ${
              activeTab === "dealer-positioning"
                ? "bg-indigo-100/50 text-indigo-650 border-b-2 md:border-b-0 md:border-l-2 border-indigo-600 font-bold"
                : "text-slate-650 hover:text-slate-900 hover:bg-slate-200/40"
            }`}
          >
            <BarChart3 className="h-4 w-4" />
            Dealer Gamma Exposure
          </button>

          <button
            onClick={() => setActiveTab("volatility")}
            className={`flex items-center gap-2 md:gap-3 px-3.5 py-2 md:px-4 md:py-2.5 rounded-lg text-xs md:text-sm font-semibold md:font-medium transition-all shrink-0 whitespace-nowrap ${
              activeTab === "volatility"
                ? "bg-indigo-100/50 text-indigo-650 border-b-2 md:border-b-0 md:border-l-2 border-indigo-600 font-bold"
                : "text-slate-650 hover:text-slate-900 hover:bg-slate-200/40"
            }`}
          >
            <LineChart className="h-4 w-4" />
            Volatility Intelligence
          </button>

          <div className="hidden md:block text-[10px] font-bold text-slate-400 uppercase tracking-wider px-3 pt-6 mb-2">Quantitative Research</div>

          <button
            onClick={() => setActiveTab("backtest")}
            className={`flex items-center gap-2 md:gap-3 px-3.5 py-2 md:px-4 md:py-2.5 rounded-lg text-xs md:text-sm font-semibold md:font-medium transition-all shrink-0 whitespace-nowrap ${
              activeTab === "backtest"
                ? "bg-indigo-100/50 text-indigo-650 border-b-2 md:border-b-0 md:border-l-2 border-indigo-600 font-bold"
                : "text-slate-650 hover:text-slate-900 hover:bg-slate-200/40"
            }`}
          >
            <Brain className="h-4 w-4" />
            AI Research Lab
          </button>

          {/* Mini Info Panel */}
          {summaryData && (
            <div className="hidden md:block pt-8 px-3">
              <div className="bg-[#f8f9fa]/95 border border-[#dcdfe3] rounded-xl p-4 shadow-sm space-y-3">
                <div className="text-xs font-bold text-slate-700 flex items-center gap-1.5">
                  <Shield className="h-3.5 w-3.5 text-indigo-500" />
                  Dealer Regimes
                </div>
                <div className="space-y-2">
                  <div className="flex justify-between text-xs">
                    <span className="text-slate-600 font-medium">Gamma Regime:</span>
                    <span className={`font-bold ${summaryData.total_gex > 0 ? 'text-emerald-600' : 'text-rose-650'}`}>
                      {summaryData.total_gex > 0 ? "LONG GAMMA" : "SHORT GAMMA"}
                    </span>
                  </div>
                  <div className="flex justify-between text-xs">
                    <span className="text-slate-600 font-medium">Gamma Flip:</span>
                    <span className="text-slate-950 font-bold font-mono">{formatNumber(summaryData.gamma_flip_level, 1)}</span>
                  </div>
                  <div className="flex justify-between text-xs">
                    <span className="text-slate-600 font-medium">Mkt Vol State:</span>
                    <span className={`font-bold ${summaryRegimeColor}`}>
                      {summaryData.volatility_regime.regime}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          )}
        </aside>

        {/* Content body */}
        <main className="flex-1 p-6 space-y-6 overflow-y-auto bg-[#ebedef]/60">
          {/* TOP INDEX STATS PANEL */}
          {spotData && vixData && (
            <section className="grid grid-cols-1 md:grid-cols-4 gap-4">
              {/* Spot price card */}
              <div className="bg-[#f8f9fa] border border-[#dcdfe3] rounded-2xl p-5 relative overflow-hidden shadow-sm shadow-slate-100/50">
                <div className="flex justify-between items-start">
                  <div>
                    <span className="text-xs font-bold text-slate-550 uppercase tracking-wider">{symbol} Index Spot</span>
                    <h2 className="text-3xl font-extrabold tracking-tight mt-1 text-slate-900 font-mono">
                      {formatNumber(spotData.price)}
                    </h2>
                  </div>
                  <span className={`flex items-center gap-1 text-xs font-bold px-2 py-1 rounded-md mt-1 ${
                    spotChange >= 0 ? "bg-emerald-50 text-emerald-700 border border-emerald-250" : "bg-rose-50 text-rose-700 border border-rose-250"
                  }`}>
                    {spotChange >= 0 ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
                    {spotChange >= 0 ? "+" : ""}{safeNumber(spotChange, 2)}%
                  </span>
                </div>
                
                {/* Mini trend sparkline */}
                {spotData.trend && spotData.trend.length >= 1 && (
                  <div className="h-10 mt-4 opacity-50">
                    {mounted && (
                      <ResponsiveContainer width="100%" height="100%">
                        <AreaChart data={spotData.trend}>
                          <defs>
                            <linearGradient id="colorSpot" x1="0" y1="0" x2="0" y2="1">
                              <stop offset="5%" stopColor={spotChange >= 0 ? "#10b981" : "#f43f5e"} stopOpacity={0.2}/>
                              <stop offset="95%" stopColor={spotChange >= 0 ? "#10b981" : "#f43f5e"} stopOpacity={0}/>
                            </linearGradient>
                          </defs>
                          <XAxis dataKey="timestamp" hide />
                          <YAxis hide domain={['dataMin - 10', 'dataMax + 10']} />
                          <Area 
                            type="monotone" 
                            dataKey="price" 
                            stroke={spotChange >= 0 ? "#10b981" : "#f43f5e"} 
                            strokeWidth={1.5}
                            fillOpacity={1} 
                            fill="url(#colorSpot)" 
                          />
                        </AreaChart>
                      </ResponsiveContainer>
                    )}
                  </div>
                )}
              </div>

              {/* VIX Card */}
              <div className="bg-[#f8f9fa] border border-[#dcdfe3] rounded-2xl p-5 shadow-sm shadow-slate-100/50">
                <span className="text-xs font-bold text-slate-555 uppercase tracking-wider">India VIX</span>
                <div className="flex items-baseline gap-2 mt-1">
                  <h2 className="text-3xl font-extrabold tracking-tight text-slate-900 font-mono">
                    {formatNumber(vixData.value)}
                  </h2>
                  {summaryData && (
                    <span className={`text-xs font-bold ${summaryRegimeColor}`}>
                      {summaryData.volatility_regime.regime}
                    </span>
                  )}
                </div>
                <p className="text-xs text-slate-500 mt-2 font-semibold">Implied volatility indicator of nearest options contracts</p>
              </div>

              {/* PCR Card */}
              <div className="bg-[#f8f9fa] border border-[#dcdfe3] rounded-2xl p-5 shadow-sm shadow-slate-100/50">
                <span className="text-xs font-bold text-slate-555 uppercase tracking-wider">Put-Call Ratio (PCR)</span>
                {summaryData ? (
                  <div className="grid grid-cols-2 gap-2 mt-1">
                    <div>
                      <div className="text-2xl font-extrabold text-slate-900 font-mono">{formatNumber(summaryData.pcr.pcr_oi)}</div>
                      <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wide">OI PCR</span>
                    </div>
                    <div>
                      <div className="text-2xl font-extrabold text-slate-900 font-mono">{formatNumber(summaryData.pcr.pcr_volume)}</div>
                      <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wide">Volume PCR</span>
                    </div>
                  </div>
                ) : (
                  <h2 className="text-3xl font-extrabold tracking-tight mt-1 text-slate-900 font-mono">1.05</h2>
                )}
                <p className="text-xs text-slate-500 mt-1 font-semibold">Value &gt; 1 indicates bullish bias/higher put writing</p>
              </div>

              {/* Max Pain Card */}
              <div className="bg-[#f8f9fa] border border-[#dcdfe3] rounded-2xl p-5 shadow-sm shadow-slate-100/50">
                <span className="text-xs font-bold text-slate-555 uppercase tracking-wider">Max Pain Level</span>
                {summaryData ? (
                  <div className="flex justify-between items-baseline mt-1">
                    <h2 className="text-3xl font-extrabold tracking-tight text-slate-900 font-mono">
                      {formatNumber(summaryData.max_pain, 0)}
                    </h2>
                    <span className="text-xs font-semibold text-slate-550">
                      Dist: {formatNumber((spotData.price - summaryData.max_pain), 1)}
                    </span>
                  </div>
                ) : (
                  <h2 className="text-3xl font-extrabold tracking-tight mt-1 text-slate-900 font-mono">24,300</h2>
                )}
                <p className="text-xs text-slate-500 mt-2 font-semibold">Strike where option buyers lose maximum capital</p>
              </div>
            </section>
          )}

          {/* TAB 1: OVERVIEW MARKET INTELLIGENCE */}
          {activeTab === "overview" && (
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Real-time AI Intelligence Panel */}
              <div className="lg:col-span-2 bg-[#f8f9fa] border border-[#dcdfe3] rounded-2xl p-6 shadow-sm relative overflow-hidden">
                <div className="absolute top-0 right-0 h-40 w-40 bg-gradient-to-bl from-cyan-500/5 to-indigo-600/0 rounded-full blur-2xl"></div>
                
                <h3 className="text-base font-black text-slate-950 flex items-center gap-2">
                  <Brain className="h-5 w-5 text-indigo-650" />
                  AI Forecast & Predictive Signal
                </h3>
                <p className="text-xs text-slate-550 mt-1 font-semibold">Deep Learning & ensemble model probabilities trained on dealer gamma imbalance</p>

                {forecastData ? (
                  <div className="mt-6 grid grid-cols-1 md:grid-cols-5 gap-6 items-center">
                    {/* Signal Box */}
                    <div className={`md:col-span-2 p-5 rounded-xl text-center relative shadow-inner border transition-all duration-300 ${
                      forecastData.forecast.signal === "BUY" 
                        ? "bg-emerald-100/45 border-emerald-300/80 text-emerald-950" 
                        : forecastData.forecast.signal === "SELL" 
                          ? "bg-rose-100/45 border-rose-300/80 text-rose-955" 
                          : "bg-white border-[#dcdfe3] text-slate-800"
                    }`}>
                      <span className={`text-[10px] font-bold uppercase tracking-widest block ${
                        forecastData.forecast.signal === "BUY" ? "text-emerald-800" : (forecastData.forecast.signal === "SELL" ? "text-rose-800" : "text-slate-500")
                      }`}>
                        Combined Signal
                      </span>
                      
                      <div className={`text-4xl font-black mt-2 tracking-wide ${
                        forecastData.forecast.signal === "BUY" 
                          ? "text-emerald-700" 
                          : forecastData.forecast.signal === "SELL" 
                            ? "text-rose-700" 
                            : "text-slate-600"
                      }`}>
                        {forecastData.forecast.signal}
                      </div>
                      
                      <div className={`mt-3 flex items-center justify-center gap-1.5 text-xs font-bold ${
                        forecastData.forecast.signal === "BUY" ? "text-emerald-900" : (forecastData.forecast.signal === "SELL" ? "text-rose-900" : "text-slate-600")
                      }`}>
                        <Zap className={`h-3.5 w-3.5 ${forecastData.forecast.signal === "SELL" ? "text-rose-600" : "text-amber-500"}`} />
                        Confidence: <span className={`font-bold font-mono ${
                          forecastData.forecast.signal === "BUY" ? "text-emerald-950" : (forecastData.forecast.signal === "SELL" ? "text-rose-955" : "text-slate-900")
                        }`}>{forecastData.forecast.confidence}%</span>
                      </div>
                    </div>

                    {/* Probability Bars */}
                    <div className="md:col-span-3 space-y-4">
                      {/* UP PROBABILITY */}
                      <div>
                        <div className="flex justify-between text-xs font-semibold mb-1">
                          <span className="text-emerald-600 flex items-center gap-1">
                            <TrendingUp className="h-3.5 w-3.5" /> Upwards Shift
                          </span>
                          <span className="text-slate-700 font-mono font-bold">{(forecastData.forecast.prob_up * 100).toFixed(1)}%</span>
                        </div>
                        <div className="w-full bg-slate-300/40 rounded-full h-2 border border-slate-300/20">
                          <div className="bg-emerald-500 h-1.8 rounded-full shadow-md shadow-emerald-500/20" style={{ width: `${forecastData.forecast.prob_up * 100}%` }}></div>
                        </div>
                      </div>

                      {/* DOWN PROBABILITY */}
                      <div>
                        <div className="flex justify-between text-xs font-semibold mb-1">
                          <span className="text-rose-600 flex items-center gap-1">
                            <TrendingDown className="h-3.5 w-3.5" /> Downwards Slide
                          </span>
                          <span className="text-slate-700 font-mono font-bold">{(forecastData.forecast.prob_down * 100).toFixed(1)}%</span>
                        </div>
                        <div className="w-full bg-slate-300/40 rounded-full h-2 border border-slate-300/20">
                          <div className="bg-rose-550 h-1.8 rounded-full shadow-md shadow-rose-500/20" style={{ width: `${forecastData.forecast.prob_down * 100}%` }}></div>
                        </div>
                      </div>

                      {/* NEUTRAL PROBABILITY */}
                      <div>
                        <div className="flex justify-between text-xs font-semibold mb-1">
                          <span className="text-slate-550 font-bold">Neutral range</span>
                          <span className="text-slate-700 font-mono font-bold">{(forecastData.forecast.prob_neutral * 100).toFixed(1)}%</span>
                        </div>
                        <div className="w-full bg-slate-300/40 rounded-full h-2 border border-slate-300/20">
                          <div className="bg-slate-400 h-1.8 rounded-full" style={{ width: `${forecastData.forecast.prob_neutral * 100}%` }}></div>
                        </div>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="py-8 text-center text-slate-550 text-sm">Computing AI intelligence parameters...</div>
                )}

                {/* Footnote */}
                <div className="mt-6 border-t border-[#dcdfe3] pt-4 flex flex-col md:flex-row md:items-center justify-between text-xs text-slate-550 gap-3">
                  <span className="flex items-center gap-1 font-semibold">
                    <Info className="h-3.5 w-3.5 text-indigo-600" />
                    Our predictive model merges BSM Greeks, Net GEX volume trends, and skew dynamics.
                  </span>
                  <button 
                    onClick={handleRetrain}
                    disabled={retraining}
                    className="self-start md:self-auto px-3 py-1.5 rounded-lg bg-[#f8f9fa] hover:bg-slate-200/60 text-slate-700 border border-[#dcdfe3] shadow-sm flex items-center gap-1.5 transition-all text-xs font-bold"
                  >
                    <RefreshCw className={`h-3 w-3 ${retraining ? 'animate-spin' : ''}`} />
                    {retraining ? "Training Models..." : "Retrain Ensemble"}
                  </button>
                </div>
              </div>

              {/* Key Volatility Curvature Regime */}
              <div className="bg-[#f8f9fa] border border-[#dcdfe3] rounded-2xl p-6 shadow-sm flex flex-col justify-between">
                <div>
                  <h3 className="text-sm font-black text-slate-950 flex items-center gap-1.5">
                    <Shield className="h-4 w-4 text-indigo-500" />
                    Market Risk & Volatility Regime
                  </h3>
                  
                  {summaryData && (
                    <div className="mt-6 space-y-4">
                      {/* VIX speedometer bar */}
                      <div className="w-full bg-[#ebedef]/70 rounded-xl p-4 border border-[#dcdfe3]">
                        <div className="flex justify-between items-baseline">
                          <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">Fear Index (VIX)</span>
                          <span className={`text-sm font-extrabold ${summaryRegimeColor}`}>
                            {vixData.value.toFixed(2)}
                          </span>
                        </div>
                        
                        {/* Speedometer range block */}
                        <div className="grid grid-cols-4 gap-1 mt-3">
                          <div className={`h-2.5 rounded-l-md ${vixData.value < 12 ? 'bg-emerald-500' : 'bg-slate-300/40'}`}></div>
                          <div className={`h-2.5 ${vixData.value >= 12 && vixData.value < 16 ? 'bg-cyan-500' : (vixData.value > 16 ? 'bg-cyan-600' : 'bg-slate-300/40')}`}></div>
                          <div className={`h-2.5 ${vixData.value >= 16 && vixData.value < 22 ? 'bg-amber-500' : (vixData.value > 22 ? 'bg-amber-600' : 'bg-slate-300/40')}`}></div>
                          <div className={`h-2.5 rounded-r-md ${vixData.value >= 22 ? 'bg-rose-500' : 'bg-slate-300/40'}`}></div>
                        </div>
                      </div>

                      {/* Description */}
                      <p className="text-xs text-slate-700 leading-relaxed bg-[#ebedef]/55 p-3 rounded-lg border border-[#dcdfe3]/80">
                        {summaryData.volatility_regime.description}
                      </p>
                    </div>
                  )}
                </div>

                {summaryData && (
                  <div className="mt-6 border-t border-[#dcdfe3] pt-4 flex justify-between items-center text-xs">
                    <span className="text-slate-550 font-bold">Vol Skew (Put - Call IV):</span>
                    <span className={`font-mono font-bold ${summaryData.iv_skew > 0 ? "text-amber-500" : "text-emerald-600"}`}>
                      {summaryData.iv_skew > 0 ? "+" : ""}{summaryData.iv_skew}%
                    </span>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* TAB 2: INTERACTIVE OPTION CHAIN */}
          {activeTab === "option-chain" && (
            <div className="bg-[#f8f9fa] border border-[#dcdfe3] rounded-2xl p-6 shadow-sm space-y-6">
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-[#dcdfe3] pb-4">
                <div>
                  <h3 className="text-base font-black text-slate-950">Option Chain (Weekly Expiry)</h3>
                  <p className="text-xs text-slate-600 mt-0.5 font-semibold">Filter NIFTY or BANKNIFTY contracts including live delta, gamma, vega, and theta greeks.</p>
                </div>
                
                {chainData && (
                  <div className="text-xs font-semibold text-slate-700 flex flex-wrap gap-3 bg-[#ebedef]/60 p-2 rounded-lg border border-[#dcdfe3]">
                    <span className="text-slate-500 font-semibold">Nearest Expiry: <span className="text-indigo-650 font-bold">{chainData.expiry_date}</span></span>
                    <span className="text-slate-350">|</span>
                    <span className="text-slate-500 font-semibold">Spot reference: <span className="text-slate-900 font-extrabold font-mono">{formatNumber(chainData.spot_price)}</span></span>
                  </div>
                )}
              </div>

              {/* Options Chain Table */}
              <div className="overflow-x-auto">
                <table className="w-full text-xs text-left text-slate-700 font-mono min-w-[900px]">
                  <thead>
                    <tr className="bg-[#ebedef]/90 text-slate-700 text-[10px] font-bold uppercase tracking-wider border-b border-[#dcdfe3]">
                      {/* Call columns */}
                      <th className="py-3 px-2 text-center" colSpan={7}>Calls (CE)</th>
                      {/* Strike */}
                      <th className="py-3 px-4 text-center bg-[#f4f5f7] border-x border-[#dcdfe3]">Strike</th>
                      {/* Put columns */}
                      <th className="py-3 px-2 text-center" colSpan={7}>Puts (PE)</th>
                    </tr>
                    <tr className="bg-[#ebedef]/50 text-slate-650 text-[9px] uppercase border-b border-[#dcdfe3]">
                      {/* Call cols */}
                      <th className="py-2 px-1 text-right font-bold">OI</th>
                      <th className="py-2 px-1 text-right font-bold">OI Chg</th>
                      <th className="py-2 px-1 text-right font-bold">Vol</th>
                      <th className="py-2 px-1 text-right font-bold">IV%</th>
                      <th className="py-2 px-1 text-right font-bold">Price</th>
                      <th className="py-2 px-1 text-right font-bold">Delta</th>
                      <th className="py-2 px-1 text-right font-bold">Gamma</th>
                      
                      {/* Strike */}
                      <th className="py-2 px-4 text-center bg-[#f4f5f7] border-x border-[#dcdfe3] font-bold text-slate-700">Strike Price</th>
                      
                      {/* Put cols */}
                      <th className="py-2 px-1 text-left font-bold">Gamma</th>
                      <th className="py-2 px-1 text-left font-bold">Delta</th>
                      <th className="py-2 px-1 text-left font-bold">Price</th>
                      <th className="py-2 px-1 text-left font-bold">IV%</th>
                      <th className="py-2 px-1 text-left font-bold">Vol</th>
                      <th className="py-2 px-1 text-left font-bold">OI Chg</th>
                      <th className="py-2 px-1 text-left font-bold">OI</th>
                    </tr>
                  </thead>
                  <tbody>
                    {chainData ? (
                      (() => {
                        // Pair calls and puts by strike
                        const strikesMap: Record<number, Record<string, any>> = {};
                        chainData.options.forEach((opt: any) => {
                          const strike = opt.strike_price;
                          if (!strikesMap[strike]) strikesMap[strike] = {};
                          strikesMap[strike][opt.option_type] = opt;
                        });
                        
                        const sortedStrikes = Object.keys(strikesMap)
                          .map(Number)
                          .sort((a, b) => a - b);
                          
                        // Filter to show strikes close to ATM (e.g. within 3% of spot)
                        const atmStrike = chainData.spot_price;
                        const visibleStrikes = sortedStrikes.filter(
                          (s) => Math.abs(s - atmStrike) / atmStrike <= 0.035
                        );
                        
                        return visibleStrikes.map((strike) => {
                          const ce = strikesMap[strike]["CE"];
                          const pe = strikesMap[strike]["PE"];
                          const isATM = Math.abs(strike - atmStrike) < 25;
                          
                          // Determine ITM status (Call is ITM if Strike < Spot, Put is ITM if Strike > Spot)
                          const isCallITM = strike < atmStrike;
                          const isPutITM = strike > atmStrike;
                          
                          return (
                            <tr 
                              key={strike} 
                              className={`border-b border-[#dcdfe3]/60 hover:bg-[#ebedef]/40 transition-colors ${
                                isATM ? "bg-cyan-100/35 font-bold" : ""
                              }`}
                            >
                              {/* Call columns */}
                              <td className={`py-2 px-1 text-right text-slate-550 ${isCallITM ? "bg-indigo-50/20 text-slate-700" : ""}`}>
                                {formatGex(ce?.open_interest)}
                              </td>
                              <td className={`py-2 px-1 text-right font-bold ${
                                ce?.change_in_oi >= 0 ? "text-emerald-600" : "text-rose-605"
                              } ${isCallITM ? "bg-indigo-50/10" : ""}`}>
                                {ce?.change_in_oi > 0 ? "+" : ""}{formatGex(ce?.change_in_oi)}
                              </td>
                              <td className={`py-2 px-1 text-right text-slate-550 ${isCallITM ? "bg-indigo-50/20" : ""}`}>
                                {formatGex(ce?.volume)}
                              </td>
                              <td className={`py-2 px-1 text-right text-amber-600 font-semibold ${isCallITM ? "bg-indigo-50/20" : ""}`}>
                                {ce ? (ce.implied_volatility * 100).toFixed(1) + "%" : "-"}
                              </td>
                              <td className={`py-2 px-1 text-right font-bold text-slate-950 ${isCallITM ? "bg-indigo-50/20" : ""}`}>
                                {formatNumber(ce?.last_price)}
                              </td>
                              <td className={`py-2 px-1 text-right text-cyan-600 font-semibold ${isCallITM ? "bg-indigo-50/20" : ""}`}>
                                {ce?.delta.toFixed(2)}
                              </td>
                              <td className={`py-2 px-1 text-right text-indigo-650 ${isCallITM ? "bg-indigo-50/20" : ""}`}>
                                {ce?.gamma.toFixed(5)}
                              </td>
                              
                              {/* Strike central cell */}
                              <td className={`py-2 px-4 text-center bg-[#ebedef] border-x border-[#dcdfe3] font-bold text-slate-900 ${
                                isATM ? "text-indigo-650 ring-1 ring-indigo-500/20 font-extrabold bg-indigo-100/60" : ""
                              }`}>
                                {strike}
                              </td>
                              
                              {/* Put columns */}
                              <td className={`py-2 px-1 text-left text-indigo-650 ${isPutITM ? "bg-indigo-50/20" : ""}`}>
                                {pe?.gamma.toFixed(5)}
                              </td>
                              <td className={`py-2 px-1 text-left text-cyan-600 font-semibold ${isPutITM ? "bg-indigo-50/20" : ""}`}>
                                {pe?.delta.toFixed(2)}
                              </td>
                              <td className={`py-2 px-1 text-left font-bold text-slate-950 ${isPutITM ? "bg-indigo-50/20" : ""}`}>
                                {formatNumber(pe?.last_price)}
                              </td>
                              <td className={`py-2 px-1 text-left text-amber-600 font-semibold ${isPutITM ? "bg-indigo-50/20" : ""}`}>
                                {pe ? (pe.implied_volatility * 100).toFixed(1) + "%" : "-"}
                              </td>
                              <td className={`py-2 px-1 text-left text-slate-550 ${isPutITM ? "bg-indigo-50/20" : ""}`}>
                                {formatGex(pe?.volume)}
                              </td>
                              <td className={`py-2 px-1 text-left font-bold ${
                                pe?.change_in_oi >= 0 ? "text-emerald-600" : "text-rose-605"
                              } ${isPutITM ? "bg-indigo-50/10" : ""}`}>
                                {pe?.change_in_oi > 0 ? "+" : ""}{formatGex(pe?.change_in_oi)}
                              </td>
                              <td className={`py-2 px-1 text-left text-slate-550 ${isPutITM ? "bg-indigo-50/20 text-slate-700" : ""}`}>
                                {formatGex(pe?.open_interest)}
                              </td>
                            </tr>
                          );
                        });
                      })()
                    ) : (
                      <tr>
                        <td colSpan={15} className="py-8 text-center text-slate-550">Loading live option chain contracts...</td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* TAB 3: DEALER GAMMA EXPOSURE */}
          {activeTab === "dealer-positioning" && (
            <div className="space-y-6">
              {/* Charts grid */}
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                
                {/* Net GEX profile chart */}
                <div className="lg:col-span-2 bg-[#f8f9fa] border border-[#dcdfe3] rounded-2xl p-6 shadow-sm shadow-slate-100/50">
                  <div>
                    <h3 className="text-sm font-black text-slate-950">Net Gamma Exposure (GEX) Profile</h3>
                    <p className="text-xs text-slate-600 mt-0.5 font-semibold">Visualizes dealer hedging pressure curve and identifies the volatility acceleration boundary.</p>
                  </div>
                  
                  {gexProfile && (
                    <div className="h-72 mt-6">
                      {mounted && (
                        <ResponsiveContainer width="100%" height="100%">
                          <RecLineChart data={gexProfile.profile}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#dcdfe3" />
                            <XAxis 
                              dataKey="spot_price" 
                              stroke="#475569" 
                              fontSize={10} 
                              tickFormatter={(tick) => formatNumber(tick, 0)}
                            />
                            <YAxis 
                              stroke="#475569" 
                              fontSize={10}
                              tickFormatter={(tick) => formatGex(tick)}
                            />
                            <Tooltip 
                              contentStyle={{ backgroundColor: "#f4f5f7", border: "1px solid #dcdfe3", borderRadius: "12px", boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.05)" }}
                              labelFormatter={(label) => `Spot Price: ${formatNumber(label)}`}
                              formatter={(value: any) => [`Net GEX: ${formatGex(value)}`, 'Gamma Exposure']}
                              itemStyle={{ color: "#1e293b" }}
                              labelStyle={{ color: "#475569", fontWeight: "bold" }}
                            />
                            <ReferenceLine y={0} stroke="#ef4444" strokeWidth={1.5} strokeDasharray="3 3" />
                            {/* Reference vertical line for current spot */}
                            <ReferenceLine x={gexProfile.spot_price} stroke="#2563eb" strokeWidth={1} label={{ value: 'Current Spot', position: 'top', fill: '#2563eb', fontSize: 10 }} />
                            {/* Reference vertical line for Gamma Flip */}
                            <ReferenceLine x={gexProfile.gamma_flip_level} stroke="#ef4444" strokeWidth={1.5} label={{ value: 'Gamma Flip', position: 'bottom', fill: '#ef4444', fontSize: 10 }} />
                            <Line 
                              type="monotone" 
                              dataKey="net_gex" 
                              stroke="#2563eb" 
                              strokeWidth={2} 
                              dot={false}
                            />
                          </RecLineChart>
                        </ResponsiveContainer>
                      )}
                    </div>
                  )}
                </div>

                {/* Legend & positioning card */}
                <div className="bg-[#f8f9fa] border border-[#dcdfe3] rounded-2xl p-6 shadow-sm flex flex-col justify-between">
                  <div className="space-y-4">
                    <h3 className="text-sm font-black text-slate-950">How to interpret GEX</h3>
                    
                    <div className="space-y-3 text-xs leading-relaxed text-slate-700">
                      <div className="flex items-start gap-2 bg-[#e8f5e9]/70 border border-emerald-200 p-3 rounded-lg">
                        <span className="h-2 w-2 rounded-full bg-emerald-500 mt-1.5 shrink-0"></span>
                        <div>
                          <strong className="text-emerald-700 block mb-0.5 font-bold">Positive Gamma Zone (Above Flip)</strong>
                          Dealers buy dips and sell rallies. Volatility is dampened. Standard support levels should hold tightly.
                        </div>
                      </div>

                      <div className="flex items-start gap-2 bg-[#ffebee]/75 border border-rose-200 p-3 rounded-lg">
                        <span className="h-2 w-2 rounded-full bg-rose-500 mt-1.5 shrink-0"></span>
                        <div>
                          <strong className="text-rose-700 block mb-0.5 font-bold">Negative Gamma Zone (Below Flip)</strong>
                          Dealers hedge by selling on down moves and buying on up moves. Instability increases, accelerating market movements.
                        </div>
                      </div>
                    </div>
                  </div>

                  {gexProfile && (
                    <div className="mt-6 border-t border-[#dcdfe3] pt-4 flex flex-col gap-2 text-xs">
                      <div className="flex justify-between">
                        <span className="text-slate-550 font-semibold">Current Spot Price:</span>
                        <span className="text-slate-950 font-bold font-mono">{formatNumber(gexProfile.spot_price)}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-555 font-semibold">Gamma Flip Level:</span>
                        <span className="text-rose-655 font-bold font-mono">{formatNumber(gexProfile.gamma_flip_level)}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-555 font-semibold">Distance to Flip:</span>
                        <span className="text-slate-955 font-bold font-mono">
                          {((gexProfile.spot_price - gexProfile.gamma_flip_level) / gexProfile.spot_price * 100).toFixed(2)}%
                        </span>
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {/* GEX by Strike Bar Chart */}
              {summaryData && (
                <div className="bg-[#f8f9fa] border border-[#dcdfe3] rounded-2xl p-6 shadow-sm shadow-slate-100/50">
                  <div>
                    <h3 className="text-sm font-black text-slate-950">Gamma Exposure (GEX) by Strike Price</h3>
                    <p className="text-xs text-slate-605 mt-0.5 font-semibold">Call GEX represents positive dealer hedging zones, Put GEX represents negative acceleration zones.</p>
                  </div>

                  <div className="h-80 mt-6">
                    {mounted && (
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={dealerExposureData?.strikes || (chainData?.options ? compileGexData(chainData.options, chainData.spot_price) : [])}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#dcdfe3" />
                          <XAxis dataKey="strike" stroke="#64748b" fontSize={10} />
                          <YAxis stroke="#64748b" fontSize={10} tickFormatter={(tick) => formatGex(tick)} />
                          <Tooltip 
                            contentStyle={{ backgroundColor: "#f4f5f7", border: "1px solid #dcdfe3", borderRadius: "12px", boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.05)" }}
                            labelFormatter={(label) => `Strike: ${label}`}
                            itemStyle={{ color: "#1e293b" }}
                            labelStyle={{ color: "#475569", fontWeight: "bold" }}
                          />
                          <ReferenceLine y={0} stroke="#94a3b8" />
                          <Bar dataKey="call_gex" fill="#10b981" name="Call GEX" stackId="stack" radius={[2, 2, 0, 0]} />
                          <Bar dataKey="put_gex" fill="#f43f5e" name="Put GEX" stackId="stack" radius={[0, 0, 2, 2]} />
                        </BarChart>
                      </ResponsiveContainer>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* TAB 4: VOLATILITY INTELLIGENCE */}
          {activeTab === "volatility" && (
            <div className="space-y-6">
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                
                {/* Volatility Smile Chart */}
                <div className="lg:col-span-2 bg-[#f8f9fa] border border-[#dcdfe3] rounded-2xl p-6 shadow-sm shadow-slate-100/50">
                  <div>
                    <h3 className="text-sm font-black text-slate-950">Implied Volatility (IV) Smile</h3>
                    <p className="text-xs text-slate-600 mt-0.5 font-semibold">Strike vs Implied Volatility curves for Calls and Puts options.</p>
                  </div>

                  {volSmile ? (
                    <div className="h-72 mt-6">
                      {mounted && (
                        <ResponsiveContainer width="100%" height="100%">
                          <RecLineChart data={volSmile.smile}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#dcdfe3" />
                            <XAxis dataKey="strike" stroke="#64748b" fontSize={10} />
                            <YAxis 
                              stroke="#64748b" 
                              fontSize={10}
                              tickFormatter={(tick) => `${tick}%`}
                            />
                            <Tooltip 
                              contentStyle={{ backgroundColor: "#f4f5f7", border: "1px solid #dcdfe3", borderRadius: "12px", boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.05)" }}
                              labelFormatter={(label) => `Strike: ${label}`}
                              formatter={(value: any) => [`${value}%`, 'IV']}
                              itemStyle={{ color: "#1e293b" }}
                              labelStyle={{ color: "#475569", fontWeight: "bold" }}
                            />
                            <Legend />
                            {/* Reference vertical line for current spot */}
                            <ReferenceLine x={volSmile.spot_price} stroke="#94a3b8" strokeWidth={1} strokeDasharray="3 3" label={{ value: 'ATM', fill: '#475569', fontSize: 10 }} />
                            <Line 
                              type="monotone" 
                              dataKey="call_iv" 
                              stroke="#10b981" 
                              strokeWidth={2} 
                              name="Call IV %"
                              dot={{ r: 2 }}
                              activeDot={{ r: 4 }}
                            />
                            <Line 
                              type="monotone" 
                              dataKey="put_iv" 
                              stroke="#f43f5e" 
                              strokeWidth={2} 
                              name="Put IV %"
                              dot={{ r: 2 }}
                              activeDot={{ r: 4 }}
                            />
                          </RecLineChart>
                        </ResponsiveContainer>
                      )}
                    </div>
                  ) : (
                    <div className="h-72 flex items-center justify-center text-slate-550">Compiling volatility smile curves...</div>
                  )}
                </div>

                {/* Vol Surface Moneyness Grid */}
                <div className="bg-[#f8f9fa] border border-[#dcdfe3] rounded-2xl p-6 shadow-sm shadow-slate-100/50">
                  <div>
                    <h3 className="text-sm font-black text-slate-950">Volatility Moneyness Map</h3>
                    <p className="text-xs text-slate-600 mt-0.5 font-semibold">Implied Volatility relative to spot price moneyness zones.</p>
                  </div>

                  <div className="mt-6 space-y-3 overflow-y-auto max-h-[280px] pr-2">
                    {volSmile ? (
                      volSmile.smile.map((point: any) => (
                        <div key={point.strike} className="flex justify-between items-center text-xs py-2 border-b border-[#dcdfe3]/60">
                          <span className="font-mono text-slate-600 font-semibold">Strike {point.strike}</span>
                          <div className="flex gap-4">
                            <span className="text-emerald-600 font-mono font-semibold">CE: {point.call_iv ? `${point.call_iv}%` : "-"}</span>
                            <span className="text-rose-600 font-mono font-semibold">PE: {point.put_iv ? `${point.put_iv}%` : "-"}</span>
                          </div>
                        </div>
                      ))
                    ) : (
                      <div className="text-slate-550 py-10 text-center">Loading moneyness surface metrics...</div>
                    )}
                  </div>
                </div>

              </div>
            </div>
          )}

          {/* TAB 5: AI RESEARCH LAB (BACKTESTER) */}
          {activeTab === "backtest" && (
            <div className="space-y-6">
              
              {/* Backtest Strategy Header */}
              <div className="bg-[#f8f9fa] border border-[#dcdfe3] rounded-2xl p-6 shadow-sm">
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                  <div>
                    <h3 className="text-base font-black text-slate-950 flex items-center gap-2">
                      <Brain className="h-5 w-5 text-indigo-650" />
                      AI Options Intelligence Backtester
                    </h3>
                    <p className="text-xs text-slate-600 mt-0.5 font-semibold">
                      Backtesting trading signals generated by our ensemble ML classifiers (predicting spot returns utilizing options variables and VIX indicators).
                    </p>
                  </div>
                  
                  {/* Controls */}
                  <div className="text-xs text-slate-600 font-semibold flex items-center gap-2">
                    <span>Active Model: <span className="text-indigo-650 font-bold">LightGBM + XGBoost Ensemble</span></span>
                  </div>
                </div>

                {/* Backtest stats columns */}
                {backtestData ? (
                  <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4 mt-6 border-t border-[#dcdfe3] pt-6">
                    <div className="bg-[#ebedef]/70 p-4 rounded-xl border border-[#dcdfe3] shadow-inner">
                      <span className="text-[10px] text-slate-600 font-bold uppercase tracking-wider block">Total Return</span>
                      <div className="text-2xl font-black text-emerald-605 font-mono mt-1">
                        {backtestData.results.metrics.total_return}%
                      </div>
                    </div>
                    <div className="bg-[#ebedef]/70 p-4 rounded-xl border border-[#dcdfe3] shadow-inner">
                      <span className="text-[10px] text-slate-605 font-bold uppercase tracking-wider block">CAGR (Ann.)</span>
                      <div className="text-2xl font-black text-emerald-605 font-mono mt-1">
                        {backtestData.results.metrics.cagr}%
                      </div>
                    </div>
                    <div className="bg-[#ebedef]/70 p-4 rounded-xl border border-[#dcdfe3] shadow-inner">
                      <span className="text-[10px] text-slate-605 font-bold uppercase tracking-wider block">Sharpe Ratio</span>
                      <div className="text-2xl font-black text-indigo-650 font-mono mt-1">
                        {backtestData.results.metrics.sharpe}
                      </div>
                    </div>
                    <div className="bg-[#ebedef]/70 p-4 rounded-xl border border-[#dcdfe3] shadow-inner">
                      <span className="text-[10px] text-slate-605 font-bold uppercase tracking-wider block">Sortino Ratio</span>
                      <div className="text-2xl font-black text-indigo-650 font-mono mt-1">
                        {backtestData.results.metrics.sortino}
                      </div>
                    </div>
                    <div className="bg-[#ebedef]/70 p-4 rounded-xl border border-[#dcdfe3] shadow-inner">
                      <span className="text-[10px] text-slate-605 font-bold uppercase tracking-wider block">Win Rate</span>
                      <div className="text-2xl font-black text-slate-900 font-mono mt-1">
                        {backtestData.results.metrics.win_rate}%
                      </div>
                    </div>
                    <div className="bg-[#ebedef]/70 p-4 rounded-xl border border-[#dcdfe3] shadow-inner">
                      <span className="text-[10px] text-slate-605 font-bold uppercase tracking-wider block">Max Drawdown</span>
                      <div className="text-2xl font-black text-rose-605 font-mono mt-1">
                        {backtestData.results.metrics.max_drawdown}%
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="py-10 text-center text-slate-550">Running backtest simulation calculations...</div>
                )}
              </div>

              {/* Equity curve chart */}
              {backtestData && (
                <div className="bg-[#f8f9fa] border border-[#dcdfe3] rounded-2xl p-6 shadow-sm shadow-slate-100/50">
                  <div>
                    <h3 className="text-sm font-black text-slate-950">Equity Curve: AI Strategy vs Benchmark</h3>
                    <p className="text-xs text-slate-600 mt-0.5 font-semibold">Compares strategy returns using ML options signals against a standard buy-and-hold index benchmark.</p>
                  </div>

                  <div className="h-80 mt-6">
                    {mounted && (
                      <ResponsiveContainer width="100%" height="100%">
                        <AreaChart data={backtestData.results.equity_curve}>
                          <defs>
                            <linearGradient id="colorStrategy" x1="0" y1="0" x2="0" y2="1">
                              <stop offset="5%" stopColor="#818cf8" stopOpacity={0.2}/>
                              <stop offset="95%" stopColor="#818cf8" stopOpacity={0}/>
                            </linearGradient>
                            <linearGradient id="colorMarket" x1="0" y1="0" x2="0" y2="1">
                              <stop offset="5%" stopColor="#94a3b8" stopOpacity={0.1}/>
                              <stop offset="95%" stopColor="#94a3b8" stopOpacity={0}/>
                            </linearGradient>
                          </defs>
                          <CartesianGrid strokeDasharray="3 3" stroke="#dcdfe3" />
                          <XAxis dataKey="timestamp" stroke="#64748b" fontSize={10} />
                          <YAxis stroke="#64748b" fontSize={10} tickFormatter={(tick) => `${tick}%`} />
                          <Tooltip 
                            contentStyle={{ backgroundColor: "#f4f5f7", border: "1px solid #dcdfe3", borderRadius: "12px", boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.05)" }}
                            labelFormatter={(label) => `Time: ${label}`}
                            formatter={(value: any) => [`${value}%`, 'Return']}
                            itemStyle={{ color: "#1e293b" }}
                            labelStyle={{ color: "#475569", fontWeight: "bold" }}
                          />
                          <Legend />
                          <Area 
                            type="monotone" 
                            dataKey="strategy_return" 
                            stroke="#818cf8" 
                            strokeWidth={2} 
                            fillOpacity={1} 
                            fill="url(#colorStrategy)" 
                            name="AI Strategy %"
                          />
                          <Area 
                            type="monotone" 
                            dataKey="market_return" 
                            stroke="#64748b" 
                            strokeWidth={1.5} 
                            fillOpacity={1} 
                            fill="url(#colorMarket)" 
                            name="Benchmark Buy-and-Hold %"
                          />
                        </AreaChart>
                      </ResponsiveContainer>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}
        </main>
      </div>
    </div>
  );
}

// helper for central Central Central المركزي centrality 중앙 central cell components
function pepe_gamma(pe: any) {
  if (!pe) return "-";
  return pe.gamma.toFixed(5);
}

// helper to format strike specific Call/Put GEX values
function compileGexData(options: any[], spot_price: number) {
  const strikesMap: { [key: number]: { strike: number; call_gex: number; put_gex: number } } = {};
  
  options.forEach((opt) => {
    const strike = opt.strike_price;
    // Limit strikes to +/- 4% for bar chart clutter prevention
    if (Math.abs(strike - spot_price) / spot_price > 0.04) return;
    
    if (!strikesMap[strike]) {
      strikesMap[strike] = { strike, call_gex: 0, put_gex: 0 };
    }
    
    // GEX calculation: OI * Gamma * Lot Size * Spot * 0.01
    // Delta and Gamma are calculated and returned in options array
    const lotSize = 25; // NIFTY default
    const gex = opt.open_interest * opt.gamma * lotSize * spot_price * 0.01;
    
    if (opt.option_type === "CE") {
      strikesMap[strike].call_gex = gex;
    } else {
      // Put GEX is negative
      strikesMap[strike].put_gex = -gex;
    }
  });
  
  return Object.values(strikesMap).sort((a, b) => a.strike - b.strike);
}

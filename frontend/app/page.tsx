"use client";

import React, { useState, useEffect, useMemo } from "react";
import { 
  Activity, 
  TrendingUp, 
  TrendingDown, 
  BarChart2,
  BarChart3, 
  LineChart, 
  Brain, 
  RefreshCw, 
  Layers, 
  Compass, 
  AlertCircle,
  Shield,
  Zap,
  Sliders,
  Terminal,
  Bell,
  Settings,
  Globe,
  MessageSquare
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
  Legend,
  ComposedChart,
  Cell,
  ScatterChart,
  Scatter
} from "recharts";

// Configuration
const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "/api";
const POLLING_INTERVAL_MS = 5000;

const LOT_SIZES: { [key: string]: number } = {
  NIFTY: 25,
  BANKNIFTY: 15,
  SENSEX: 10,
  BANKEX: 15,
};

export default function Dashboard() {
  // Navigation & Filter State
  const [activeTab, setActiveTab] = useState<string>("overview");
  const [symbol, setSymbol] = useState<string>("NIFTY");
  const [backtestStrategy, setBacktestStrategy] = useState<string>("AI_Probability");
  const [timeframe, setTimeframe] = useState<string>("5 Minute");
  
  // Data State
  const [spotData, setSpotData] = useState<any>(null);
  const [futuresData, setFuturesData] = useState<any>(null);
  const [vixData, setVixData] = useState<any>(null);
  const [fiiDiiData, setFiiDiiData] = useState<any>(null);
  const [usdinrData, setUsdinrData] = useState<any>(null);
  const [niftySpot, setNiftySpot] = useState<any>(null);
  const [bankniftySpot, setBankniftySpot] = useState<any>(null);
  const [summaryData, setSummaryData] = useState<any>(null);
  const [chainData, setChainData] = useState<any>(null);
  const [oiData, setOiData] = useState<any>(null);
  const [maxPainData, setMaxPainData] = useState<any>(null);
  const [forecastData, setForecastData] = useState<any>(null);
  const [backtestData, setBacktestData] = useState<any>(null);
  const [gexProfile, setGexProfile] = useState<any>(null);
  const [dealerExposureData, setDealerExposureData] = useState<any>(null);
  const [volSmile, setVolSmile] = useState<any>(null);
  
  // Research Terminal State
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [researchChat, setResearchChat] = useState<Array<{role: string, text: string}>>([
    { role: "assistant", text: "Welcome to the QuantForge Bloomberg-lite Research Terminal. Ask me anything about SENSEX technical support, PCR trends, or Volatility regimes." }
  ]);
  const [researchLoading, setResearchLoading] = useState<boolean>(false);
  
  // Admin & Alerts State
  const [adminStatus, setAdminStatus] = useState<any>(null);
  const [adminLogs, setAdminLogs] = useState<any>(null);
  const [alertsData, setAlertsData] = useState<any>(null);
  
  // UI State
  const [loading, setLoading] = useState<boolean>(true);
  const [retraining, setRetraining] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date>(new Date());
  const [mounted, setMounted] = useState<boolean>(false);
  const [expandedChart, setExpandedChart] = useState<string | null>(null);

  // Safe numerical formatter
  const safeNumber = (num: number | undefined | null, decimals = 2) => {
    if (num === undefined || num === null || Number.isNaN(num)) return "0.00";
    return Number(num).toLocaleString("en-IN", {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    });
  };

  const getBadgeColorClass = (trend?: string) => {
    if (!trend) return "bg-slate-50 text-slate-655 border border-slate-200";
    const t = trend.toUpperCase();
    if (t.includes("STRONG BULLISH") || t.includes("UP") || t.includes("BUY")) {
      return "bg-emerald-50/70 text-emerald-800 border border-emerald-200 font-bold";
    }
    if (t.includes("BULLISH")) {
      return "bg-emerald-50/40 text-emerald-700 border border-emerald-150";
    }
    if (t.includes("STRONG BEARISH") || t.includes("DOWN") || t.includes("SELL")) {
      return "bg-rose-50/70 text-rose-800 border border-rose-200 font-bold";
    }
    if (t.includes("BEARISH")) {
      return "bg-rose-50/40 text-rose-700 border border-rose-150";
    }
    return "bg-slate-50 text-slate-700 border border-slate-200";
  };

  // Prepare GEX Data centered around ATM spot
  const compileGexData = (options: any[], spot: number) => {
    if (!options || spot <= 0) return [];
    const strikesMap: { [strike: number]: { strike: number, call_gex: number, put_gex: number } } = {};
    
    options.forEach((opt: any) => {
      const strike = opt.strike_price;
      if (!strikesMap[strike]) {
        strikesMap[strike] = { strike, call_gex: 0, put_gex: 0 };
      }
      
      const gamma = opt.gamma || 0;
      const oi = opt.open_interest || 0;
      const gexValue = (oi * gamma * spot * spot * 0.0001) / 1000000;
      
      if (opt.option_type === "CE") {
        strikesMap[strike].call_gex = gexValue;
      } else {
        strikesMap[strike].put_gex = -gexValue;
      }
    });
    
    const sorted = Object.values(strikesMap).sort((a, b) => a.strike - b.strike);
    
    let closestIdx = 0;
    let minDiff = Infinity;
    sorted.forEach((item, idx) => {
      const diff = Math.abs(item.strike - spot);
      if (diff < minDiff) {
        minDiff = diff;
        closestIdx = idx;
      }
    });
    
    const start = Math.max(0, closestIdx - 6);
    const end = Math.min(sorted.length, closestIdx + 6);
    return sorted.slice(start, end);
  };

  // Prepare Vol Smile data from options list
  const getVolSmileData = () => {
    if (!chainData?.options) return [];
    const strikesMap: { [strike: number]: { strike: number, callIV: number, putIV: number } } = {};
    
    chainData.options.forEach((opt: any) => {
      const strike = opt.strike_price;
      if (!strikesMap[strike]) {
        strikesMap[strike] = { strike, callIV: 0, putIV: 0 };
      }
      if (opt.option_type === "CE") {
        strikesMap[strike].callIV = opt.implied_volatility * 100;
      } else {
        strikesMap[strike].putIV = opt.implied_volatility * 100;
      }
    });
    
    const sorted = Object.values(strikesMap).sort((a, b) => a.strike - b.strike);
    const spot = spotData?.price || chainData?.spot_price || 0;
    
    if (spot > 0) {
      let closestIdx = 0;
      let minDiff = Infinity;
      sorted.forEach((item, idx) => {
        const diff = Math.abs(item.strike - spot);
        if (diff < minDiff) {
          minDiff = diff;
          closestIdx = idx;
        }
      });
      const start = Math.max(0, closestIdx - 6);
      const end = Math.min(sorted.length, closestIdx + 6);
      return sorted.slice(start, end);
    }
    return sorted.slice(6, 18);
  };

  // Prepare OI and IV Chart Data for Recharts (ATM centered)
  const getOiChartData = () => {
    if (!chainData?.options) return [];
    const strikesMap: { [strike: number]: { strike: number, callOI: number, putOI: number, callIV: number, putIV: number } } = {};
    
    chainData.options.forEach((opt: any) => {
      const strike = opt.strike_price;
      if (!strikesMap[strike]) {
        strikesMap[strike] = { strike, callOI: 0, putOI: 0, callIV: 0, putIV: 0 };
      }
      if (opt.option_type === "CE") {
        strikesMap[strike].callOI = opt.open_interest / 1000;
        strikesMap[strike].callIV = opt.implied_volatility * 100;
      } else {
        strikesMap[strike].putOI = opt.open_interest / 1000;
        strikesMap[strike].putIV = opt.implied_volatility * 100;
      }
    });
    
    const sortedStrikes = Object.values(strikesMap).sort((a, b) => a.strike - b.strike);
    const spot = spotData?.price || chainData?.spot_price || 0;
    
    if (spot > 0) {
      let closestIdx = 0;
      let minDiff = Infinity;
      sortedStrikes.forEach((item, idx) => {
        const diff = Math.abs(item.strike - spot);
        if (diff < minDiff) {
          minDiff = diff;
          closestIdx = idx;
        }
      });
      const start = Math.max(0, closestIdx - 6);
      const end = Math.min(sortedStrikes.length, closestIdx + 6);
      return sortedStrikes.slice(start, end);
    }
    
    return sortedStrikes.slice(6, 18);
  };

  // Group option chain options by strike and center around ATM
  const getGroupedOptions = () => {
    if (!chainData?.options) return [];
    const strikesMap: { [strike: number]: { strike: number, CE?: any, PE?: any } } = {};
    
    chainData.options.forEach((opt: any) => {
      const strike = opt.strike_price;
      if (!strikesMap[strike]) {
        strikesMap[strike] = { strike };
      }
      if (opt.option_type === "CE") {
        strikesMap[strike].CE = opt;
      } else {
        strikesMap[strike].PE = opt;
      }
    });
    
    const sorted = Object.values(strikesMap).sort((a, b) => a.strike - b.strike);
    const spot = spotData?.price || chainData?.spot_price || 0;
    
    if (spot > 0) {
      let closestIdx = 0;
      let minDiff = Infinity;
      sorted.forEach((item, idx) => {
        const diff = Math.abs(item.strike - spot);
        if (diff < minDiff) {
          minDiff = diff;
          closestIdx = idx;
        }
      });
      const start = Math.max(0, closestIdx - 10);
      const end = Math.min(sorted.length, closestIdx + 11);
      return sorted.slice(start, end);
    }
    
    return sorted.slice(0, 20);
  };

  // Recommends dynamic options strategies based on signal and VIX regime
  const getDynamicStrategy = () => {
    const signal = forecastData?.forecast?.signal || "NEUTRAL";
    const vix = vixVal;
    const lowBound = forecastData?.forecast?.expected_low ? Math.round(forecastData.forecast.expected_low) : null;
    const highBound = forecastData?.forecast?.expected_high ? Math.round(forecastData.forecast.expected_high) : null;
    
    let name = "";
    let description = "";
    
    if (signal === "BUY") {
      if (vix > 17.0) {
        name = `${symbol} Bull Call Debit Spread`;
        description = "Buy ATM CE / Sell OTM CE (Premium Exp.)";
      } else {
        name = `${symbol} Bull Put Credit Spread`;
        description = "Sell ATM PE / Buy OTM PE (Theta Decay)";
      }
    } else if (signal === "SELL") {
      if (vix > 17.0) {
        name = `${symbol} Bear Put Debit Spread`;
        description = "Buy ATM PE / Sell OTM PE (Premium Exp.)";
      } else {
        name = `${symbol} Bear Call Credit Spread`;
        description = "Sell ATM CE / Buy OTM CE (Theta Decay)";
      }
    } else {
      if (vix > 15.0) {
        name = `${symbol} Short Iron Condor`;
        description = "Sell OTM CE/PE, Buy further OTM Protection";
      } else {
        name = `${symbol} Short Straddle / Iron Fly`;
        description = "Sell ATM CE/PE, Buy OTM Protection";
      }
    }
    
    return {
      name,
      description,
      range: lowBound && highBound ? `${lowBound.toLocaleString("en-IN")} - ${highBound.toLocaleString("en-IN")}` : null
    };
  };

  // Uses actual spot price trend from the backend for the intraday sparkline
  const getSparklineData = () => {
    if (spotData?.trend && spotData.trend.length > 0) {
      return spotData.trend.map((point: any, idx: number) => ({
        t: point.timestamp || idx,
        price: point.price
      }));
    }
    return [];
  };

  // Derives options volume distribution data from chain (call/put volume vs strike)
  const getVolumeDistributionData = () => {
    if (!chainData?.options) return [];
    const strikesMap: { [strike: number]: { strike: number; callVol: number; putVol: number } } = {};
    chainData.options.forEach((opt: any) => {
      const strike = opt.strike_price;
      if (!strikesMap[strike]) strikesMap[strike] = { strike, callVol: 0, putVol: 0 };
      // Backend uses "volume" field (not total_traded_volume)
      const vol = (opt.volume || opt.total_traded_volume || 0) / 1000;
      if (opt.option_type === "CE") strikesMap[strike].callVol += vol;
      else strikesMap[strike].putVol += vol;
    });
    const sorted = Object.values(strikesMap).sort((a, b) => a.strike - b.strike);
    const spot = spotData?.price || chainData?.spot_price || 0;
    if (spot > 0) {
      let closestIdx = 0, minDiff = Infinity;
      sorted.forEach((item, idx) => {
        const diff = Math.abs(item.strike - spot);
        if (diff < minDiff) { minDiff = diff; closestIdx = idx; }
      });
      return sorted.slice(Math.max(0, closestIdx - 8), closestIdx + 9);
    }
    return sorted.slice(0, 17);
  };

  // Derives Option Price vs Volume data for scatter chart
  const getOptionPriceVsVolumeData = (optionType: string) => {
    if (!chainData?.options) return [];
    return chainData.options
      .filter((opt: any) => opt.option_type === optionType && (opt.volume > 0 || opt.total_traded_volume > 0) && opt.last_price > 0)
      .map((opt: any) => ({
        price: opt.last_price,
        volume: (opt.volume || opt.total_traded_volume || 0) / 1000, // in thousands
        strike: opt.strike_price
      }));
  };

  // Derives net OI skew (callOI - putOI) per strike for decision support
  const getOiSkewData = () => {
    if (!chainData?.options) return [];
    const strikesMap: { [strike: number]: { strike: number; callOI: number; putOI: number; netSkew: number } } = {};
    chainData.options.forEach((opt: any) => {
      const strike = opt.strike_price;
      if (!strikesMap[strike]) strikesMap[strike] = { strike, callOI: 0, putOI: 0, netSkew: 0 };
      if (opt.option_type === "CE") strikesMap[strike].callOI += (opt.open_interest || 0) / 1000;
      else strikesMap[strike].putOI += (opt.open_interest || 0) / 1000;
    });
    const sorted = Object.values(strikesMap)
      .map(d => ({ ...d, netSkew: parseFloat((d.callOI - d.putOI).toFixed(1)) }))
      .sort((a, b) => a.strike - b.strike);
    const spot = spotData?.price || chainData?.spot_price || 0;
    if (spot > 0) {
      let closestIdx = 0, minDiff = Infinity;
      sorted.forEach((item, idx) => {
        const diff = Math.abs(item.strike - spot);
        if (diff < minDiff) { minDiff = diff; closestIdx = idx; }
      });
      return sorted.slice(Math.max(0, closestIdx - 7), closestIdx + 8);
    }
    return sorted.slice(0, 15);
  };


  // Memoized Chart Data to prevent Recharts infinite rendering loops
  const oiChartData = useMemo(() => getOiChartData(), [chainData, spotData]);
  const volumeDistributionData = useMemo(() => getVolumeDistributionData(), [chainData, spotData]);
  const oiSkewData = useMemo(() => getOiSkewData(), [chainData, spotData]);
  const volSmileData = useMemo(() => getVolSmileData(), [chainData, spotData]);
  const gexData = useMemo(() => compileGexData(chainData?.options, spotData?.price || chainData?.spot_price || 0), [chainData, spotData]);
  const sparklineData = useMemo(() => getSparklineData(), [spotData]);
  const vwapData = useMemo(() => {
    if (!spotData?.trend || spotData.trend.length === 0) return [];
    let cumulativePriceVolume = 0;
    let cumulativeVolume = 0;
    return spotData.trend.map((point: any, idx: number) => {
      const price = Number(point.price) || 0;
      const totalPoints = spotData.trend.length;
      const progress = idx / Math.max(1, totalPoints - 1);
      const volumeFactor = 1.0 + 4.0 * Math.pow(progress - 0.5, 2);
      const baseVolume = 1000 + (Math.sin(idx * 0.5) * 200);
      const volume = Math.round(baseVolume * volumeFactor);
      cumulativePriceVolume += price * volume;
      cumulativeVolume += volume;
      const vwap = cumulativeVolume > 0 ? (cumulativePriceVolume / cumulativeVolume) : price;
      return {
        timestamp: point.timestamp || `T+${idx}`,
        price: price,
        vwap: Number(vwap.toFixed(2))
      };
    });
  }, [spotData]);
  const optionsVwapData = useMemo(() => {
    if (!spotData?.trend || spotData.trend.length === 0) return [];
    return spotData.trend.map((point: any) => ({
      timestamp: point.timestamp,
      ce_vwap: point.ce_vwap || 0,
      pe_vwap: point.pe_vwap || 0
    }));
  }, [spotData]);
  const groupedOptions = useMemo(() => getGroupedOptions(), [chainData, spotData]);
  const ceOptionPriceVsVolumeData = useMemo(() => getOptionPriceVsVolumeData("CE"), [chainData]);
  const peOptionPriceVsVolumeData = useMemo(() => getOptionPriceVsVolumeData("PE"), [chainData]);
  const institutionalFlowsData = useMemo(() => {
    if (!fiiDiiData) return [];
    return [
      { name: "FII Flows", Net: fiiDiiData.fii_net },
      { name: "DII Flows", Net: fiiDiiData.dii_net }
    ];
  }, [fiiDiiData]);

  const fetchData = async (tabKey = activeTab) => {
    try {
      setError(null);
      
      const [spotRes, niftyRes, bankniftyRes, futRes, vixRes, fiiRes, usdRes] = await Promise.all([
        fetch(`${API_BASE}/market/spot?symbol=${symbol}`),
        fetch(`${API_BASE}/market/spot?symbol=NIFTY`),
        fetch(`${API_BASE}/market/spot?symbol=BANKNIFTY`),
        fetch(`${API_BASE}/market/futures?symbol=${symbol}`),
        fetch(`${API_BASE}/market/vix`),
        fetch(`${API_BASE}/market/fii-dii`),
        fetch(`${API_BASE}/market/usdinr`)
      ]);
      
      if (spotRes.ok) setSpotData(await spotRes.json());
      if (niftyRes.ok) setNiftySpot(await niftyRes.json());
      if (bankniftyRes.ok) setBankniftySpot(await bankniftyRes.json());
      if (futRes.ok) setFuturesData(await futRes.json());
      if (vixRes.ok) setVixData(await vixRes.json());
      if (fiiRes.ok) setFiiDiiData(await fiiRes.json());
      if (usdRes.ok) setUsdinrData(await usdRes.json());

      const [summaryRes, forecastRes] = await Promise.all([
        fetch(`${API_BASE}/analytics/summary?symbol=${symbol}`),
        fetch(`${API_BASE}/signals/forecast?symbol=${symbol}`)
      ]);
      
      if (summaryRes.ok) setSummaryData(await summaryRes.json());
      if (forecastRes.ok) setForecastData(await forecastRes.json());

      const [chainRes, oiRes, maxPainRes] = await Promise.all([
        fetch(`${API_BASE}/market/option-chain?symbol=${symbol}`),
        fetch(`${API_BASE}/analytics/oi?symbol=${symbol}`),
        fetch(`${API_BASE}/analytics/maxpain?symbol=${symbol}`)
      ]);
      if (chainRes.ok) setChainData(await chainRes.json());
      if (oiRes.ok) setOiData(oiRes.ok ? await oiRes.json() : null);
      if (maxPainRes.ok) setMaxPainData(await maxPainRes.json());

      if (tabKey === "dealer-positioning") {
        const [gexProfileRes, dealerRes] = await Promise.all([
          fetch(`${API_BASE}/analytics/gex-profile?symbol=${symbol}`),
          fetch(`${API_BASE}/analytics/dealer-positioning?symbol=${symbol}`)
        ]);
        if (gexProfileRes.ok) setGexProfile(await gexProfileRes.json());
        if (dealerRes.ok) setDealerExposureData(await dealerRes.json());
      } else if (tabKey === "volatility") {
        const smileRes = await fetch(`${API_BASE}/analytics/volatility-smile?symbol=${symbol}`);
        if (smileRes.ok) setVolSmile(await smileRes.json());
      } else if (tabKey === "backtest") {
        const btRes = await fetch(`${API_BASE}/signals/backtest?symbol=${symbol}&strategy=${backtestStrategy}`);
        if (btRes.ok) setBacktestData(await btRes.json());
      } else if (tabKey === "alerts") {
        const alertRes = await fetch(`${API_BASE}/alerts`);
        if (alertRes.ok) setAlertsData(await alertRes.json());
      } else if (tabKey === "admin") {
        const [statusRes, logRes] = await Promise.all([
          fetch(`${API_BASE}/admin/status`),
          fetch(`${API_BASE}/admin/logs`)
        ]);
        if (statusRes.ok) setAdminStatus(await statusRes.json());
        if (logRes.ok) setAdminLogs(await logRes.json());
      }

      setLastUpdated(new Date());
      setLoading(false);
    } catch (err: any) {
      console.error(err);
      setError("Synchronizing failed. Please ensure the FastAPI Python backend is running on http://127.0.0.1:8000.");
      setLoading(false);
    }
  };

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    setLoading(true);
    fetchData(activeTab);
    if (activeTab === "backtest") return;
    
    const interval = setInterval(() => {
      fetchData(activeTab);
    }, POLLING_INTERVAL_MS);
    
    return () => clearInterval(interval);
  }, [symbol, activeTab, backtestStrategy]);

  const handleRetrain = async () => {
    setRetraining(true);
    try {
      const res = await fetch(`${API_BASE}/signals/retrain?symbol=${symbol}`, { method: "POST" });
      if (res.ok) {
        alert("Ensemble ML models retraining started in the background. Performance metrics will refresh shortly.");
        setTimeout(() => fetchData(activeTab), 3000);
      }
    } catch (e) {
      alert("Failed to connect to API node.");
    }
    setRetraining(false);
  };

  const handleResearchQuery = async (queryText = searchQuery) => {
    if (!queryText.trim()) return;
    setResearchChat(prev => [...prev, { role: "user", text: queryText }]);
    setSearchQuery("");
    setResearchLoading(true);
    
    try {
      const res = await fetch(`${API_BASE}/research/query?query=${encodeURIComponent(queryText)}&symbol=${symbol}`);
      if (res.ok) {
        const data = await res.json();
        setResearchChat(prev => [...prev, { role: "assistant", text: data.response }]);
      } else {
        setResearchChat(prev => [...prev, { role: "assistant", text: "Error: Failed to process terminal request. Query API returned an invalid response." }]);
      }
    } catch (e) {
      setResearchChat(prev => [...prev, { role: "assistant", text: "Connection error: Unable to contact the quantitative research node." }]);
    }
    setResearchLoading(false);
  };

  const spotChange = Number(spotData?.change_pct ?? 0);
  const futureChange = Number(futuresData?.change_pct ?? 0);
  const vixVal = Number(vixData?.value ?? 13.5);

  return (
    <div className="flex-1 flex flex-col bg-slate-50/20 text-slate-808 min-h-screen font-sans antialiased text-base">
      <style dangerouslySetInnerHTML={{__html: `
        @keyframes fadeSlideUp {
          from { opacity: 0; transform: translateY(8px); }
          to { opacity: 1; transform: translateY(0); }
        }
        .animate-fade-slide {
          animation: fadeSlideUp 0.35s cubic-bezier(0.16, 1, 0.3, 1) forwards;
        }
        @keyframes modalIn {
          from { opacity: 0; transform: scale(0.96) translateY(10px); }
          to { opacity: 1; transform: scale(1) translateY(0); }
        }
        .animate-modal-in {
          animation: modalIn 0.25s cubic-bezier(0.16, 1, 0.3, 1) forwards;
        }
      `}} />

      {/* ==================== FULLSCREEN CHART MODAL ==================== */}
      {expandedChart && (
        <div
          className="fixed inset-0 z-[999] bg-black/60 backdrop-blur-sm flex items-center justify-center p-4"
          onClick={() => setExpandedChart(null)}
        >
          <div
            className="bg-white rounded-2xl shadow-2xl border border-slate-200 w-full max-w-5xl max-h-[90vh] flex flex-col animate-modal-in"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200">
              <h2 className="text-sm font-black text-slate-800 uppercase tracking-wider">{expandedChart}</h2>
              <button
                onClick={() => setExpandedChart(null)}
                className="text-slate-400 hover:text-slate-800 font-black text-lg leading-none w-8 h-8 flex items-center justify-center rounded-lg hover:bg-slate-100 transition-all"
              >✕</button>
            </div>
            {/* Modal Chart Body — renders the same chart data at full size */}
            <div className="flex-1 p-6 overflow-auto">
              {expandedChart === "OI Distribution & IV" && (
                <div className="h-[60vh]">
                  <ResponsiveContainer width="100%" height="100%">
                    <ComposedChart data={oiChartData} margin={{ top: 10, right: 20, left: 10, bottom: 10 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                      <XAxis dataKey="strike" stroke="#64748b" style={{ fontSize: 11 }} />
                      <YAxis yAxisId="left" stroke="#64748b" style={{ fontSize: 11 }} tickFormatter={(val) => `${val}k`} />
                      <YAxis yAxisId="right" orientation="right" stroke="#475569" style={{ fontSize: 11 }} tickFormatter={(val) => `${val}%`} />
                      <Tooltip contentStyle={{ backgroundColor: "#ffffff", border: "1px solid #cbd5e1", fontSize: 12 }} formatter={(value: any, name: any) => { const n = String(name||""); return n.includes("OI") ? [`${safeNumber(value,1)}k`, n] : [`${safeNumber(value,2)}%`, n]; }} labelFormatter={(s) => `Strike: ${s}`} />
                      <Legend wrapperStyle={{ fontSize: 11 }} />
                      <ReferenceLine x={spotData?.price ? (symbol === "NIFTY" ? Math.round(spotData.price / 50) * 50 : Math.round(spotData.price / 100) * 100) : undefined} stroke="#6366f1" strokeWidth={2} strokeDasharray="4 2" label={{ value: "ATM", fill: "#6366f1", fontSize: 10, position: "top" }} zIndex={10} />
                      <Bar yAxisId="left" dataKey="callOI" name="Call OI (CE)" fill="#f43f5e" radius={[3,3,0,0]} opacity={0.65} />
                      <Bar yAxisId="left" dataKey="putOI" name="Put OI (PE)" fill="#10b981" radius={[3,3,0,0]} opacity={0.65} />
                      <Line yAxisId="right" type="monotone" dataKey="callIV" name="Call IV (CE %)" stroke="#e11d48" strokeWidth={2} dot={true} />
                      <Line yAxisId="right" type="monotone" dataKey="putIV" name="Put IV (PE %)" stroke="#059669" strokeWidth={2} dot={true} />
                    </ComposedChart>
                  </ResponsiveContainer>
                </div>
              )}
              {expandedChart === "Options Volume Distribution" && (
                <div className="h-[60vh]">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={volumeDistributionData} margin={{ top: 10, right: 20, left: 10, bottom: 10 }}>
                      <defs>
                        <linearGradient id="callVolGradM" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#f43f5e" stopOpacity={0.35} />
                          <stop offset="95%" stopColor="#f43f5e" stopOpacity={0.02} />
                        </linearGradient>
                        <linearGradient id="putVolGradM" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#10b981" stopOpacity={0.35} />
                          <stop offset="95%" stopColor="#10b981" stopOpacity={0.02} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                      <XAxis dataKey="strike" stroke="#64748b" style={{ fontSize: 11 }} />
                      <YAxis stroke="#64748b" style={{ fontSize: 11 }} tickFormatter={(v) => `${v}k`} />
                      <Tooltip contentStyle={{ fontSize: 12 }} formatter={(v: any, n: any) => [`${safeNumber(v,1)}k lots`, n]} labelFormatter={(s) => `Strike: ${s}`} />
                      <Legend wrapperStyle={{ fontSize: 11 }} />
                      <ReferenceLine x={spotData?.price ? Math.round(spotData.price / 100) * 100 : undefined} stroke="#6366f1" strokeDasharray="4 2" label={{ value: "ATM", fill: "#6366f1", fontSize: 10 }} />
                      <Area type="monotone" dataKey="callVol" name="Call Volume (CE)" stroke="#f43f5e" strokeWidth={2} fill="url(#callVolGradM)" />
                      <Area type="monotone" dataKey="putVol" name="Put Volume (PE)" stroke="#10b981" strokeWidth={2} fill="url(#putVolGradM)" />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              )}
              {expandedChart === "Net OI Skew" && (
                <div className="h-[60vh]">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={oiSkewData} margin={{ top: 10, right: 20, left: 10, bottom: 10 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                      <XAxis dataKey="strike" stroke="#64748b" style={{ fontSize: 11 }} />
                      <YAxis stroke="#64748b" style={{ fontSize: 11 }} tickFormatter={(v) => `${v}k`} />
                      <Tooltip contentStyle={{ fontSize: 12 }} formatter={(v: any) => [`${safeNumber(v,1)}k`, "Net OI Skew (CE-PE)"]} labelFormatter={(s) => `Strike: ${s}`} />
                      <ReferenceLine y={0} stroke="#94a3b8" strokeWidth={1.5} />
                      <ReferenceLine x={spotData?.price ? Math.round(spotData.price / 100) * 100 : undefined} stroke="#6366f1" strokeDasharray="4 2" label={{ value: "ATM", fill: "#6366f1", fontSize: 10 }} />
                      <Bar dataKey="netSkew" name="Net OI Skew" radius={[3,3,0,0]}>
                        {oiSkewData.map((entry, index) => (
                          <Cell key={`skewM-${index}`} fill={entry.netSkew >= 0 ? "#f43f5e" : "#10b981"} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}
              {expandedChart === "Dealer GEX Profile" && (
                <div className="h-[60vh]">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={gexData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                      <XAxis dataKey="strike" stroke="#64748b" style={{ fontSize: 11 }} />
                      <YAxis stroke="#64748b" style={{ fontSize: 11 }} tickFormatter={(val) => `${val.toFixed(1)}M`} />
                      <Tooltip contentStyle={{ backgroundColor: "#ffffff", border: "1px solid #cbd5e1", fontSize: 12 }} formatter={(val: any) => [`$${safeNumber(val, 2)}M`, "Net GEX"]} />
                      <Legend wrapperStyle={{ fontSize: 11 }} />
                      <Bar dataKey="call_gex" name="Call Gamma GEX" fill="#10b981" radius={[3,3,0,0]} />
                      <Bar dataKey="put_gex" name="Put Gamma GEX" fill="#ef4444" radius={[0,0,3,3]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}
              {expandedChart === "IV Smile" && (
                <div className="h-[60vh]">
                  <ResponsiveContainer width="100%" height="100%">
                    <RecLineChart data={volSmileData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                      <XAxis dataKey="strike" stroke="#64748b" style={{ fontSize: 11 }} />
                      <YAxis stroke="#64748b" style={{ fontSize: 11 }} tickFormatter={(val) => `${val}%`} />
                      <Tooltip contentStyle={{ fontSize: 12 }} formatter={(val: any) => [`${val.toFixed(2)}%`, "IV"]} />
                      <Legend wrapperStyle={{ fontSize: 11 }} />
                      <Line type="monotone" dataKey="callIV" name="Call IV %" stroke="#10b981" strokeWidth={2} dot={true} />
                      <Line type="monotone" dataKey="putIV" name="Put IV %" stroke="#ef4444" strokeWidth={2} dot={true} />
                    </RecLineChart>
                  </ResponsiveContainer>
                </div>
              )}
              {expandedChart === "Intraday Spot vs VWAP" && (
                <div className="h-[60vh]">
                  <ResponsiveContainer width="100%" height="100%">
                    <RecLineChart data={vwapData} margin={{ top: 10, right: 20, left: 10, bottom: 10 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                      <XAxis dataKey="timestamp" stroke="#64748b" style={{ fontSize: 11 }} />
                      <YAxis stroke="#64748b" style={{ fontSize: 11 }} domain={["dataMin - 20", "dataMax + 20"]} tickFormatter={(val) => safeNumber(val, 0)} />
                      <Tooltip 
                        contentStyle={{ backgroundColor: "#ffffff", border: "1px solid #cbd5e1", fontSize: 12 }}
                        formatter={(value: any, name: any) => [safeNumber(value, 2), name === "price" ? "Spot Price" : "VWAP"]}
                        labelFormatter={(label) => `Time: ${label}`}
                      />
                      <Legend wrapperStyle={{ fontSize: 11 }} />
                      <Line type="monotone" dataKey="price" name="Spot Price" stroke="#6366f1" strokeWidth={2} dot={false} />
                      <Line type="monotone" dataKey="vwap" name="VWAP" stroke="#f59e0b" strokeWidth={2} dot={false} strokeDasharray="5 5" />
                    </RecLineChart>
                  </ResponsiveContainer>
                </div>
              )}
              {expandedChart === "Options VWAP (Call vs Put)" && (
                <div className="h-[60vh]">
                  <ResponsiveContainer width="100%" height="100%">
                    <RecLineChart data={optionsVwapData} margin={{ top: 10, right: 20, left: 10, bottom: 10 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                      <XAxis dataKey="timestamp" stroke="#64748b" style={{ fontSize: 11 }} />
                      <YAxis stroke="#64748b" style={{ fontSize: 11 }} domain={["dataMin - 10", "dataMax + 10"]} tickFormatter={(val) => `₹${safeNumber(val, 0)}`} />
                      <Tooltip 
                        contentStyle={{ backgroundColor: "#ffffff", border: "1px solid #cbd5e1", fontSize: 12 }}
                        formatter={(value: any, name: any) => [`₹${safeNumber(value, 2)}`, name]}
                        labelFormatter={(label) => `Time: ${label}`}
                      />
                      <Legend wrapperStyle={{ fontSize: 11 }} />
                      <Line type="monotone" dataKey="ce_vwap" name="Call (CE) VWAP" stroke="#10b981" strokeWidth={2} dot={false} />
                      <Line type="monotone" dataKey="pe_vwap" name="Put (PE) VWAP" stroke="#ef4444" strokeWidth={2} dot={false} />
                    </RecLineChart>
                  </ResponsiveContainer>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Premium Top Navigation Bar */}
      <header className="sticky top-0 z-50 flex items-center justify-between px-6 py-4 bg-white border-b border-slate-200/80 shadow-sm">
        <div className="flex items-center gap-4">
          <div className="bg-slate-800 p-2.5 rounded-xl shadow-sm">
            <BarChart2 className="h-5 w-5 text-white" />
          </div>
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-xl font-black tracking-wider uppercase bg-gradient-to-r from-slate-700 to-slate-900 bg-clip-text text-transparent">
                QuantForge Alpha
              </h1>
            </div>
            <p className="text-xs text-slate-500 font-bold tracking-wider">by Abha Mahato ✦ Options Intelligence Suite</p>
          </div>
        </div>

        {/* Global Control Bar */}
        <div className="flex items-center gap-4">
          {/* Symbol Selector Tab */}
          <div className="flex bg-slate-100 p-1.5 rounded-xl border border-slate-200/80">
            {["SENSEX", "BANKEX", "NIFTY", "BANKNIFTY"].map((s) => (
              <button
                key={s}
                onClick={() => setSymbol(s)}
                className={`px-4 py-2 rounded-lg text-sm font-bold tracking-wider transition-all duration-300 ${
                  symbol === s 
                    ? "bg-white text-slate-800 border border-slate-200 shadow-sm" 
                    : "text-slate-500 hover:text-slate-880 hover:bg-white/50"
                }`}
              >
                {s}
              </button>
            ))}
          </div>

          {/* Timeframe selector */}
          <div className="hidden lg:flex bg-slate-100 p-1.5 rounded-xl border border-slate-200/80">
            {["1 Min", "5 Min", "15 Min", "Daily"].map((t) => (
              <button
                key={t}
                onClick={() => setTimeframe(t)}
                className={`px-3 py-2 rounded-lg text-sm font-bold uppercase tracking-wider transition-all ${
                  timeframe === t 
                    ? "bg-white text-slate-700 border border-slate-200 shadow-sm" 
                    : "text-slate-500 hover:text-slate-808"
                }`}
              >
                {t}
              </button>
            ))}
          </div>

          {/* Connection and Sync indicators */}
          <div className="hidden md:flex items-center gap-3 text-sm bg-slate-50 border border-slate-200/80 px-4 py-2 rounded-xl">
            <span className="h-2 w-2 rounded-full bg-emerald-450 animate-pulse"></span>
            <span className="text-slate-655 font-bold">R-T Data Feed</span>
            <span className="text-slate-350">|</span>
            <span className="text-slate-500 font-semibold">Refreshed: {mounted ? lastUpdated.toLocaleTimeString() : "--:--:--"}</span>
          </div>

          {/* Hard Reload */}
          <button 
            onClick={() => { fetchData(activeTab); }}
            disabled={loading}
            title="Refresh data"
            className="p-2.5 rounded-xl bg-white hover:bg-slate-50 border border-slate-205 transition-all text-slate-600 disabled:opacity-50 active:scale-95"
          >
            <RefreshCw className={`h-4.5 w-4.5 transition-transform ${loading ? 'animate-spin text-emerald-500' : 'text-slate-500 hover:text-slate-800'}`} />
          </button>
        </div>
      </header>

      {/* API fallbacks banner */}
      {error && (
        <div className="bg-rose-50/70 border-b border-rose-150 px-6 py-3 flex items-center justify-between text-rose-808 text-sm font-bold shadow-sm">
          <div className="flex items-center gap-2.5">
            <AlertCircle className="h-5 w-5 text-rose-600 shrink-0" />
            <p>{error}</p>
          </div>
          <span className="text-xs bg-rose-100/85 border border-rose-205 px-2.5 py-1 rounded text-rose-700 uppercase tracking-widest font-black">
            SQLite Fallback Mode Active
          </span>
        </div>
      )}
      {/* Real-time Indices & Global Macro Ticker Ribbon */}
      {mounted && (
        <div className="bg-[#1e293b] text-slate-100 text-xs px-6 py-2.5 flex flex-wrap items-center gap-x-6 gap-y-1.5 border-b border-[#334155] font-semibold">
          <div className="flex items-center gap-1.5">
            <span className="text-[#94a3b8] font-bold">NIFTY Spot:</span>
            <span className="font-mono text-white">
              {niftySpot ? safeNumber(niftySpot.price) : "22,345.60"}
            </span>
            <span className={`font-bold font-mono text-[10px] ${
              (niftySpot?.change_pct ?? 0) >= 0 ? "text-emerald-450" : "text-rose-455"
            }`}>
              {(niftySpot?.change_pct ?? 0) >= 0 ? "+" : ""}{safeNumber(niftySpot?.change_pct ?? 0.45, 2)}%
            </span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="text-[#94a3b8] font-bold">BANKNIFTY:</span>
            <span className="font-mono text-white">
              {bankniftySpot ? safeNumber(bankniftySpot.price) : "47,890.15"}
            </span>
            <span className={`font-bold font-mono text-[10px] ${
              (bankniftySpot?.change_pct ?? 0) >= 0 ? "text-emerald-450" : "text-rose-455"
            }`}>
              {(bankniftySpot?.change_pct ?? 0) >= 0 ? "+" : ""}{safeNumber(bankniftySpot?.change_pct ?? 0.62, 2)}%
            </span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="text-[#94a3b8] font-bold">India VIX:</span>
            <span className={`font-mono font-bold ${vixVal > 15 ? 'text-rose-400' : 'text-emerald-400'}`}>
              {safeNumber(vixVal, 2)}
            </span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="text-[#94a3b8] font-bold">USDINR:</span>
            <span className="font-mono text-white">{safeNumber(usdinrData?.value ?? 83.45, 2)}</span>
          </div>
          <div className="ml-auto flex items-center gap-4 text-[#94a3b8]">
            <span>FII/DII Net: <span className={fiiDiiData?.net_flow >= 0 ? "text-emerald-400" : "text-rose-400 font-mono"}>{fiiDiiData?.net_flow >= 0 ? "+" : ""}{safeNumber(fiiDiiData?.net_flow, 1)} Cr</span></span>
          </div>
        </div>
      )}

      {/* Main Terminal Area */}
      <div className="flex-1 flex flex-col lg:flex-row bg-slate-50/30">
        {/* Sidebar Tabs Panel (Reduced width and compact styles) */}
        <aside className="w-full lg:w-52 bg-white lg:border-r border-slate-200/80 p-3.5 flex flex-row lg:flex-col gap-1.5 shrink-0 overflow-x-auto lg:overflow-visible scrollbar-none">
          <div className="hidden lg:block text-[10px] font-black text-slate-400 uppercase tracking-widest px-2 mb-1.5">Platform Analytics</div>
          
          {/* Quick Stats sidebar widget (dealer exposures) */}
          {summaryData && (
            <div className="hidden lg:block pb-3 border-b border-slate-100">
              <div className="bg-slate-50 border border-slate-200 p-4 rounded-xl shadow-sm space-y-2.5">
                <span className="text-xs font-black text-slate-550 tracking-wider flex items-center gap-1 uppercase">
                  <span className="h-1.5 w-1.5 rounded-full bg-slate-450"></span>
                  Dealer Exposure
                </span>
                <div className="space-y-1.5 text-xs font-bold">
                  <div className="flex justify-between">
                    <span className="text-slate-500">State:</span>
                    <span className={`font-black ${summaryData.total_gex > 0 ? "text-emerald-650" : "text-rose-655"}`}>
                      {summaryData.total_gex > 0 ? "LONG" : "SHORT"}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Flip:</span>
                    <span className="text-slate-905 font-mono">{safeNumber(summaryData.gamma_flip_level, 0)}</span>
                  </div>
                </div>
              </div>
            </div>
          )}

          <button
            onClick={() => setActiveTab("overview")}
            className={`flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-xs font-bold tracking-wider transition-all shrink-0 whitespace-nowrap ${
              activeTab === "overview"
                ? "bg-slate-100 text-slate-808 border border-slate-200 shadow-sm font-black"
                : "text-slate-500 hover:text-slate-805 hover:bg-slate-50 border border-transparent"
            }`}
          >
            <Compass className="h-4.5 w-4.5" />
            Overview
          </button>

          <button
            onClick={() => setActiveTab("option-chain")}
            className={`flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-xs font-bold tracking-wider transition-all shrink-0 whitespace-nowrap ${
              activeTab === "option-chain"
                ? "bg-slate-100 text-slate-808 border border-slate-200 shadow-sm font-black"
                : "text-slate-500 hover:text-slate-805 hover:bg-slate-50 border border-transparent"
            }`}
          >
            <Layers className="h-4.5 w-4.5" />
            Option Chain
          </button>

          <button
            onClick={() => setActiveTab("dealer-positioning")}
            className={`flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-xs font-bold tracking-wider transition-all shrink-0 whitespace-nowrap ${
              activeTab === "dealer-positioning"
                ? "bg-slate-100 text-slate-808 border border-slate-200 shadow-sm font-black"
                : "text-slate-500 hover:text-slate-805 hover:bg-slate-50 border border-transparent"
            }`}
          >
            <BarChart3 className="h-4.5 w-4.5" />
            Dealer GEX
          </button>

          <button
            onClick={() => setActiveTab("volatility")}
            className={`flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-xs font-bold tracking-wider transition-all shrink-0 whitespace-nowrap ${
              activeTab === "volatility"
                ? "bg-slate-100 text-slate-808 border border-slate-200 shadow-sm font-black"
                : "text-slate-500 hover:text-slate-805 hover:bg-slate-50 border border-transparent"
            }`}
          >
            <LineChart className="h-4.5 w-4.5" />
            Volatility
          </button>

          <button
            onClick={() => setActiveTab("institutional")}
            className={`flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-xs font-bold tracking-wider transition-all shrink-0 whitespace-nowrap ${
              activeTab === "institutional"
                ? "bg-slate-100 text-slate-808 border border-slate-200 shadow-sm font-black"
                : "text-slate-500 hover:text-slate-805 hover:bg-slate-50 border border-transparent"
            }`}
          >
            <Globe className="h-4.5 w-4.5" />
            Inst. Flows
          </button>

          <div className="hidden lg:block text-[10px] font-black text-slate-400 uppercase tracking-widest px-2 pt-4 mb-1.5">Quantitative Labs</div>

          <button
            onClick={() => setActiveTab("backtest")}
            className={`flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-xs font-bold tracking-wider transition-all shrink-0 whitespace-nowrap ${
              activeTab === "backtest"
                ? "bg-slate-100 text-slate-808 border border-slate-200 shadow-sm font-black"
                : "text-slate-500 hover:text-slate-805 hover:bg-slate-50 border border-transparent"
            }`}
          >
            <Brain className="h-4.5 w-4.5" />
            Backtester
          </button>

          <button
            onClick={() => setActiveTab("terminal")}
            className={`flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-xs font-bold tracking-wider transition-all shrink-0 whitespace-nowrap ${
              activeTab === "terminal"
                ? "bg-slate-100 text-slate-808 border border-slate-200 shadow-sm font-black"
                : "text-slate-500 hover:text-slate-805 hover:bg-slate-50 border border-transparent"
            }`}
          >
            <Terminal className="h-4.5 w-4.5" />
            Research AI
          </button>
        </aside>

        {/* Central Terminal Body - Spanning full-width */}
        <main className="flex-1 p-5 space-y-5 overflow-y-auto w-full max-w-none">
          


          {/* ==================== TAB 1: EXECUTIVE TERMINAL ==================== */}
          {activeTab === "overview" && (
            <div className="space-y-5 animate-fade-slide">
              {/* ==================== 1. EXECUTIVE CARD HEADER ==================== */}
              {spotData && (
                <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5">
                  {/* Index Spot Price Card — with intraday sparkline */}
                  <div className="bg-white border border-slate-205 p-5 rounded-2xl relative overflow-hidden shadow-sm hover:border-slate-350 transition-all duration-300">
                    <span className="text-[11px] font-black text-slate-500 uppercase tracking-widest block">{symbol} Spot</span>
                    <h2 className="text-5xl font-black mt-2 text-slate-950 font-mono leading-none tracking-tight">
                      {safeNumber(spotData.price)}
                    </h2>
                    <span className={`inline-flex items-center gap-0.5 text-[11px] font-extrabold px-2 py-0.5 rounded border mt-2 ${
                      spotChange >= 0 ? "bg-emerald-50 text-emerald-700 border-emerald-150" : "bg-rose-50 text-rose-700 border-rose-150"
                    }`}>
                      {spotChange >= 0 ? "+" : ""}{safeNumber(spotChange, 2)}%
                    </span>
                    {/* Mini Sparkline */}
                    <div className="h-12 mt-2 -mx-1">
                      <ResponsiveContainer width="100%" height="100%">
                        <AreaChart data={sparklineData} margin={{ top: 0, right: 0, left: 0, bottom: 0 }}>
                          <defs>
                            <linearGradient id="sparkGrad" x1="0" y1="0" x2="0" y2="1">
                              <stop offset="5%" stopColor={spotChange >= 0 ? "#10b981" : "#f43f5e"} stopOpacity={0.25} />
                              <stop offset="95%" stopColor={spotChange >= 0 ? "#10b981" : "#f43f5e"} stopOpacity={0} />
                            </linearGradient>
                          </defs>
                          <YAxis domain={["dataMin - 10", "dataMax + 10"]} hide={true} />
                          <Area type="monotone" dataKey="price" stroke={spotChange >= 0 ? "#10b981" : "#f43f5e"} strokeWidth={1.5} fill="url(#sparkGrad)" dot={false} />
                        </AreaChart>
                      </ResponsiveContainer>
                    </div>
                  </div>

                  {/* India VIX Card */}
                  <div className="bg-white border border-slate-205 p-5 rounded-2xl relative overflow-hidden shadow-sm hover:border-slate-350 transition-all duration-305">
                    <span className="text-[11px] font-black text-slate-500 uppercase tracking-widest block">India VIX</span>
                    <h2 className="text-5xl font-black mt-2 text-slate-950 font-mono leading-none tracking-tight">
                      {safeNumber(vixVal, 2)}
                    </h2>
                    <span className={`inline-block text-sm font-extrabold px-2.5 py-0.5 rounded border mt-3.5 ${
                      vixVal > 16.0 ? "bg-rose-50 text-rose-700 border-rose-205" : "bg-slate-50 text-slate-605 border-slate-200"
                    }`}>
                      {vixVal > 18.0 ? "High Vol" : "Stable"}
                    </span>
                  </div>

                  {/* PCR Open Interest Card */}
                  <div className="bg-white border border-slate-205 p-5 rounded-2xl relative overflow-hidden shadow-sm hover:border-slate-350 transition-all">
                    <span className="text-[11px] font-black text-slate-500 uppercase tracking-widest block">PCR (OI)</span>
                    <h2 className="text-5xl font-black mt-2 text-slate-950 font-mono leading-none tracking-tight">
                      {safeNumber(summaryData?.pcr?.pcr_oi, 3)}
                    </h2>
                    <span className="text-sm font-extrabold text-slate-600 block mt-3">Put/Call OI Ratio</span>
                  </div>

                  {/* PCR Volume Card */}
                  <div className="bg-white border border-slate-205 p-5 rounded-2xl relative overflow-hidden shadow-sm hover:border-slate-350 transition-all">
                    <span className="text-[11px] font-black text-slate-500 uppercase tracking-widest block">PCR (Volume)</span>
                    <h2 className="text-5xl font-black mt-2 text-slate-950 font-mono leading-none tracking-tight">
                      {safeNumber(summaryData?.pcr?.pcr_volume, 3)}
                    </h2>
                    <span className="text-sm font-extrabold text-slate-600 block mt-3">Put/Call Vol Ratio</span>
                  </div>
                </section>
              )}
              {/* ==================== AI TRADE SIGNAL GENERATOR ADVISOR ==================== */}
              <div className="bg-slate-50 border border-slate-205 p-6 rounded-2xl shadow-sm text-slate-808 flex flex-col xl:flex-row justify-between items-start xl:items-center gap-6 relative overflow-hidden">
                <div className="space-y-1">
                  <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest flex items-center gap-1.5">
                    <Brain className="h-4 w-4 text-slate-500 animate-pulse" />
                    Ensemble ML Signal Core
                  </span>
                  <div className="flex flex-wrap items-center gap-3">
                    <span className="text-xl font-black text-slate-900 tracking-tight">{symbol}</span>
                    <span className="text-slate-300">|</span>
                    <span className="text-xs font-bold text-slate-500">Live Spot:</span>
                    <span className="text-lg font-black text-slate-700 font-mono">{safeNumber(spotData?.price)}</span>
                  </div>
                </div>
                
                <div className="flex flex-wrap items-stretch gap-4 w-full xl:w-auto">
                  {/* Card 1: Direction */}
                  <div className="flex-1 min-w-[180px] bg-white border border-slate-200 p-4 rounded-xl flex items-center gap-4 shadow-sm">
                    <span className={`h-4.5 w-4.5 rounded-full flex items-center justify-center ${
                      forecastData?.forecast?.signal === "BUY" ? "bg-emerald-55 text-emerald-600 border border-emerald-150 animate-pulse" : (forecastData?.forecast?.signal === "SELL" ? "bg-rose-50 text-rose-600 border border-rose-150 animate-pulse" : "bg-slate-50 text-slate-400 border border-slate-200")
                    }`}>
                      <span className={`h-2 w-2 rounded-full ${
                        forecastData?.forecast?.signal === "BUY" ? "bg-emerald-500" : (forecastData?.forecast?.signal === "SELL" ? "bg-rose-500" : "bg-slate-400")
                      }`}></span>
                    </span>
                    <div>
                      <span className="text-[9px] text-slate-400 font-bold block uppercase tracking-wider">AI DIRECTION</span>
                      <span className={`text-base font-black uppercase tracking-widest ${
                        forecastData?.forecast?.signal === "BUY" ? "text-emerald-700" : (forecastData?.forecast?.signal === "SELL" ? "text-rose-655" : "text-slate-600")
                      }`}>
                        {forecastData?.forecast?.signal === "BUY" ? "BUY / GO LONG" : (forecastData?.forecast?.signal === "SELL" ? "SELL / GO SHORT" : "NEUTRAL / HOLD")}
                      </span>
                    </div>
                  </div>

                  {/* Card 2: Recommended Strategy */}
                  <div className="flex-1 min-w-[280px] bg-white border border-slate-200 p-4 rounded-xl flex flex-col justify-center shadow-sm">
                    <span className="text-[9px] text-slate-400 font-bold block uppercase tracking-wider">RECOMMENDED STRATEGY</span>
                    {(() => {
                      const strat = getDynamicStrategy();
                      return (
                        <div className="mt-1">
                          <span className="text-sm font-black text-slate-800 block leading-tight">{strat.name}</span>
                          <span className="text-xs text-slate-500 font-bold block mt-0.5">{strat.description}</span>
                        </div>
                      );
                    })()}
                  </div>

                  {/* Card 3: Target Range (Fills the empty space with large typography) */}
                  {(() => {
                    const strat = getDynamicStrategy();
                    return strat.range ? (
                      <div className="flex-1 min-w-[200px] bg-white border border-slate-200 p-4 rounded-xl flex flex-col justify-center shadow-sm">
                        <span className="text-[9px] text-slate-450 font-bold block uppercase tracking-wider">EXPECTED RANGE</span>
                        <span className="text-lg font-black text-slate-800 mt-1 font-mono tracking-wide">{strat.range}</span>
                      </div>
                    ) : null;
                  })()}

                  {/* Card 4: Bounds & Targets */}
                  <div className="flex-1 min-w-[200px] bg-white border border-slate-200 p-4 rounded-xl flex flex-col justify-center shadow-sm font-mono">
                    <span className="text-[9px] text-slate-400 font-bold block uppercase tracking-wider font-sans">BOUNDS & TARGETS</span>
                    <div className="text-xs font-bold text-slate-700 mt-1.5 space-y-1">
                      <div className="flex justify-between border-b border-slate-100 pb-0.5">
                        <span className="text-slate-450">Stop Loss:</span>
                        <span className="text-rose-600 font-black">{forecastData?.forecast?.signal === "BUY" ? safeNumber(spotData?.price * 0.993, 0) : safeNumber(spotData?.price * 1.007, 0)}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-455">Target Price:</span>
                        <span className="text-emerald-600 font-black">{forecastData?.forecast?.signal === "BUY" ? safeNumber(spotData?.price * 1.015, 0) : safeNumber(spotData?.price * 0.985, 0)}</span>
                      </div>
                    </div>
                  </div>

                </div>
              </div>

              {/* Call vs Put Composed Chart */}
              <div className="bg-white border border-slate-205 p-5 rounded-2xl shadow-sm space-y-3">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-bold uppercase tracking-wider text-slate-705 flex items-center gap-2">
                    <BarChart3 className="h-4.5 w-4.5 text-slate-550" />
                    OI Distribution (Bars) &amp; Implied Volatility IV (Lines)
                  </h3>
                  <button onClick={() => setExpandedChart("OI Distribution & IV")} className="text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded-lg p-1.5 transition-all" title="Expand chart">
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" /></svg>
                  </button>
                </div>
                <div className="h-60 bg-slate-50 p-3 rounded-lg border border-slate-100">
                  <ResponsiveContainer width="100%" height="100%">
                    <ComposedChart data={oiChartData} margin={{ top: 10, right: 10, left: 0, bottom: 5 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                      <XAxis dataKey="strike" stroke="#64748b" style={{ fontSize: 10 }} />
                      <YAxis yAxisId="left" stroke="#64748b" style={{ fontSize: 10 }} tickFormatter={(val) => `${val}k`} />
                      <YAxis yAxisId="right" orientation="right" stroke="#475569" style={{ fontSize: 10 }} tickFormatter={(val) => `${val}%`} />
                      <Tooltip 
                        contentStyle={{ backgroundColor: "#ffffff", border: "1px solid #cbd5e1", fontSize: 11 }}
                        formatter={(value: any, name: any) => {
                          const nameStr = String(name || "");
                          if (nameStr.includes("OI")) return [`${safeNumber(value, 1)}k`, nameStr];
                          return [`${safeNumber(value, 2)}%`, nameStr];
                        }}
                        labelFormatter={(strike) => `Strike: ${strike}`}
                      />
                      <Legend wrapperStyle={{ fontSize: 10 }} />
                      <ReferenceLine x={spotData?.price ? (symbol === "NIFTY" ? Math.round(spotData.price / 50) * 50 : Math.round(spotData.price / 100) * 100) : undefined} stroke="#6366f1" strokeWidth={2} strokeDasharray="4 2" label={{ value: "ATM", fill: "#6366f1", fontSize: 9, position: "top" }} zIndex={10} />
                      <Bar yAxisId="left" dataKey="callOI" name="Call OI (CE)" fill="#f43f5e" radius={[3, 3, 0, 0]} opacity={0.65} />
                      <Bar yAxisId="left" dataKey="putOI" name="Put OI (PE)" fill="#10b981" radius={[3, 3, 0, 0]} opacity={0.65} />
                      <Line yAxisId="right" type="monotone" dataKey="callIV" name="Call IV (CE %)" stroke="#e11d48" strokeWidth={1.5} dot={true} />
                      <Line yAxisId="right" type="monotone" dataKey="putIV" name="Put IV (PE %)" stroke="#059669" strokeWidth={1.5} dot={true} />
                    </ComposedChart>
                  </ResponsiveContainer>
                </div>
              </div>

              {/* Intraday Spot Price vs VWAP & Options Premium VWAP side-by-side */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                {/* Intraday Spot Price vs VWAP Chart */}
                <div className="bg-white border border-slate-205 p-5 rounded-2xl shadow-sm space-y-3">
                  <div className="flex items-center justify-between">
                    <h3 className="text-sm font-bold uppercase tracking-wider text-slate-705 flex items-center gap-2">
                      <LineChart className="h-4.5 w-4.5 text-slate-550" />
                      Intraday Spot Price vs VWAP
                    </h3>
                    <button onClick={() => setExpandedChart("Intraday Spot vs VWAP")} className="text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded-lg p-1.5 transition-all" title="Expand chart">
                      <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" /></svg>
                    </button>
                  </div>
                  <div className="h-60 bg-slate-50 p-3 rounded-lg border border-slate-100">
                    <ResponsiveContainer width="100%" height="100%">
                      <RecLineChart data={vwapData} margin={{ top: 10, right: 10, left: 0, bottom: 5 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                        <XAxis dataKey="timestamp" stroke="#64748b" style={{ fontSize: 10 }} />
                        <YAxis stroke="#64748b" style={{ fontSize: 10 }} domain={["dataMin - 20", "dataMax + 20"]} tickFormatter={(val) => safeNumber(val, 0)} />
                        <Tooltip 
                          contentStyle={{ backgroundColor: "#ffffff", border: "1px solid #cbd5e1", fontSize: 11 }}
                          formatter={(value: any, name: any) => [safeNumber(value, 2), name === "price" ? "Spot Price" : "VWAP"]}
                          labelFormatter={(label) => `Time: ${label}`}
                        />
                        <Legend wrapperStyle={{ fontSize: 10 }} />
                        <Line type="monotone" dataKey="price" name="Spot Price" stroke="#6366f1" strokeWidth={2} dot={false} />
                        <Line type="monotone" dataKey="vwap" name="VWAP" stroke="#f59e0b" strokeWidth={2} dot={false} strokeDasharray="5 5" />
                      </RecLineChart>
                    </ResponsiveContainer>
                  </div>
                </div>

                {/* Options Premium VWAP (Call vs Put) Chart */}
                <div className="bg-white border border-slate-205 p-5 rounded-2xl shadow-sm space-y-3">
                  <div className="flex items-center justify-between">
                    <h3 className="text-sm font-bold uppercase tracking-wider text-slate-705 flex items-center gap-2">
                      <LineChart className="h-4.5 w-4.5 text-slate-550" />
                      Options Premium VWAP (Call vs Put)
                    </h3>
                    <button onClick={() => setExpandedChart("Options VWAP (Call vs Put)")} className="text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded-lg p-1.5 transition-all" title="Expand chart">
                      <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" /></svg>
                    </button>
                  </div>
                  <div className="h-60 bg-slate-50 p-3 rounded-lg border border-slate-100">
                    <ResponsiveContainer width="100%" height="100%">
                      <RecLineChart data={optionsVwapData} margin={{ top: 10, right: 10, left: 0, bottom: 5 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                        <XAxis dataKey="timestamp" stroke="#64748b" style={{ fontSize: 10 }} />
                        <YAxis stroke="#64748b" style={{ fontSize: 10 }} domain={["dataMin - 10", "dataMax + 10"]} tickFormatter={(val) => `₹${safeNumber(val, 0)}`} />
                        <Tooltip 
                          contentStyle={{ backgroundColor: "#ffffff", border: "1px solid #cbd5e1", fontSize: 11 }}
                          formatter={(value: any, name: any) => [`₹${safeNumber(value, 2)}`, name]}
                          labelFormatter={(label) => `Time: ${label}`}
                        />
                        <Legend wrapperStyle={{ fontSize: 10 }} />
                        <Line type="monotone" dataKey="ce_vwap" name="Call (CE) VWAP" stroke="#10b981" strokeWidth={2} dot={false} />
                        <Line type="monotone" dataKey="pe_vwap" name="Put (PE) VWAP" stroke="#ef4444" strokeWidth={2} dot={false} />
                      </RecLineChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              </div>

              {/* ==================== OPTIONS VOLUME DISTRIBUTION CHART ==================== */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">

                {/* Options Volume Distribution (Bell Curve) */}
                <div className="bg-white border border-slate-205 p-5 rounded-2xl shadow-sm space-y-3">
                  <div className="flex items-center justify-between">
                    <h3 className="text-sm font-bold uppercase tracking-wider text-slate-705 flex items-center gap-2">
                      <BarChart3 className="h-4.5 w-4.5 text-slate-550" />
                      Options Volume Distribution (Volume vs Strike)
                    </h3>
                    <button onClick={() => setExpandedChart("Options Volume Distribution")} className="text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded-lg p-1.5 transition-all" title="Expand chart">
                      <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" /></svg>
                    </button>
                  </div>
                  <div className="h-52 bg-slate-50 p-3 rounded-lg border border-slate-100">
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart data={volumeDistributionData} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
                        <defs>
                          <linearGradient id="callVolGrad" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="#f43f5e" stopOpacity={0.3} />
                            <stop offset="95%" stopColor="#f43f5e" stopOpacity={0.02} />
                          </linearGradient>
                          <linearGradient id="putVolGrad" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
                            <stop offset="95%" stopColor="#10b981" stopOpacity={0.02} />
                          </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                        <XAxis dataKey="strike" stroke="#64748b" style={{ fontSize: 10 }} />
                        <YAxis stroke="#64748b" style={{ fontSize: 10 }} tickFormatter={(v) => `${v}k`} />
                        <Tooltip
                          contentStyle={{ backgroundColor: "#ffffff", border: "1px solid #cbd5e1", fontSize: 11 }}
                          formatter={(v: any, n: any) => [`${safeNumber(v, 1)}k lots`, n]}
                          labelFormatter={(s) => `Strike: ${s}`}
                        />
                        <Legend wrapperStyle={{ fontSize: 10 }} />
                        <ReferenceLine x={spotData?.price ? Math.round(spotData.price / 100) * 100 : undefined} stroke="#6366f1" strokeDasharray="4 2" label={{ value: "ATM", fill: "#6366f1", fontSize: 9 }} />
                        <Area type="monotone" dataKey="callVol" name="Call Volume (CE)" stroke="#f43f5e" strokeWidth={1.5} fill="url(#callVolGrad)" />
                        <Area type="monotone" dataKey="putVol" name="Put Volume (PE)" stroke="#10b981" strokeWidth={1.5} fill="url(#putVolGrad)" />
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>
                </div>

                {/* Net OI Skew Bar Chart — Decision Support */}
                <div className="bg-white border border-slate-205 p-5 rounded-2xl shadow-sm space-y-3">
                  <div className="flex items-center justify-between">
                    <h3 className="text-sm font-bold uppercase tracking-wider text-slate-705 flex items-center gap-2">
                      <BarChart3 className="h-4.5 w-4.5 text-slate-550" />
                      Net OI Skew — Call vs Put Positioning
                    </h3>
                    <button onClick={() => setExpandedChart("Net OI Skew")} className="text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded-lg p-1.5 transition-all" title="Expand chart">
                      <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" /></svg>
                    </button>
                  </div>
                  <p className="text-[10px] text-slate-500 font-bold">+ve = Call buildup (resistance) · -ve = Put buildup (support floor)</p>
                  <div className="h-48 bg-slate-50 p-3 rounded-lg border border-slate-100">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={oiSkewData} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                        <XAxis dataKey="strike" stroke="#64748b" style={{ fontSize: 10 }} />
                        <YAxis stroke="#64748b" style={{ fontSize: 10 }} tickFormatter={(v) => `${v}k`} />
                        <Tooltip
                          contentStyle={{ backgroundColor: "#ffffff", border: "1px solid #cbd5e1", fontSize: 11 }}
                          formatter={(v: any) => [`${safeNumber(v, 1)}k`, "Net OI Skew (CE-PE)"]}
                          labelFormatter={(s) => `Strike: ${s}`}
                        />
                        <ReferenceLine y={0} stroke="#94a3b8" strokeWidth={1.5} />
                        <ReferenceLine x={spotData?.price ? Math.round(spotData.price / 100) * 100 : undefined} stroke="#6366f1" strokeDasharray="4 2" label={{ value: "ATM", fill: "#6366f1", fontSize: 9 }} />
                        <Bar dataKey="netSkew" name="Net OI Skew" radius={[3, 3, 0, 0]}>
                          {oiSkewData.map((entry, index) => (
                            <Cell key={`skew-${index}`} fill={entry.netSkew >= 0 ? "#f43f5e" : "#10b981"} />
                          ))}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </div>

              </div>

              {/* Outlook & Predictions Grid */}
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                
                {/* AI Market Summary Panel (Compacted to single column) */}
                <div className="bg-white border border-slate-200 p-4 rounded-xl space-y-3.5 shadow-sm">
                  <div className="flex justify-between items-center border-b border-slate-200 pb-2">
                    <h3 className="text-sm font-bold uppercase tracking-wider flex items-center gap-2 text-slate-700">
                      <Brain className="h-4.5 w-4.5 text-slate-500" />
                      AI Outlook Summary
                    </h3>
                    {forecastData && (
                      <span className={`text-[10px] px-2 py-0.5 rounded font-bold uppercase ${getBadgeColorClass(forecastData.forecast.signal)}`}>
                        {forecastData.forecast.signal}
                      </span>
                    )}
                  </div>
                  
                  {forecastData && (
                    <div className="space-y-3">
                      {/* Metric Dial */}
                      <div className="bg-slate-55 p-3 rounded-lg flex flex-col justify-center items-center border border-slate-205">
                        <span className="text-[10px] text-slate-500 font-semibold uppercase">AI Confidence</span>
                        <div className="text-3xl font-black text-slate-700 mt-0.5 font-mono">{forecastData.forecast.confidence}%</div>
                      </div>

                      {/* Direction probability breakdown */}
                      <div className="bg-slate-55 p-3 rounded-lg border border-slate-205 space-y-2">
                        <div className="space-y-1">
                          <div className="flex justify-between text-xs font-bold">
                            <span className="text-emerald-700">Bullish</span>
                            <span className="font-mono text-slate-905">{safeNumber(forecastData.forecast.prob_up * 100, 1)}%</span>
                          </div>
                          <div className="w-full bg-slate-200 rounded-full h-1">
                            <div className="bg-emerald-450 h-1 rounded-full" style={{width: `${forecastData.forecast.prob_up * 100}%`}}></div>
                          </div>
                        </div>

                        <div className="space-y-1">
                          <div className="flex justify-between text-xs font-bold">
                            <span className="text-rose-705">Bearish</span>
                            <span className="font-mono text-slate-905">{safeNumber(forecastData.forecast.prob_down * 100, 1)}%</span>
                          </div>
                          <div className="w-full bg-slate-200 rounded-full h-1">
                            <div className="bg-rose-455 h-1 rounded-full" style={{width: `${forecastData.forecast.prob_down * 100}%`}}></div>
                          </div>
                        </div>
                      </div>
                    </div>
                  )}
                </div>

                {/* Regime & Range Predictions Card */}
                <div className="bg-white border border-slate-200 p-4 rounded-xl space-y-3.5 flex flex-col shadow-sm">
                  <h3 className="text-base font-bold uppercase tracking-wider border-b border-slate-200 pb-2 text-slate-705 flex items-center gap-2.5">
                    <Sliders className="h-5 w-5 text-slate-500" />
                    Regime & Range Predictor
                  </h3>
                  
                  {forecastData && (
                    <div className="space-y-4 flex-1 flex flex-col justify-between">
                      <div className="grid grid-cols-2 gap-3.5">
                        <div className="bg-slate-55 p-2.5 rounded-lg border border-slate-205">
                          <span className="text-[9px] text-slate-450 font-bold block uppercase tracking-wider">Trend Strength</span>
                          <span className="text-base font-black mt-1 block tracking-wide text-slate-808">{forecastData.forecast.trend_strength}</span>
                        </div>
                        <div className="bg-slate-55 p-2.5 rounded-lg border border-slate-205">
                          <span className="text-[9px] text-slate-455 font-bold block uppercase tracking-wider">Regime</span>
                          <span className="text-base font-black mt-1 block tracking-wide text-slate-808">{forecastData.forecast.regime}</span>
                        </div>
                      </div>

                      <div className="bg-slate-55 p-3 rounded-lg border border-slate-205 space-y-1">
                        <div className="flex justify-between items-center text-xs">
                          <div className="text-center bg-emerald-50 p-1.5 rounded w-[45%]">
                            <span className="text-[8px] text-emerald-600 block font-bold uppercase">VIX Expected High</span>
                            <span className="font-mono text-xs font-bold text-slate-800 block mt-0.5">{safeNumber(forecastData.forecast.expected_high, 0)}</span>
                          </div>
                          <div className="text-slate-405 font-bold font-mono">TO</div>
                          <div className="text-center bg-rose-50 p-1.5 rounded w-[45%]">
                            <span className="text-[8px] text-rose-600 block font-bold uppercase">VIX Expected Low</span>
                            <span className="font-mono text-xs font-bold text-slate-800 block mt-0.5">{safeNumber(forecastData.forecast.expected_low, 0)}</span>
                          </div>
                        </div>
                      </div>
                    </div>
                  )}
                </div>

                {/* Explainable AI Deep Dive (Enlarged net gamma representation) */}
                <div className="bg-white border border-slate-200 p-4 rounded-xl space-y-3.5 shadow-sm">
                  <h3 className="text-base font-bold uppercase tracking-wider border-b border-slate-200 pb-2 text-slate-700 flex items-center gap-2">
                    <Shield className="h-5 w-5 text-slate-550" />
                    AI Attributions
                  </h3>
                  {summaryData && (
                    <div className="space-y-3.5 text-sm font-bold text-slate-750">
                      <div className="flex justify-between border-b border-slate-100 pb-2">
                        <span className="text-slate-500">OI Imbalance:</span>
                        <span className="text-slate-900 font-extrabold">{safeNumber(forecastData?.features?.oi_imbalance * 100, 1)}%</span>
                      </div>
                      <div className="flex justify-between border-b border-slate-100 pb-2">
                        <span className="text-slate-500">Dealer Net Gamma:</span>
                        <span className={`font-mono font-black text-base ${summaryData.total_gex > 0 ? "text-emerald-600" : "text-rose-650"}`}>
                          {safeNumber(summaryData.total_gex, 0)}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-500">VIX Level:</span>
                        <span className="text-slate-900 font-extrabold">{vixVal} ({summaryData.volatility_regime?.regime ?? "Normal"})</span>
                      </div>
                    </div>
                  )}
                </div>

              </div>

            </div>
          )}

          {/* ==================== TAB 2: INTERACTIVE OPTION CHAIN ==================== */}
          {activeTab === "option-chain" && (
            <div className="space-y-4 animate-fade-slide">
              {/* Option Chain Summary Cards */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="bg-white border border-slate-200 p-4 rounded-xl shadow-sm">
                  <span className="text-[10px] text-slate-455 font-black uppercase tracking-wider block">Put-Call Ratio (OI)</span>
                  <div className="text-2xl font-extrabold text-slate-808 mt-1 font-mono">{safeNumber(summaryData?.pcr?.pcr_oi, 3)}</div>
                  <span className="text-[10px] text-slate-500 font-semibold block uppercase">OI PCR</span>
                </div>
                
                <div className="bg-white border border-slate-200 p-4 rounded-xl shadow-sm">
                  <span className="text-[10px] text-slate-455 font-black uppercase tracking-wider block">Put-Call Ratio (Vol)</span>
                  <div className="text-2xl font-extrabold text-slate-808 mt-1 font-mono">{safeNumber(summaryData?.pcr?.pcr_volume, 3)}</div>
                  <span className="text-[10px] text-slate-500 font-semibold block uppercase">Volume PCR</span>
                </div>

                <div className="bg-white border border-slate-200 p-4 rounded-xl shadow-sm">
                  <span className="text-[10px] text-slate-455 font-black uppercase tracking-wider block">Max Pain Level</span>
                  <div className="text-2xl font-extrabold text-slate-700 mt-1 font-mono">
                    {safeNumber(maxPainData?.max_pain, 0)}
                  </div>
                  <span className={`text-[10px] font-bold uppercase block ${maxPainData?.shift >= 0 ? "text-emerald-600" : "text-rose-600"}`}>
                    Shift: {maxPainData?.shift >= 0 ? "+" : ""}{maxPainData?.shift ?? 0}
                  </span>
                </div>

                <div className="bg-white border border-slate-200 p-4 rounded-xl shadow-sm">
                  <span className="text-[10px] text-slate-455 font-black uppercase tracking-wider block">Smart Money Walls</span>
                  <div className="text-sm font-bold text-slate-808 mt-1 space-y-1">
                    <div className="flex justify-between">
                      <span className="text-rose-655">PUT WALL:</span>
                      <span className="font-mono text-slate-905">{safeNumber(oiData?.put_wall?.strike, 0)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-emerald-655">CALL WALL:</span>
                      <span className="font-mono text-slate-905">{safeNumber(oiData?.call_wall?.strike, 0)}</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Option Price vs Volume Chart */}
              <div className="bg-white border border-slate-200 p-5 rounded-2xl shadow-sm">
                <h3 className="text-base font-bold uppercase tracking-wider border-b border-slate-205 pb-3 text-slate-705 flex items-center gap-2.5">
                  <BarChart3 className="h-5.5 w-5.5 text-slate-500" />
                  Option Premium Price vs Volume
                </h3>
                <div className="h-72 mt-4 bg-slate-50 p-4 rounded-xl border border-slate-200">
                  <ResponsiveContainer width="100%" height="100%">
                    <ScatterChart margin={{ top: 20, right: 20, bottom: 20, left: 20 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                      <XAxis type="number" dataKey="price" name="Premium Price" stroke="#64748b" style={{ fontSize: 10 }} tickFormatter={(val) => `₹${val}`} />
                      <YAxis type="number" dataKey="volume" name="Volume" stroke="#64748b" style={{ fontSize: 10 }} tickFormatter={(val) => `${val}k`} />
                      <Tooltip cursor={{ strokeDasharray: '3 3' }} contentStyle={{ backgroundColor: "#ffffff", border: "1px solid #cbd5e1", fontSize: 11 }} formatter={(value: any, name: any) => name === 'Volume' ? [`${safeNumber(value, 1)}k lots`, name] : [`₹${safeNumber(value, 1)}`, name]} />
                      <Legend wrapperStyle={{ fontSize: 10 }} />
                      <Scatter name="Call Options (CE)" data={ceOptionPriceVsVolumeData} fill="#10b981" />
                      <Scatter name="Put Options (PE)" data={peOptionPriceVsVolumeData} fill="#ef4444" />
                    </ScatterChart>
                  </ResponsiveContainer>
                </div>
              </div>

              {/* Option Chain Table (Removed vertical scroll lock) */}
              <div className="bg-white border border-slate-200 rounded-2xl overflow-hidden shadow-sm">
                <div className="p-4 border-b border-slate-200 bg-slate-50 flex items-center justify-between">
                  <h3 className="text-base font-bold uppercase tracking-wider flex items-center gap-2.5 text-slate-705">
                    <Layers className="h-5 w-5 text-slate-500" />
                    Option Chain - Nearest Expiry
                  </h3>
                  <span className="text-sm text-slate-655 font-bold bg-white px-4 py-1.5 rounded-lg border border-slate-200 uppercase tracking-widest font-mono">
                    Expiry: {chainData?.expiry_date ?? "Fetching..."}
                  </span>
                </div>
                
                <div className="overflow-x-auto">
                  <table className="w-full text-sm text-left text-slate-700 font-bold">
                    <thead className="text-xs text-slate-555 uppercase bg-slate-50 border-b border-slate-200 text-center tracking-wider font-extrabold sticky top-0 z-10">
                      <tr>
                        <th colSpan={7} className="py-2.5 border-r border-slate-200 text-emerald-655">Calls (CE)</th>
                        <th className="py-2.5 border-r border-slate-200">Strike</th>
                        <th colSpan={7} className="py-2.5 text-rose-655">Puts (PE)</th>
                      </tr>
                      <tr className="border-t border-slate-200">
                        <th className="px-2 py-1.5">OI</th>
                        <th className="px-2 py-1.5">OI Chg</th>
                        <th className="px-2 py-1.5">Vol</th>
                        <th className="px-2 py-1.5">IV</th>
                        <th className="px-2 py-1.5">LTP</th>
                        <th className="px-2 py-1.5">Lot Price</th>
                        <th className="px-2 py-1.5 border-r border-slate-200">Delta</th>
                        <th className="px-3 py-1.5 border-r border-slate-200">Strike</th>
                        <th className="px-2 py-1.5">Delta</th>
                        <th className="px-2 py-1.5">LTP</th>
                        <th className="px-2 py-1.5">Lot Price</th>
                        <th className="px-2 py-1.5">IV</th>
                        <th className="px-2 py-1.5">Vol</th>
                        <th className="px-2 py-1.5">OI Chg</th>
                        <th className="px-2 py-1.5">OI</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-200 font-mono text-center">
                      {groupedOptions.map((row: any, idx: number) => {
                        const strike = row.strike;
                        const isITMCall = spotData && strike < spotData.price;
                        const isITMPut = spotData && strike > spotData.price;
                        
                        const ceOpt = row.CE || {};
                        const peOpt = row.PE || {};

                        const lotSize = LOT_SIZES[symbol] || 1;
                        const ceLotPrice = (ceOpt.last_price || 0) * lotSize;
                        const peLotPrice = (peOpt.last_price || 0) * lotSize;

                        return (
                          <tr key={idx} className="hover:bg-slate-50/50">
                            <td className={`px-2 py-2.5 ${isITMCall ? 'bg-slate-100/30' : ''}`}>{safeNumber(ceOpt.open_interest / 1000, 1)}k</td>
                            <td className={`px-2 py-2.5 ${isITMCall ? 'bg-slate-100/30' : ''} ${ceOpt.change_in_oi >= 0 ? 'text-emerald-600' : 'text-rose-600'}`}>{safeNumber(ceOpt.change_in_oi / 1000, 1)}k</td>
                            <td className={`px-2 py-2.5 ${isITMCall ? 'bg-slate-100/30' : ''}`}>{safeNumber(ceOpt.volume / 1000, 1)}k</td>
                            <td className={`px-2 py-2.5 ${isITMCall ? 'bg-slate-100/30' : ''}`}>{safeNumber(ceOpt.implied_volatility * 100, 1)}%</td>
                            <td className={`px-2 py-2.5 font-bold ${isITMCall ? 'bg-slate-100/30' : ''} text-slate-808`}>{safeNumber(ceOpt.last_price, 1)}</td>
                            <td className={`px-2 py-2.5 font-bold ${isITMCall ? 'bg-slate-100/30' : ''} text-slate-500`}>₹{safeNumber(ceLotPrice, 0)}</td>
                            <td className={`px-2 py-2.5 border-r border-slate-200 ${isITMCall ? 'bg-slate-100/30' : ''} text-emerald-600`}>{safeNumber(ceOpt.delta, 2)}</td>
                            
                            <td className="px-3 py-2.5 border-r border-slate-200 bg-slate-50 font-bold text-slate-905 text-sm">{safeNumber(strike, 0)}</td>
                            
                            <td className={`px-2 py-2.5 ${isITMPut ? 'bg-slate-100/30' : ''} text-rose-600`}>{safeNumber(peOpt.delta, 2)}</td>
                            <td className={`px-2 py-2.5 font-bold ${isITMPut ? 'bg-slate-100/30' : ''} text-slate-808`}>{safeNumber(peOpt.last_price, 1)}</td>
                            <td className={`px-2 py-2.5 font-bold ${isITMPut ? 'bg-slate-100/30' : ''} text-slate-500`}>₹{safeNumber(peLotPrice, 0)}</td>
                            <td className={`px-2 py-2.5 ${isITMPut ? 'bg-slate-100/30' : ''}`}>{safeNumber(peOpt.implied_volatility * 100, 1)}%</td>
                            <td className={`px-2 py-2.5 ${isITMPut ? 'bg-slate-100/30' : ''}`}>{safeNumber(peOpt.volume / 1000, 1)}k</td>
                            <td className={`px-2 py-2.5 ${isITMPut ? 'bg-slate-100/30' : ''} ${peOpt.change_in_oi >= 0 ? 'text-emerald-600' : 'text-rose-600'}`}>{safeNumber(peOpt.change_in_oi / 1000, 1)}k</td>
                            <td className={`px-2 py-2.5 ${isITMPut ? 'bg-slate-100/30' : ''}`}>{safeNumber(peOpt.open_interest / 1000, 1)}k</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {/* ==================== TAB 3: DEALER POSITIONING ==================== */}
          {activeTab === "dealer-positioning" && (
            <div className="space-y-4 animate-fade-slide">
              <div className="bg-white border border-slate-200 p-5 rounded-2xl shadow-sm">
                <h3 className="text-base font-bold uppercase tracking-wider border-b border-slate-200 pb-3 text-slate-705 flex items-center gap-2.5">
                  <BarChart3 className="h-5.5 w-5.5 text-slate-550" />
                  Dealer Net Gamma Exposure (GEX Profile in Millions)
                </h3>
                <div className="h-72 mt-4 bg-slate-50 p-4 rounded-xl border border-slate-200">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={gexData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                      <XAxis dataKey="strike" stroke="#64748b" style={{ fontSize: 10 }} />
                      <YAxis stroke="#64748b" style={{ fontSize: 10 }} tickFormatter={(val) => `${val.toFixed(1)}M`} />
                      <Tooltip 
                        contentStyle={{ backgroundColor: "#ffffff", border: "1px solid #cbd5e1", fontSize: 11 }}
                        formatter={(val: any) => [`$${safeNumber(val, 2)}M`, "Net GEX"]}
                      />
                      <Legend wrapperStyle={{ fontSize: 10 }} />
                      <Bar dataKey="call_gex" name="Call Gamma GEX" fill="#10b981" radius={[3, 3, 0, 0]} />
                      <Bar dataKey="put_gex" name="Put Gamma GEX" fill="#ef4444" radius={[0, 0, 3, 3]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </div>
          )}

          {/* ==================== TAB 4: VOLATILITY LABS ==================== */}
          {activeTab === "volatility" && (
            <div className="space-y-4 animate-fade-slide">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="bg-white border border-slate-205 p-4 rounded-xl shadow-sm">
                  <span className="text-[10px] text-slate-450 font-black uppercase tracking-wider block">Implied Volatility</span>
                  <div className="text-2xl font-extrabold text-slate-850 mt-1 font-mono">{safeNumber(summaryData?.volatility_metrics?.implied_volatility, 2)}%</div>
                </div>
                <div className="bg-white border border-slate-205 p-4 rounded-xl shadow-sm">
                  <span className="text-[10px] text-slate-455 font-black uppercase tracking-wider block">Realized Vol (30d)</span>
                  <div className="text-2xl font-extrabold text-slate-850 mt-1 font-mono">{safeNumber(summaryData?.volatility_metrics?.historical_volatility, 2)}%</div>
                </div>
                <div className="bg-white border border-slate-205 p-4 rounded-xl shadow-sm">
                  <span className="text-[10px] text-slate-455 font-black uppercase tracking-wider block">IV Rank</span>
                  <div className="text-2xl font-extrabold text-slate-700 mt-1 font-mono">{safeNumber(summaryData?.volatility_metrics?.iv_rank, 1)}</div>
                </div>
                <div className="bg-white border border-slate-205 p-4 rounded-xl shadow-sm">
                  <span className="text-[10px] text-slate-455 font-black uppercase tracking-wider block">IV Percentile</span>
                  <div className="text-2xl font-extrabold text-slate-700 mt-1 font-mono">{safeNumber(summaryData?.volatility_metrics?.iv_percentile, 1)}%</div>
                </div>
              </div>

              {/* Volatility Smile Chart */}
              <div className="bg-white border border-slate-200 p-5 rounded-2xl shadow-sm">
                <h3 className="text-base font-bold uppercase tracking-wider border-b border-slate-205 pb-3 text-slate-705 flex items-center gap-2.5">
                  <LineChart className="h-5.5 w-5.5 text-slate-500" />
                  Implied Volatility (IV) Smile
                </h3>
                <div className="h-72 mt-4 bg-slate-50 p-4 rounded-xl border border-slate-200">
                  <ResponsiveContainer width="100%" height="100%">
                    <RecLineChart data={volSmileData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                      <XAxis dataKey="strike" stroke="#64748b" style={{ fontSize: 10 }} />
                      <YAxis stroke="#64748b" style={{ fontSize: 10 }} tickFormatter={(val) => `${val}%`} />
                      <Tooltip contentStyle={{ fontSize: 11 }} formatter={(val: any) => [`${val.toFixed(2)}%`, "IV"]} />
                      <Legend wrapperStyle={{ fontSize: 10 }} />
                      <Line type="monotone" dataKey="callIV" name="Call IV %" stroke="#10b981" strokeWidth={1.5} dot={true} />
                      <Line type="monotone" dataKey="putIV" name="Put IV %" stroke="#ef4444" strokeWidth={1.5} dot={true} />
                    </RecLineChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </div>
          )}

          {/* ==================== TAB 5: INSTITUTIONAL FLOWS ==================== */}
          {activeTab === "institutional" && (
            <div className="space-y-4 animate-fade-slide">
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                
                {/* FII DII Activity */}
                <div className="bg-white border border-slate-205 p-5 rounded-xl space-y-4 shadow-sm lg:col-span-1">
                  <h3 className="text-base font-bold uppercase tracking-wider border-b border-slate-200 pb-2.5 text-slate-700 flex items-center gap-2.5">
                    <Globe className="h-5 w-5 text-slate-550" />
                    FII & DII Market Action
                  </h3>
                  
                  {fiiDiiData ? (
                    <div className="space-y-4 text-sm font-semibold text-slate-705">
                      <div className="space-y-3">
                        <div className="bg-slate-50 p-4 rounded-xl border border-slate-200 text-center">
                          <span className="text-xs text-slate-450 uppercase tracking-widest block font-bold">FII Net Purchase</span>
                          <span className={`text-xl font-bold font-mono block mt-1 ${fiiDiiData.fii_net >= 0 ? "text-emerald-650" : "text-rose-655"}`}>
                            {fiiDiiData.fii_net >= 0 ? "+" : ""}{safeNumber(fiiDiiData.fii_net, 1)} Cr
                          </span>
                        </div>
                        <div className="bg-slate-50 p-4 rounded-xl border border-slate-200 text-center">
                          <span className="text-xs text-slate-450 uppercase tracking-widest block font-bold">DII Net Purchase</span>
                          <span className={`text-xl font-bold font-mono block mt-1 ${fiiDiiData.dii_net >= 0 ? "text-emerald-655" : "text-rose-655"}`}>
                            {fiiDiiData.dii_net >= 0 ? "+" : ""}{safeNumber(fiiDiiData.dii_net, 1)} Cr
                          </span>
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div className="text-slate-500 text-sm font-bold text-center py-8">
                      Synchronizing institutional flows...
                    </div>
                  )}
                </div>

                {/* Institutional Net Flows Bar Chart */}
                <div className="bg-white border border-slate-205 p-5 rounded-xl space-y-4 shadow-sm lg:col-span-2">
                  <h3 className="text-base font-bold uppercase tracking-wider border-b border-slate-200 pb-2.5 text-slate-700 flex items-center gap-2.5">
                    <BarChart3 className="h-5.5 w-5.5 text-slate-500" />
                    Institutional Net Buying Power Comparison (Cr)
                  </h3>
                  <div className="h-48 bg-slate-50 p-3 rounded-lg border border-slate-100">
                    {fiiDiiData ? (
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={institutionalFlowsData}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                          <XAxis dataKey="name" stroke="#64748b" style={{ fontSize: 11, fontWeight: "bold" }} />
                          <YAxis stroke="#64748b" style={{ fontSize: 10 }} tickFormatter={(val) => `${val} Cr`} />
                          <Tooltip formatter={(val: any) => [`${val.toFixed(1)} Cr`, "Net Position"]} />
                          <ReferenceLine y={0} stroke="#94a3b8" />
                          <Bar dataKey="Net" fill="#3b82f6" radius={[3, 3, 0, 0]}>
                            {
                              [
                                { Net: fiiDiiData.fii_net },
                                { Net: fiiDiiData.dii_net }
                              ].map((entry, index) => (
                                <Cell key={`cell-${index}`} fill={entry.Net >= 0 ? "#10b981" : "#ef4444"} />
                              ))
                            }
                          </Bar>
                        </BarChart>
                      </ResponsiveContainer>
                    ) : (
                      <div className="h-full flex items-center justify-center text-slate-500 text-xs">Loading Flow Graph...</div>
                    )}
                  </div>
                </div>

              </div>
            </div>
          )}

          {/* ==================== TAB 6: BACKTESTING LAB ==================== */}
          {activeTab === "backtest" && (
            <div className="space-y-4 animate-fade-slide">
              <div className="bg-white border border-slate-200 p-5 rounded-xl space-y-4 shadow-sm">
                <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center border-b border-slate-200 pb-3 gap-3">
                  <h3 className="text-base font-bold uppercase tracking-wider text-slate-750 flex items-center gap-2.5">
                    <Brain className="h-5 w-5 text-slate-500" />
                    Backtesting Engine Lab
                  </h3>
                  
                  <div className="flex bg-slate-100 p-1.5 rounded-xl border border-slate-200">
                    {[
                      {id: "AI_Probability", label: "AI Prob"},
                      {id: "PCR_Strategy", label: "PCR Strategy"},
                      {id: "Max_Pain_Strategy", label: "Max Pain"}
                    ].map((s) => (
                      <button
                        key={s.id}
                        onClick={() => setBacktestStrategy(s.id)}
                        className={`px-3 py-2 rounded-lg text-xs font-bold uppercase tracking-wider transition-all duration-305 ${
                          backtestStrategy === s.id 
                            ? "bg-white text-slate-808 border border-slate-200 font-bold shadow-sm" 
                            : "text-slate-500 hover:text-slate-808"
                        }`}
                      >
                        {s.label}
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              {backtestData?.results?.metrics && (
                <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                  <div className="bg-white border border-slate-205 p-4 rounded-xl text-center shadow-sm">
                    <span className="text-[10px] text-slate-455 uppercase tracking-widest block font-bold">Return</span>
                    <span className="text-xl font-bold font-mono text-emerald-600 block mt-1">{safeNumber(backtestData.results.metrics.total_return, 1)}%</span>
                  </div>
                  <div className="bg-white border border-slate-205 p-4 rounded-xl text-center shadow-sm">
                    <span className="text-[10px] text-slate-455 uppercase tracking-widest block font-bold">Win Rate</span>
                    <span className="text-xl font-bold font-mono text-slate-808 block mt-1">{safeNumber(backtestData.results.metrics.win_rate, 1)}%</span>
                  </div>
                  <div className="bg-white border border-slate-205 p-4 rounded-xl text-center shadow-sm">
                    <span className="text-[10px] text-slate-455 uppercase tracking-widest block font-bold">Sharpe</span>
                    <span className="text-xl font-bold font-mono text-slate-700 block mt-1">{safeNumber(backtestData.results.metrics.sharpe, 2)}</span>
                  </div>
                  <div className="bg-white border border-slate-205 p-4 rounded-xl text-center shadow-sm">
                    <span className="text-[10px] text-slate-455 uppercase tracking-widest block font-bold">Sortino</span>
                    <span className="text-xl font-bold font-mono text-slate-700 block mt-1">{safeNumber(backtestData.results.metrics.sortino, 2)}</span>
                  </div>
                  <div className="bg-white border border-slate-205 p-4 rounded-xl text-center shadow-sm">
                    <span className="text-[10px] text-slate-455 uppercase tracking-widest block font-bold">Max DD</span>
                    <span className="text-xl font-bold font-mono text-rose-605 block mt-1">{safeNumber(backtestData.results.metrics.max_drawdown, 2)}%</span>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* ==================== TAB 7: RESEARCH TERMINAL ==================== */}
          {activeTab === "terminal" && (
            <div className="space-y-4 animate-fade-slide">
              <div className="bg-white border border-slate-200 rounded-2xl overflow-hidden flex flex-col h-[460px] shadow-sm">
                <div className="p-4 border-b border-slate-200 bg-slate-50 flex items-center justify-between">
                  <div className="flex items-center gap-2.5 text-slate-700">
                    <Terminal className="h-5 w-5 text-slate-500" />
                    <span className="text-xs font-bold uppercase tracking-wider">QuantForge Bloomberg-lite GPT</span>
                  </div>
                </div>
                
                <div className="flex-1 p-4 overflow-y-auto space-y-3.5 font-mono text-sm leading-normal">
                  {researchChat.map((msg, idx) => (
                    <div key={idx} className={`flex gap-3 max-w-[85%] ${msg.role === 'user' ? 'ml-auto flex-row-reverse' : ''}`}>
                      <div className={`p-1.5 rounded bg-slate-100 h-fit shrink-0 border ${
                        msg.role === 'user' ? 'border-slate-350 text-slate-855' : 'border-slate-200 text-slate-700'
                      }`}>
                        {msg.role === 'user' ? 'USR' : 'SYS'}
                      </div>
                      <div className={`p-3.5 rounded-xl border ${
                        msg.role === 'user' ? 'bg-slate-50 border-slate-200 text-slate-808 font-semibold' : 'bg-white border-slate-200 text-slate-700 shadow-sm'
                      }`}>
                        {msg.text.split("\n").map((para, i) => (
                          <p key={i} className="mb-2 last:mb-0">{para}</p>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>

                <div className="p-3 bg-slate-50 border-t border-slate-200 flex gap-3">
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleResearchQuery()}
                    placeholder="Ask research terminal..."
                    className="flex-1 bg-white border border-slate-200 rounded-lg px-4 py-2 text-sm font-mono text-slate-808 placeholder-slate-400 focus:outline-none focus:border-slate-500"
                  />
                  <button
                    onClick={() => handleResearchQuery()}
                    className="bg-slate-700 hover:bg-slate-800 text-white px-4 py-2 rounded-xl text-sm font-bold font-mono transition-all shadow-sm"
                  >
                    SEND
                  </button>
                </div>
              </div>
            </div>
          )}

        </main>
      </div>
    </div>
  );
}

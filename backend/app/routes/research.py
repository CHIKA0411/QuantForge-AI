from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from app.db import get_db
from app.routes.analytics import get_current_options_data
from app.analytics import calculate_pcr, calculate_support_resistance
import os

router = APIRouter(prefix="/research", tags=["research"])

@router.get("/query")
def query_research_terminal(
    query: str = Query(..., description="The query to ask the research assistant"),
    symbol: str = Query(default="SENSEX"),
    db: Session = Depends(get_db)
):
    sym = symbol.upper()
    try:
        spot_price, vix, expiry_date, T, options = get_current_options_data(sym, db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to query market data for research: {e}")
        
    pcr = calculate_pcr(options, spot_price)
    sr = calculate_support_resistance(options, spot_price)
    
    # 1. Check if Gemini API key exists for live LLM responses
    api_key = os.getenv("GEMINI_API_KEY")
    if api_key:
        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel("gemini-1.5-flash")
            
            system_prompt = (
                f"You are a Bloomberg-lite terminal research analyst for Indian markets. "
                f"Answer the user's query contextually based on the following real-time data for {sym}:\n"
                f"- Spot Price: {spot_price}\n"
                f"- India VIX: {vix}\n"
                f"- Put-Call Ratio (OI): {pcr['pcr_oi']}\n"
                f"- Put-Call Ratio (Volume): {pcr['pcr_volume']}\n"
                f"- Supports: {', '.join([str(s['strike']) for s in sr['supports']])}\n"
                f"- Resistances: {', '.join([str(r['strike']) for r in sr['resistances']])}\n"
                f"- Expiry Date: {expiry_date}\n\n"
                f"Be precise, use bullet points, and maintain an institutional tone. Output in Markdown."
            )
            response = model.generate_content(f"{system_prompt}\n\nUser Question: {query}")
            return {
                "query": query,
                "symbol": sym,
                "response": response.text,
                "llm_powered": True
            }
        except Exception as e:
            # If genai fails, fallback to template builder
            pass

    # 2. Template-based RAG / rule engine
    q = query.lower()
    
    # Bullet points / Analysis templates
    if "support" in q or "resistance" in q or "level" in q or "floor" in q or "ceiling" in q:
        title = f"### Quantitative S/R Analysis for {sym}"
        s_list = "\n".join([f"- **Support Level**: {s['strike']} (OI: {int(s['oi']):,} contracts)" for s in sr['supports']])
        r_list = "\n".join([f"- **Resistance Level**: {r['strike']} (OI: {int(r['oi']):,} contracts)" for r in sr['resistances']])
        
        md_response = (
            f"{title}\n\n"
            f"Based on the options chain distribution for the expiry on {expiry_date}, here are the key technical levels:\n\n"
            f"{s_list}\n\n"
            f"{r_list}\n\n"
            f"**Analysis**: The highest concentration of Put open interest lies at **{sr['supports'][0]['strike'] if sr['supports'] else 'N/A'}**, acting as a strong technical support floor. "
            f"Meanwhile, heavy Call open interest concentration at **{sr['resistances'][0]['strike'] if sr['resistances'] else 'N/A'}** forms a major ceiling. "
            f"A breach on either side will likely trigger short-covering or long-unwinding spikes."
        )
    elif "pcr" in q or "put call" in q or "ratio" in q:
        title = f"### Put-Call Ratio (PCR) Deep-Dive: {sym}"
        pcr_oi = pcr["pcr_oi"]
        pcr_vol = pcr["pcr_volume"]
        
        if pcr_oi > 1.25:
            bias = "Strongly Bullish (Put writing dominates)"
            verdict = "Bullish. Put writers are aggressively defending downside strikes, suggesting a strong support floor."
        elif pcr_oi > 1.0:
            bias = "Bullish Bias"
            verdict = "Moderately Bullish. Rising put option accumulation indicates positive market sentiment."
        elif pcr_oi > 0.8:
            bias = "Neutral / Range Bound"
            verdict = "Balanced. Call writing and put writing are in equilibrium, indicating range-bound drift."
        else:
            bias = "Bearish Bias (Call writing dominates)"
            verdict = "Bearish. Aggressive Call writing at OTM strikes indicates limited upside potential."
            
        md_response = (
            f"{title}\n\n"
            f"Current PCR metrics for {sym}:\n"
            f"- **OI Put-Call Ratio (PCR)**: `{pcr_oi}`\n"
            f"- **Volume Put-Call Ratio**: `{pcr_vol}`\n"
            f"- **Sentiment Bias**: **{bias}**\n\n"
            f"**Verdict**: {verdict}\n\n"
            f"**Context**: Institutional traders typically write put options when they expect the market to remain above the strike. "
            f"The PCR OI of `{pcr_oi}` implies that for every call option written, there are `{pcr_oi}` put options written near the money."
        )
    elif "vix" in q or "volatility" in q or "skew" in q or "vega" in q:
        title = f"### Volatility Dashboard: {sym}"
        
        if vix < 12.0:
            regime = "Low Volatility (Risk-On)"
            implication = "Option premiums are relatively cheap. Buying options (long straddles/strangles) or trading long-biased directional trades is favored."
        elif vix < 16.0:
            regime = "Normal / Balanced State"
            implication = "Healthy, balanced market environment. Option prices reflect standard expected daily movement."
        elif vix < 22.0:
            regime = "Elevated Fear State"
            implication = "Increased market panic. Option premiums have expanded. High probability of large swings; delta-neutral option selling (iron condors) is viable but risky."
        else:
            regime = "Extreme Volatility (Capitulation)"
            implication = "High panic. Dealers are short gamma, leading to amplified price swings. Focus on risk management."
            
        md_response = (
            f"{title}\n\n"
            f"Current Volatility status for {sym}:\n"
            f"- **India VIX**: `{vix}`\n"
            f"- **Volatility Regime**: **{regime}**\n\n"
            f"**Market Implication**: {implication}\n\n"
            f"**Expected Spot Movement**: A VIX of `{vix}%` implies that the market expects a +/- `{vix}%` annualized standard deviation movement, translating to a daily expected move range of approximately `+/- {round(spot_price * (vix / 100.0) / 19.1, 1)}` points."
        )
    else:
        # Default: general market outlook
        title = f"### AI Market Outlook & Analysis: {sym}"
        pcr_oi = pcr["pcr_oi"]
        
        if pcr_oi > 1.05 and vix < 15.0:
            outlook = "Bullish consolidation. Favorable liquidity and low risk appetite suggest buying on dips."
        elif pcr_oi < 0.9 and vix > 15.0:
            outlook = "Bearish/Cautionary drift. High VIX and aggressive Call writing indicate overhead selling pressure."
        else:
            outlook = "Range-bound consolidative drift. Stable spot prices with consolidation around the ATM strike."
            
        md_response = (
            f"{title}\n\n"
            f"**Real-Time Snapshot**:\n"
            f"- **Spot price**: `{spot_price}`\n"
            f"- **India VIX**: `{vix}`\n"
            f"- **PCR (OI)**: `{pcr_oi}`\n\n"
            f"**Market Outlook**: {outlook}\n\n"
            f"**Strategic Recommendation**: Options writing (selling OTM puts) or bullish spreads are favored if spot remains above the primary support of **{sr['supports'][0]['strike'] if sr['supports'] else 'N/A'}**."
        )
        
    return {
        "query": query,
        "symbol": sym,
        "response": md_response,
        "llm_powered": False
    }

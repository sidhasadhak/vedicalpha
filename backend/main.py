"""
VedicAlpha — FastAPI Backend
Indian Stock & Commodity Prediction Engine
Combines 6 Vedic Jyotish engines with live market data and technical analysis.
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import uvicorn
from datetime import datetime, date
import math

from jyotish_engine import JyotishEngine
from prediction_engine import PredictionEngine
from market_data import MarketDataFetcher
from history_store import HistoryStore
from kalamrita_engine import KalamritaEngine

app = FastAPI(
    title="VedicAlpha API",
    description="Indian market prediction — 6 Vedic engines + Technical Analysis",
    version="1.0.0"
)

# Allow iOS app to call this backend (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialise engines (singleton instances)
jyotish   = JyotishEngine()
predictor = PredictionEngine(jyotish)
market    = MarketDataFetcher()
history   = HistoryStore()
kalamrita = KalamritaEngine()


# Default tickers shown on the iOS dashboard, in display order
DASHBOARD_TICKERS = [
    {"ticker": "SENSEX",    "exchange": "BSE",   "category": "index"},
    {"ticker": "NIFTY50",   "exchange": "NSE",   "category": "index"},
    {"ticker": "BANKNIFTY", "exchange": "NSE",   "category": "index"},
    {"ticker": "GOLD",      "exchange": "MCX",   "category": "gold"},
    {"ticker": "SILVER",    "exchange": "MCX",   "category": "silver"},
    {"ticker": "CRUDEOIL",  "exchange": "MCX",   "category": "commodity"},
    {"ticker": "COPPER",    "exchange": "MCX",   "category": "commodity"},
    {"ticker": "RELIANCE",  "exchange": "NSE",   "category": "equity"},
    {"ticker": "TCS",       "exchange": "NSE",   "category": "equity"},
    {"ticker": "HDFCBANK",  "exchange": "NSE",   "category": "equity"},
    {"ticker": "INFY",      "exchange": "NSE",   "category": "equity"},
    {"ticker": "ICICIBANK", "exchange": "NSE",   "category": "equity"},
    {"ticker": "SBIN",      "exchange": "NSE",   "category": "equity"},
    {"ticker": "BHARTIARTL","exchange": "NSE",   "category": "equity"},
    {"ticker": "BAJFINANCE","exchange": "NSE",   "category": "equity"},
]


# ─── Request / Response models ────────────────────────────────────────────────

class PredictionRequest(BaseModel):
    ticker:   str
    exchange: str = "NSE"       # NSE | BSE | MCX | NCDEX
    category: str = "equity"    # equity | index | commodity | agri
    horizon:  str = "1D"        # 1D | 1W | 2W | 1M | 3M
    mode:     str = "both"      # both | jyotish | technical
    target_date: Optional[str] = None   # ISO date, defaults to today


class AlertRequest(BaseModel):
    ticker:    str
    condition: str   # "bull" | "bear" | "confidence_above"
    threshold: Optional[float] = 70.0


class PrashnaRequest(BaseModel):
    ticker:    str
    exchange:  str = "NSE"
    category:  str = "equity"
    query_time: Optional[str] = None   # ISO datetime; defaults to now


# ─── Routes ──────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {
        "app": "VedicAlpha",
        "version": "1.0.0",
        "status": "running",
        "endpoints": ["/predict", "/panchanga", "/quote/{ticker}", "/history", "/search"]
    }


@app.post("/predict")
def predict(req: PredictionRequest):
    """
    Core prediction endpoint.
    Returns Jyotish + Technical signal with confidence, factors, and chart data.
    """
    target = date.fromisoformat(req.target_date) if req.target_date else date.today()

    # 1. Get Panchanga for target date
    panchanga = jyotish.get_panchanga(target)

    # 2. Fetch price — returns None for unrecognised tickers (no hallucination)
    price_data = market.get_quote(req.ticker.upper(), req.exchange.upper())
    if price_data is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Ticker '{req.ticker.upper()}' not found. "
                "Use /search to find supported instruments."
            ),
        )

    # 2b. For longer horizons, extend the OHLC history.
    #     1D/1W/2W: 65 daily bars (already in get_quote)
    #     1M:       200 daily bars — enough for reliable 200-DMA + medium-term RSI
    #     3M:       420 daily bars — ~1.5 years; aggregated to weekly inside engine
    # Calendar days, not trading days. Approx 252 trading days per 365 calendar.
    # 1M needs 200 trading days for 200-DMA → request ~300 calendar days.
    # 3M needs 420 trading days for weekly aggregation → request ~600 calendar days.
    _extra_days = {"1M": 300, "3M": 600}
    if req.horizon in _extra_days:
        extended = market.get_ohlc_history(
            req.ticker.upper(), days=_extra_days[req.horizon]
        )
        if len(extended.get("closes", [])) > len(price_data.get("closes", [])):
            price_data["closes"] = extended["closes"]
            price_data["highs"]  = extended["highs"]
            price_data["lows"]   = extended["lows"]
            price_data["opens"]  = extended.get("opens", [])

    # 3. Run prediction
    result = predictor.predict(
        ticker    = req.ticker,
        category  = req.category,
        horizon   = req.horizon,
        mode      = req.mode,
        panchanga = panchanga,
        price_data= price_data,
    )

    # 4. Save to history
    history.save(req.ticker, req.horizon, result, target)

    return {
        "ticker":    req.ticker,
        "exchange":  req.exchange,
        "horizon":   req.horizon,
        "date":      str(target),
        "panchanga": panchanga,
        "price":     price_data,
        "prediction": result,
    }


@app.get("/panchanga")
def get_panchanga(target_date: Optional[str] = Query(None)):
    """Returns today's (or given date's) full Panchanga."""
    target = date.fromisoformat(target_date) if target_date else date.today()
    return jyotish.get_panchanga(target)


@app.get("/quote/{ticker}")
def get_quote(ticker: str, exchange: str = "NSE"):
    """Live price quote for a registered instrument."""
    result = market.get_quote(ticker.upper(), exchange.upper())
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Ticker '{ticker.upper()}' not found. Use /search to find supported instruments.",
        )
    return result


@app.get("/search")
def search(q: str = Query(..., min_length=1)):
    """Search for instruments by ticker or name."""
    return market.search(q)


@app.get("/history")
def get_history(ticker: Optional[str] = None, limit: int = 20):
    """Fetch recent prediction history, optionally filtered by ticker."""
    return history.fetch(ticker=ticker, limit=limit)


@app.get("/dashboard")
def get_dashboard():
    """
    Returns 1-Day predictions for all default dashboard tickers in one call.
    iOS uses this to populate the home table on launch.
    """
    today     = date.today()
    panchanga = jyotish.get_panchanga(today)
    tickers   = []
    for inst in DASHBOARD_TICKERS:
        price_data = market.get_quote(inst["ticker"], inst["exchange"])
        result     = predictor.predict(
            ticker    = inst["ticker"],
            category  = inst["category"],
            horizon   = "1D",
            mode      = "both",
            panchanga = panchanga,
            price_data= price_data,
        )
        history.save(inst["ticker"], "1D", result, today)
        tickers.append({
            "ticker":   inst["ticker"],
            "exchange": inst["exchange"],
            "category": inst["category"],
            "price":    price_data,
            "prediction": result,
        })
    return {
        "date":      str(today),
        "panchanga": panchanga,
        "tickers":   tickers,
    }


@app.post("/prashna")
def prashna(req: PrashnaRequest):
    """
    Uttara Kalamrita Prashna (Horary) endpoint.

    Cast the query chart for the current moment and return an immediate
    BUY / SELL / HOLD signal for any instrument.

    Based on Uttara Kalamrita Chapter VII:
      - Day-lord → query category alignment
      - Moon-planet → secondary signal
      - Tithi timing (dhana/maraka) → score adjustment

    No natal chart required — pure horary analysis from query time.
    """
    query_dt   = (datetime.fromisoformat(req.query_time)
                  if req.query_time else datetime.now())
    query_date = query_dt.date()

    panchanga  = jyotish.get_panchanga(query_date)

    # Build a minimal kalamrita panchanga dict
    # vaar can be "Ravivaar (Sun)", "Somavaar (Mon)", etc.
    _vaar_map = {
        "sun":0, "ravi":0, "rav":0,
        "mon":1, "som":1,
        "tue":2, "man":2,
        "wed":3, "bud":3,
        "thu":4, "gur":4,
        "fri":5, "shu":5,
        "sat":6, "sha":6,
    }
    _vaar_raw  = str(panchanga.get("vaar", "")).lower()
    vaar_idx   = next(
        (v for k, v in _vaar_map.items() if _vaar_raw.startswith(k)),
        0
    )
    tithi_num  = panchanga.get("tithi", {}).get("number", 1)
    moon_age   = panchanga.get("tithi", {}).get("moon_age", 0.0)
    paksha     = panchanga.get("tithi", {}).get("paksha", "shukla")

    kpanch = {
        "vaar_idx":  vaar_idx,
        "tithi_num": tithi_num,
        "moon_age":  moon_age,
        "paksha":    paksha,
        "category":  req.category,
    }

    reading = kalamrita.get_prashna_reading(kpanch, req.ticker, req.category)

    return {
        "ticker":    req.ticker,
        "exchange":  req.exchange,
        "category":  req.category,
        "query_time": str(query_dt),
        "panchanga": panchanga,
        "prashna":   reading,
    }


@app.post("/backtest")
def backtest(ticker: str, horizon: str = "1W",
             days: int = 730, category: str = "equity"):
    """
    Back-test all 6 Vedic engines against historical closing prices.
    Returns composite accuracy, per-engine breakdown, and last 20 results.
    Default window: 2 years (730 days).
    """
    results = predictor.backtest(
        ticker=ticker, horizon=horizon, days=days, category=category
    )
    return results


@app.post("/alert")
def set_alert(req: AlertRequest):
    """Register an alert (stored locally; iOS polls /check_alerts)."""
    history.save_alert(req.model_dump())
    return {"status": "alert_saved", "ticker": req.ticker}


@app.get("/check_alerts")
def check_alerts():
    """Called by iOS app on launch to evaluate pending alerts."""
    alerts = history.get_alerts()
    triggered = []
    for a in alerts:
        panchanga  = jyotish.get_panchanga(date.today())
        price_data = market.get_quote(a["ticker"], "NSE")
        result     = predictor.predict(
            ticker=a["ticker"], category="equity",
            horizon="1D", mode="both",
            panchanga=panchanga, price_data=price_data
        )
        if a["condition"] == result["signal"]:
            triggered.append({"alert": a, "prediction": result})
    return {"triggered": triggered}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

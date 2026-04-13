"""
market_data.py
Live market data for Indian markets — NSE equities, MCX/NCDEX commodities, indices.

Priority order per call:
  NSE/BSE equities : nsepython  → yfinance (.NS)  → mock (registry-only)
  MCX commodities  : yfinance (converted to INR)   → mock (registry-only)
  NCDEX agri       : yfinance (.NS or skip)         → mock (registry-only)

Key design rules:
  1. MCX commodity prices from yfinance are in USD / international units.
     They are converted to INR in the correct MCX-quoted unit (see MCX_CONVERSIONS).
  2. Mock data is ONLY served for tickers registered in INSTRUMENTS.
     Unknown tickers return None — the API layer must raise a 404.
  3. USD/INR rate is fetched once per session and cached for 30 minutes.
"""

import random
import time
from datetime import datetime

# ── Instrument Registry ───────────────────────────────────────────────────────

INSTRUMENTS = [
    # NSE Equities
    {"ticker": "RELIANCE",    "name": "Reliance Industries",       "exchange": "NSE",   "category": "equity"},
    {"ticker": "TCS",         "name": "Tata Consultancy Services", "exchange": "NSE",   "category": "equity"},
    {"ticker": "INFY",        "name": "Infosys Ltd",               "exchange": "NSE",   "category": "equity"},
    {"ticker": "HDFCBANK",    "name": "HDFC Bank",                 "exchange": "NSE",   "category": "equity"},
    {"ticker": "ICICIBANK",   "name": "ICICI Bank",                "exchange": "NSE",   "category": "equity"},
    {"ticker": "SBIN",        "name": "State Bank of India",       "exchange": "NSE",   "category": "equity"},
    {"ticker": "WIPRO",       "name": "Wipro Ltd",                 "exchange": "NSE",   "category": "equity"},
    {"ticker": "BAJFINANCE",  "name": "Bajaj Finance",             "exchange": "NSE",   "category": "equity"},
    {"ticker": "TATASTEEL",   "name": "Tata Steel",                "exchange": "NSE",   "category": "equity"},
    {"ticker": "ADANIENT",    "name": "Adani Enterprises",         "exchange": "NSE",   "category": "equity"},
    {"ticker": "BHARTIARTL",  "name": "Bharti Airtel",             "exchange": "NSE",   "category": "equity"},
    {"ticker": "LT",          "name": "Larsen & Toubro",           "exchange": "NSE",   "category": "equity"},
    {"ticker": "AXISBANK",    "name": "Axis Bank",                 "exchange": "NSE",   "category": "equity"},
    {"ticker": "MARUTI",      "name": "Maruti Suzuki",             "exchange": "NSE",   "category": "equity"},
    {"ticker": "SUNPHARMA",   "name": "Sun Pharmaceutical",        "exchange": "NSE",   "category": "equity"},
    {"ticker": "HCLTECH",     "name": "HCL Technologies",          "exchange": "NSE",   "category": "equity"},
    {"ticker": "KOTAKBANK",   "name": "Kotak Mahindra Bank",       "exchange": "NSE",   "category": "equity"},
    {"ticker": "TITAN",       "name": "Titan Company",             "exchange": "NSE",   "category": "equity"},
    {"ticker": "ITC",         "name": "ITC Ltd",                   "exchange": "NSE",   "category": "equity"},
    {"ticker": "NESTLEIND",   "name": "Nestle India",              "exchange": "NSE",   "category": "equity"},
    # Indices
    {"ticker": "SENSEX",      "name": "BSE Sensex",                "exchange": "BSE",   "category": "index"},
    {"ticker": "NIFTY50",     "name": "Nifty 50 Index",            "exchange": "NSE",   "category": "index"},
    {"ticker": "BANKNIFTY",   "name": "Bank Nifty Index",          "exchange": "NSE",   "category": "index"},
    {"ticker": "NIFTYMIDCAP", "name": "Nifty Midcap 100",          "exchange": "NSE",   "category": "index"},
    {"ticker": "NIFTYIT",     "name": "Nifty IT Index",            "exchange": "NSE",   "category": "index"},
    # MCX Commodities
    {"ticker": "GOLD",        "name": "Gold (24K)",                "exchange": "MCX",   "category": "gold"},
    {"ticker": "GOLDM",       "name": "Gold Mini",                 "exchange": "MCX",   "category": "gold"},
    {"ticker": "SILVER",      "name": "Silver",                    "exchange": "MCX",   "category": "silver"},
    {"ticker": "SILVERM",     "name": "Silver Mini",               "exchange": "MCX",   "category": "silver"},
    {"ticker": "CRUDEOIL",    "name": "Crude Oil",                 "exchange": "MCX",   "category": "commodity"},
    {"ticker": "NATURALGAS",  "name": "Natural Gas",               "exchange": "MCX",   "category": "commodity"},
    {"ticker": "COPPER",      "name": "Copper",                    "exchange": "MCX",   "category": "commodity"},
    {"ticker": "ZINC",        "name": "Zinc",                      "exchange": "MCX",   "category": "commodity"},
    {"ticker": "ALUMINIUM",   "name": "Aluminium",                 "exchange": "MCX",   "category": "commodity"},
    {"ticker": "NICKEL",      "name": "Nickel",                    "exchange": "MCX",   "category": "commodity"},
    {"ticker": "LEAD",        "name": "Lead",                      "exchange": "MCX",   "category": "commodity"},
    # NCDEX Agri
    {"ticker": "WHEAT",       "name": "Wheat (Gehu)",              "exchange": "NCDEX", "category": "agri"},
    {"ticker": "COTTON",      "name": "Cotton (Kapas)",            "exchange": "NCDEX", "category": "agri"},
    {"ticker": "SOYBEAN",     "name": "Soybean",                   "exchange": "NCDEX", "category": "agri"},
    {"ticker": "SUGAR",       "name": "Sugar (Chini)",             "exchange": "NCDEX", "category": "agri"},
    {"ticker": "MUSTARD",     "name": "Mustard (Sarson)",          "exchange": "NCDEX", "category": "agri"},
    {"ticker": "TURMERIC",    "name": "Turmeric (Haldi)",          "exchange": "NCDEX", "category": "agri"},
    {"ticker": "JEERA",       "name": "Cumin (Jeera)",             "exchange": "NCDEX", "category": "agri"},
    {"ticker": "CHANA",       "name": "Chana (Chickpea)",          "exchange": "NCDEX", "category": "agri"},
    {"ticker": "CASTOR",      "name": "Castor Seed",               "exchange": "NCDEX", "category": "agri"},
    {"ticker": "GUARSEED",    "name": "Guar Seed",                 "exchange": "NCDEX", "category": "agri"},
    {"ticker": "DHANIYA",     "name": "Coriander (Dhaniya)",       "exchange": "NCDEX", "category": "agri"},
    {"ticker": "BARLEY",      "name": "Barley (Jau)",              "exchange": "NCDEX", "category": "agri"},
]

VALID_TICKERS = {i["ticker"] for i in INSTRUMENTS}

# ── MCX commodity conversions ─────────────────────────────────────────────────
#
# yfinance returns international futures in USD and non-MCX units.
# Each entry: (yfinance_symbol, factor_fn)
# factor_fn(usd_inr_rate) → multiply raw yfinance price by this to get MCX INR price.
#
# GOLD   GC=F : USD per troy oz   →  INR per 10 g   (MCX quote unit)
#               1 troy oz = 31.1035 g  →  factor = usd_inr × 10 / 31.1035 × DUTY
# SILVER SI=F : USD per troy oz   →  INR per kg
#               factor = usd_inr × 1000 / 31.1035 × DUTY
# CRUDE  CL=F : USD per barrel    →  INR per barrel  (same unit, only currency)
#               factor = usd_inr
# NATGAS NG=F : USD per MMBtu     →  INR per MMBtu
#               factor = usd_inr
# COPPER HG=F : USD per pound     →  INR per kg
#               1 kg = 2.20462 lb  →  factor = usd_inr × 2.20462
#
# GOLD/SILVER DUTY NOTE:
#   COMEX futures (GC=F, SI=F) are international spot-equivalent prices.
#   MCX-quoted gold/silver prices in India include:
#     Import duty:  6.4%   (reduced from 15% in Union Budget Aug 2024)
#     GST:          3.0%
#     Total factor: ×1.094
#   Without this, gold would show ~7% below what Indian traders see on MCX.
#   Update _GOLD_SILVER_DUTY if the import duty rate changes.
#
# ZINC / ALUMINIUM / NICKEL / LEAD have no reliable public yfinance symbol;
# they fall through to calibrated mock prices.
#
_GOLD_SILVER_DUTY = 1.094  # import duty 6.4% + GST 3.0% = 9.4%

MCX_CONVERSIONS: dict[str, tuple[str, object]] = {
    "GOLD":       ("GC=F",  lambda fx: fx * 10 / 31.1035 * _GOLD_SILVER_DUTY),
    "GOLDM":      ("GC=F",  lambda fx: fx * 10 / 31.1035 * _GOLD_SILVER_DUTY),
    "SILVER":     ("SI=F",  lambda fx: fx * 1000 / 31.1035 * _GOLD_SILVER_DUTY),
    "SILVERM":    ("SI=F",  lambda fx: fx * 1000 / 31.1035 * _GOLD_SILVER_DUTY),
    "CRUDEOIL":   ("CL=F",  lambda fx: fx),
    "NATURALGAS": ("NG=F",  lambda fx: fx),
    "COPPER":     ("HG=F",  lambda fx: fx * 2.20462),
}

# yfinance symbols for indices (already priced in INR — no conversion needed)
INDEX_YF_MAP: dict[str, str] = {
    "NIFTY50":    "^NSEI",
    "BANKNIFTY":  "^NSEBANK",
    "SENSEX":     "^BSESN",
    "NIFTYMIDCAP":"^NSEMDCP50",
    "NIFTYIT":    "^CNXIT",
}

# ── Mock prices (INR, in MCX-quoted units where applicable) ───────────────────
#
# These are calibrated to approximate April 2026 levels.
# Used ONLY as fallback for registered instruments when all live sources fail.
#
MOCK_PRICES = {
    # NSE Equities — calibrated to April 2026 approximate close prices
    "RELIANCE":   1280,  "TCS":       3400,  "INFY":      1500,
    "HDFCBANK":   1750,  "ICICIBANK": 1380,  "SBIN":       780,
    "WIPRO":       300,  "BAJFINANCE":8800,  "TATASTEEL":  155,
    "ADANIENT":   2300,  "BHARTIARTL":1850,  "LT":        3500,
    "AXISBANK":   1180,  "MARUTI":   12000,  "SUNPHARMA": 1820,
    "HCLTECH":    1530,  "KOTAKBANK": 2150,  "TITAN":     3400,
    "ITC":         420,  "NESTLEIND": 2350,
    # Indices (INR points) — April 2026
    "NIFTY50":   23200,  "BANKNIFTY": 52500, "SENSEX":   76500,
    "NIFTYMIDCAP":53500, "NIFTYIT":  35500,
    # MCX Commodities — prices in MCX-quoted INR units, calibrated April 2026
    "GOLD":     152000,  # INR per 10 g   (~$5,650/oz × ₹85.5 × 10/31.1)
    "GOLDM":    152000,
    "SILVER":   243000,  # INR per kg     (~$32/oz × ₹85.5 × 1000/31.1)
    "SILVERM":  243000,
    "CRUDEOIL":   5950,  # INR per barrel (~$70/bbl × ₹85.5)
    "NATURALGAS":  285,  # INR per MMBtu  (~$3.35/MMBtu × ₹85.5)
    "COPPER":     1212,  # INR per kg     (~$6.45/lb × ₹85.5 × 2.20462)
    "ZINC":        295,  # INR per kg     (~$1.62/lb × ₹85.5 × 2.20462)
    "ALUMINIUM":   240,  # INR per kg     (~$1.31/lb × ₹85.5 × 2.20462)
    "NICKEL":     1460,  # INR per kg     (~$7.75/lb × ₹85.5 × 2.20462)
    "LEAD":        190,  # INR per kg     (~$1.01/lb × ₹85.5 × 2.20462)
    # NCDEX Agri (INR per quintal unless noted) — April 2026 estimates
    "WHEAT":      2350,  "COTTON":   58000,  "SOYBEAN":   4650,
    "SUGAR":      3850,  "MUSTARD":   5950,  "TURMERIC": 13500,
    "JEERA":     24000,  "CHANA":     5400,  "CASTOR":    6200,
    "GUARSEED":   5700,  "DHANIYA":   7800,  "BARLEY":    2100,
}


class MarketDataFetcher:
    """
    Fetches live market data with currency/unit-correct MCX commodity prices.
    Falls back to calibrated mock only for registered instruments.
    Returns None for unrecognised tickers — the API layer must surface a 404.
    """

    # USD/INR cache: (rate, fetched_at_epoch)
    _usd_inr_cache: tuple[float, float] = (84.0, 0.0)
    _CACHE_TTL = 1800  # 30 minutes

    # ── USD/INR ───────────────────────────────────────────────────────────────

    def _usd_inr(self) -> float:
        """
        Return current USD/INR rate, cached for 30 min.

        Sources tried in order:
          1. open.er-api.com  — free, no API key, reliable JSON
          2. yfinance USDINR=X .history() — uses .history(), NOT fast_info
             (fast_info is not a dict; .get() always returns None on it)
          3. Cached value from last successful fetch
        """
        rate, ts = self.__class__._usd_inr_cache
        if time.time() - ts < self._CACHE_TTL:
            return rate

        # Source 1: open.er-api.com (free, no key required)
        try:
            import urllib.request, json as _json
            with urllib.request.urlopen(
                "https://open.er-api.com/v6/latest/USD", timeout=5
            ) as resp:
                data  = _json.loads(resp.read())
                fresh = float(data["rates"]["INR"])
                if 70 < fresh < 110:
                    self.__class__._usd_inr_cache = (fresh, time.time())
                    return fresh
        except Exception:
            pass

        # Source 2: yfinance USDINR=X via history() (not fast_info)
        try:
            import yfinance as yf
            hist  = yf.Ticker("USDINR=X").history(period="2d")
            fresh = float(hist["Close"].iloc[-1])
            if 70 < fresh < 110:
                self.__class__._usd_inr_cache = (fresh, time.time())
                return fresh
        except Exception:
            pass

        return rate  # return cached value if both sources fail

    # ── Public interface ──────────────────────────────────────────────────────

    def get_quote(self, ticker: str, exchange: str = "NSE") -> dict | None:
        """
        Returns a price quote dict or None if the ticker is unrecognised.
        Callers must treat None as "instrument not found".
        """
        ticker = ticker.upper()

        # 1. NSE/BSE equities — try nsepython first
        if exchange in ("NSE", "BSE"):
            result = self._try_nsepython(ticker)
            if result:
                return result

        # 2. MCX commodities with known yfinance mapping
        if ticker in MCX_CONVERSIONS:
            result = self._try_yfinance_mcx(ticker)
            if result:
                return result

        # 3. Indices and remaining NSE equities via yfinance
        result = self._try_yfinance_inr(ticker, exchange)
        if result:
            return result

        # 4. Fallback mock — ONLY for registered instruments
        if ticker in VALID_TICKERS:
            return self._mock_quote(ticker, exchange)

        # Unknown ticker — do not hallucinate
        return None

    def get_ohlc_history(self, ticker: str, days: int = 60) -> dict:
        """
        Returns {closes, highs, lows, opens} for technical indicators.
        Used by the backtest engine and technical signal computation.
        """
        ticker = ticker.upper()
        if ticker in MCX_CONVERSIONS:
            return self._fetch_ohlc_mcx(ticker, days)
        return self._fetch_ohlc_nse(ticker, days)

    def search(self, query: str) -> list:
        """Search instruments by ticker prefix or name substring."""
        q = query.strip().upper()
        return [
            i for i in INSTRUMENTS
            if q in i["ticker"] or q in i["name"].upper()
        ][:10]

    # ── NSE / BSE via nsepython ───────────────────────────────────────────────

    def _try_nsepython(self, ticker: str) -> dict | None:
        try:
            from nsepython import nse_eq
            data  = nse_eq(ticker)
            price = data["priceInfo"]["lastPrice"]
            chg   = data["priceInfo"]["change"]
            pct   = data["priceInfo"]["pChange"]
            ohlc  = data["priceInfo"]["intraDayHighLow"]
            hist  = self._fetch_ohlc_nse(ticker)
            return {
                "ticker":     ticker,
                "price":      price,
                "change":     chg,
                "change_pct": pct,
                "open":       ohlc.get("min", price),
                "high":       ohlc.get("max", price),
                "low":        ohlc.get("min", price),
                "close":      price,
                "source":     "nsepython (live)",
                "closes":     hist["closes"],
                "highs":      hist["highs"],
                "lows":       hist["lows"],
                "opens":      hist.get("opens", []),
                "timestamp":  datetime.now().isoformat(),
            }
        except Exception:
            return None

    def _fetch_ohlc_nse(self, ticker: str, days: int = 60) -> dict:
        """OHLC history for NSE equities via yfinance (.NS suffix). Returns INR."""
        try:
            import yfinance as yf
            from datetime import timedelta, date as _date
            end   = _date.today()
            start = end - timedelta(days=days + 15)
            sym   = INDEX_YF_MAP.get(ticker, f"{ticker}.NS")
            hist  = yf.Ticker(sym).history(start=str(start), end=str(end))
            if hist.empty:
                return {"closes": [], "highs": [], "lows": [], "opens": []}
            return {
                "closes": [round(float(v), 2) for v in hist["Close"]],
                "highs":  [round(float(v), 2) for v in hist["High"]],
                "lows":   [round(float(v), 2) for v in hist["Low"]],
                "opens":  [round(float(v), 2) for v in hist["Open"]],
            }
        except Exception:
            return {"closes": [], "highs": [], "lows": [], "opens": []}

    # ── MCX commodities via yfinance (with INR conversion) ────────────────────

    def _try_yfinance_mcx(self, ticker: str) -> dict | None:
        """
        Fetch MCX commodity price from yfinance and convert to INR.
        Raw yfinance data is in USD + international units (see MCX_CONVERSIONS).
        """
        sym, factor_fn = MCX_CONVERSIONS[ticker]
        try:
            import yfinance as yf
            fx      = self._usd_inr()
            factor  = factor_fn(fx)
            t       = yf.Ticker(sym)
            hist    = t.history(period="65d")
            if hist.empty or len(hist) < 2:
                return None

            # Convert the entire price history to INR
            closes_inr = [round(float(v) * factor, 2) for v in hist["Close"]]
            highs_inr  = [round(float(v) * factor, 2) for v in hist["High"]]
            lows_inr   = [round(float(v) * factor, 2) for v in hist["Low"]]
            opens_inr  = [round(float(v) * factor, 2) for v in hist["Open"]]

            last   = closes_inr[-1]
            prev   = closes_inr[-2]
            chg    = round(last - prev, 2)
            chg_pct = round((last - prev) / prev * 100, 2) if prev else 0.0

            return {
                "ticker":     ticker,
                "price":      last,
                "change":     chg,
                "change_pct": chg_pct,
                "open":       opens_inr[-1],
                "high":       highs_inr[-1],
                "low":        lows_inr[-1],
                "close":      last,
                "source":     f"yfinance {sym} → INR (fx={fx:.2f})",
                "closes":     closes_inr,
                "highs":      highs_inr,
                "lows":       lows_inr,
                "opens":      opens_inr,
                "timestamp":  datetime.now().isoformat(),
            }
        except Exception:
            return None

    def _fetch_ohlc_mcx(self, ticker: str, days: int = 60) -> dict:
        """OHLC history for MCX commodities, converted to INR."""
        sym, factor_fn = MCX_CONVERSIONS.get(ticker, (None, None))
        if not sym:
            return {"closes": [], "highs": [], "lows": [], "opens": []}
        try:
            import yfinance as yf
            from datetime import timedelta, date as _date
            fx     = self._usd_inr()
            factor = factor_fn(fx)
            end    = _date.today()
            start  = end - timedelta(days=days + 15)
            hist   = yf.Ticker(sym).history(start=str(start), end=str(end))
            if hist.empty:
                return {"closes": [], "highs": [], "lows": [], "opens": []}
            return {
                "closes": [round(float(v) * factor, 2) for v in hist["Close"]],
                "highs":  [round(float(v) * factor, 2) for v in hist["High"]],
                "lows":   [round(float(v) * factor, 2) for v in hist["Low"]],
                "opens":  [round(float(v) * factor, 2) for v in hist["Open"]],
            }
        except Exception:
            return {"closes": [], "highs": [], "lows": [], "opens": []}

    # ── Generic yfinance (indices + NSE fallback, already in INR) ─────────────

    def _try_yfinance_inr(self, ticker: str, exchange: str) -> dict | None:
        """
        yfinance for indices and NSE equities not caught by nsepython.
        Prices returned by yfinance for Indian tickers are already in INR.
        """
        try:
            import yfinance as yf
            sym  = INDEX_YF_MAP.get(ticker, f"{ticker}.NS")
            t    = yf.Ticker(sym)
            hist = t.history(period="65d")
            if hist.empty or len(hist) < 2:
                return None

            closes = [round(float(v), 2) for v in hist["Close"]]
            highs  = [round(float(v), 2) for v in hist["High"]]
            lows   = [round(float(v), 2) for v in hist["Low"]]
            opens  = [round(float(v), 2) for v in hist["Open"]]

            last    = closes[-1]
            prev    = closes[-2]
            chg     = round(last - prev, 2)
            chg_pct = round((last - prev) / prev * 100, 2) if prev else 0.0

            return {
                "ticker":     ticker,
                "price":      last,
                "change":     chg,
                "change_pct": chg_pct,
                "open":       opens[-1],
                "high":       highs[-1],
                "low":        lows[-1],
                "close":      last,
                "source":     "yfinance (live INR)",
                "closes":     closes,
                "highs":      highs,
                "lows":       lows,
                "opens":      opens,
                "timestamp":  datetime.now().isoformat(),
            }
        except Exception:
            return None

    # ── Calibrated mock (registered instruments only) ─────────────────────────

    def _mock_quote(self, ticker: str, exchange: str) -> dict:
        """
        Simulated quote for registered instruments when all live sources fail.
        Prices match MCX-quoted INR units (see MOCK_PRICES header comments).
        Never called for unregistered tickers.
        """
        base  = MOCK_PRICES.get(ticker, 1000)
        noise = random.uniform(-0.015, 0.015)
        price = round(base * (1 + noise), 2)
        chg   = round(price - base, 2)
        pct   = round(noise * 100, 2)

        # Generate 60 simulated OHLC bars with a random walk
        closes, opens, highs, lows = [], [], [], []
        p = base
        for _ in range(61):
            o = round(p * (1 + random.uniform(-0.004, 0.004)), 2)
            p = round(p * (1 + random.uniform(-0.010, 0.010)), 2)
            h = round(max(o, p) * random.uniform(1.001, 1.008), 2)
            l = round(min(o, p) * random.uniform(0.992, 0.999), 2)
            opens.append(o); closes.append(p)
            highs.append(h); lows.append(l)

        # Replace last bar with the quoted price
        closes[-1] = price
        highs[-1]  = round(price * 1.007, 2)
        lows[-1]   = round(price * 0.993, 2)
        opens[-1]  = round(base  * (1 + random.uniform(-0.003, 0.003)), 2)

        return {
            "ticker":     ticker,
            "price":      price,
            "change":     chg,
            "change_pct": pct,
            "open":       opens[-1],
            "high":       highs[-1],
            "low":        lows[-1],
            "close":      price,
            "source":     "mock (live APIs unavailable)",
            "closes":     closes,
            "highs":      highs,
            "lows":       lows,
            "opens":      opens,
            "timestamp":  datetime.now().isoformat(),
        }

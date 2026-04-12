"""
market_data.py
Live market data fetcher for Indian markets.
Priority order: nsepython → yfinance → mock data
Gracefully falls back if APIs are unavailable.
"""

import random
from datetime import datetime

# ── Instrument Registry ───────────────────────────────────────────────────────
# All supported instruments with metadata

INSTRUMENTS = [
    # NSE Equities
    {"ticker": "RELIANCE",    "name": "Reliance Industries",      "exchange": "NSE", "category": "equity"},
    {"ticker": "TCS",         "name": "Tata Consultancy Services", "exchange": "NSE", "category": "equity"},
    {"ticker": "INFY",        "name": "Infosys Ltd",               "exchange": "NSE", "category": "equity"},
    {"ticker": "HDFCBANK",    "name": "HDFC Bank",                 "exchange": "NSE", "category": "equity"},
    {"ticker": "ICICIBANK",   "name": "ICICI Bank",                "exchange": "NSE", "category": "equity"},
    {"ticker": "SBIN",        "name": "State Bank of India",       "exchange": "NSE", "category": "equity"},
    {"ticker": "WIPRO",       "name": "Wipro Ltd",                 "exchange": "NSE", "category": "equity"},
    {"ticker": "BAJFINANCE",  "name": "Bajaj Finance",             "exchange": "NSE", "category": "equity"},
    {"ticker": "TATASTEEL",   "name": "Tata Steel",                "exchange": "NSE", "category": "equity"},
    {"ticker": "ADANIENT",    "name": "Adani Enterprises",         "exchange": "NSE", "category": "equity"},
    {"ticker": "BHARTIARTL",  "name": "Bharti Airtel",             "exchange": "NSE", "category": "equity"},
    {"ticker": "LT",          "name": "Larsen & Toubro",           "exchange": "NSE", "category": "equity"},
    {"ticker": "AXISBANK",    "name": "Axis Bank",                 "exchange": "NSE", "category": "equity"},
    {"ticker": "MARUTI",      "name": "Maruti Suzuki",             "exchange": "NSE", "category": "equity"},
    {"ticker": "SUNPHARMA",   "name": "Sun Pharmaceutical",        "exchange": "NSE", "category": "equity"},
    {"ticker": "HCLTECH",     "name": "HCL Technologies",          "exchange": "NSE", "category": "equity"},
    {"ticker": "KOTAKBANK",   "name": "Kotak Mahindra Bank",       "exchange": "NSE", "category": "equity"},
    {"ticker": "TITAN",       "name": "Titan Company",             "exchange": "NSE", "category": "equity"},
    {"ticker": "ITC",         "name": "ITC Ltd",                   "exchange": "NSE", "category": "equity"},
    {"ticker": "NESTLEIND",   "name": "Nestle India",              "exchange": "NSE", "category": "equity"},
    # NSE / BSE Indices
    {"ticker": "SENSEX",      "name": "BSE Sensex",                "exchange": "BSE", "category": "index"},
    {"ticker": "NIFTY50",     "name": "Nifty 50 Index",            "exchange": "NSE", "category": "index"},
    {"ticker": "BANKNIFTY",   "name": "Bank Nifty Index",          "exchange": "NSE", "category": "index"},
    {"ticker": "NIFTYMIDCAP", "name": "Nifty Midcap 100",          "exchange": "NSE", "category": "index"},
    {"ticker": "NIFTYIT",     "name": "Nifty IT Index",            "exchange": "NSE", "category": "index"},
    # MCX Commodities
    {"ticker": "GOLD",        "name": "Gold (24K)",                "exchange": "MCX", "category": "gold"},
    {"ticker": "GOLDM",       "name": "Gold Mini",                 "exchange": "MCX", "category": "gold"},
    {"ticker": "SILVER",      "name": "Silver",                    "exchange": "MCX", "category": "silver"},
    {"ticker": "SILVERM",     "name": "Silver Mini",               "exchange": "MCX", "category": "silver"},
    {"ticker": "CRUDEOIL",    "name": "Crude Oil (WTI)",           "exchange": "MCX", "category": "commodity"},
    {"ticker": "NATURALGAS",  "name": "Natural Gas",               "exchange": "MCX", "category": "commodity"},
    {"ticker": "COPPER",      "name": "Copper",                    "exchange": "MCX", "category": "commodity"},
    {"ticker": "ZINC",        "name": "Zinc",                      "exchange": "MCX", "category": "commodity"},
    {"ticker": "ALUMINIUM",   "name": "Aluminium",                 "exchange": "MCX", "category": "commodity"},
    {"ticker": "NICKEL",      "name": "Nickel",                    "exchange": "MCX", "category": "commodity"},
    {"ticker": "LEAD",        "name": "Lead",                      "exchange": "MCX", "category": "commodity"},
    # NCDEX Agri Commodities
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

# Reference base prices (INR) for mock data
MOCK_PRICES = {
    "RELIANCE": 2950, "TCS": 3780, "INFY": 1680, "HDFCBANK": 1720,
    "ICICIBANK": 1240, "SBIN": 820, "WIPRO": 580, "BAJFINANCE": 7100,
    "TATASTEEL": 165, "NIFTY50": 22500, "BANKNIFTY": 48000, "SENSEX": 74500,
    "GOLD": 72000, "SILVER": 86000, "CRUDEOIL": 6800, "COPPER": 850,
    "NATURALGAS": 230, "ZINC": 265, "ALUMINIUM": 225,
    "WHEAT": 2200, "COTTON": 6800, "SOYBEAN": 4500,
    "SUGAR": 3700, "MUSTARD": 5800, "TURMERIC": 14000,
    "JEERA": 25000, "CHANA": 5200,
}


class MarketDataFetcher:
    """
    Fetches live market data. Falls back gracefully through multiple sources.
    Plug in your API keys in config.py to activate live data.
    """

    def get_quote(self, ticker: str, exchange: str = "NSE") -> dict:
        """
        Returns price quote.
        Tries: nsepython → yfinance → mock data
        """
        # Try nsepython for NSE equities
        if exchange in ("NSE", "BSE"):
            result = self._try_nsepython(ticker)
            if result:
                return result

        # Try yfinance for MCX / global commodities
        result = self._try_yfinance(ticker, exchange)
        if result:
            return result

        # Fallback to mock data
        return self._mock_quote(ticker, exchange)

    def _try_nsepython(self, ticker: str) -> dict | None:
        """Fetch live NSE quote + 30-day history for RSI/MACD."""
        try:
            from nsepython import nse_eq
            data   = nse_eq(ticker)
            price  = data["priceInfo"]["lastPrice"]
            change = data["priceInfo"]["change"]
            pct    = data["priceInfo"]["pChange"]
            ohlc   = data["priceInfo"]["intraDayHighLow"]

            # Fetch OHLC history via yfinance for all technical indicators.
            ohlc_hist = self._fetch_ohlc_yfinance(ticker)

            return {
                "ticker":     ticker,
                "price":      price,
                "change":     change,
                "change_pct": pct,
                "open":       ohlc.get("min", price),
                "high":       ohlc.get("max", price),
                "low":        ohlc.get("min", price),
                "close":      price,
                "source":     "nsepython (live)",
                "closes":     ohlc_hist["closes"],
                "highs":      ohlc_hist["highs"],
                "lows":       ohlc_hist["lows"],
                "timestamp":  datetime.now().isoformat(),
            }
        except Exception:
            return None

    def _fetch_ohlc_yfinance(self, ticker: str, days: int = 60) -> dict:
        """Return {closes, highs, lows} lists via yfinance, or empty lists on failure."""
        try:
            import yfinance as yf
            from datetime import timedelta, date as _date
            end   = _date.today()
            start = end - timedelta(days=days + 10)
            hist  = yf.Ticker(f"{ticker}.NS").history(start=str(start), end=str(end))
            if hist.empty:
                return {"closes": [], "highs": [], "lows": []}
            return {
                "closes": list(hist["Close"].round(2)),
                "highs":  list(hist["High"].round(2)),
                "lows":   list(hist["Low"].round(2)),
            }
        except Exception:
            return {"closes": [], "highs": [], "lows": []}

    def _try_yfinance(self, ticker: str, exchange: str) -> dict | None:
        """Fetch data using yfinance (works for commodities and global markets)."""
        try:
            import yfinance as yf
            yf_map = {
                "GOLD": "GC=F", "SILVER": "SI=F", "CRUDEOIL": "CL=F",
                "COPPER": "HG=F", "NATURALGAS": "NG=F", "ALUMINIUM": "ALI=F",
                "NIFTY50": "^NSEI", "BANKNIFTY": "^NSEBANK", "SENSEX": "^BSESN",
            }
            symbol = yf_map.get(ticker, f"{ticker}.NS")
            t      = yf.Ticker(symbol)
            hist   = t.history(period="60d")
            if hist.empty:
                return None
            closes = list(hist["Close"].round(2))
            opens  = list(hist["Open"].round(2))
            highs  = list(hist["High"].round(2))
            lows   = list(hist["Low"].round(2))
            last   = closes[-1]
            prev   = closes[-2] if len(closes) > 1 else last
            return {
                "ticker":     ticker,
                "price":      round(last, 2),
                "change":     round(last - prev, 2),
                "change_pct": round((last - prev) / prev * 100, 2),
                "open":       round(float(hist["Open"].iloc[-1]), 2),
                "high":       round(float(hist["High"].iloc[-1]), 2),
                "low":        round(float(hist["Low"].iloc[-1]), 2),
                "close":      round(last, 2),
                "closes":     closes,
                "opens":      opens,
                "highs":      highs,
                "lows":       lows,
                "source":     "yfinance (live)",
                "timestamp":  datetime.now().isoformat(),
            }
        except Exception:
            return None

    def _mock_quote(self, ticker: str, exchange: str) -> dict:
        """Simulated quote when all live sources are unavailable."""
        base   = MOCK_PRICES.get(ticker, 1000)
        noise  = random.uniform(-0.015, 0.015)
        price  = round(base * (1 + noise), 2)
        change = round(price - base, 2)
        pct    = round(noise * 100, 2)
        # Generate 60 simulated OHLC bars for all technical indicators
        closes, opens, highs, lows = [], [], [], []
        p = base
        for _ in range(60):
            o = round(p * (1 + random.uniform(-0.005, 0.005)), 2)
            p = p * (1 + random.uniform(-0.012, 0.012))
            c = round(p, 2)
            opens.append(o)
            closes.append(c)
            highs.append(round(max(o, c) * random.uniform(1.001, 1.010), 2))
            lows.append(round(min(o, c)  * random.uniform(0.990, 0.999), 2))
        opens.append(round(price * (1 + random.uniform(-0.003, 0.003)), 2))
        closes.append(price)
        highs.append(round(price * 1.008, 2))
        lows.append(round(price  * 0.992, 2))
        return {
            "ticker":     ticker,
            "price":      price,
            "change":     change,
            "change_pct": pct,
            "open":       round(base * (1 + random.uniform(-0.01, 0.01)), 2),
            "high":       highs[-1],
            "low":        lows[-1],
            "close":      price,
            "closes":     closes,
            "opens":      opens,
            "highs":      highs,
            "lows":       lows,
            "source":     "mock (no API connected)",
            "timestamp":  datetime.now().isoformat(),
        }

    def search(self, query: str) -> list:
        """Search instruments by ticker prefix or name substring."""
        q = query.upper()
        results = [
            i for i in INSTRUMENTS
            if q in i["ticker"] or q in i["name"].upper()
        ]
        return results[:10]

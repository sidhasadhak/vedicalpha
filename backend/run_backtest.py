#!/usr/bin/env python3
"""
run_backtest.py
Runs the Vyapar Ratna prediction engine against historical data
and reports accuracy for each ticker + horizon combination.

Usage:
  python3 run_backtest.py --tickers BANKNIFTY,NIFTY50,GOLD --years 3
  python3 run_backtest.py --tickers RELIANCE,TCS --horizons 1D,1W --days 180
"""

import argparse
import sys
import os

# Add backend directory to path
sys.path.insert(0, os.path.dirname(__file__))

from prediction_engine import PredictionEngine
from jyotish_engine import JyotishEngine

def run_backtest(tickers, horizons, days):
    jyotish   = JyotishEngine()
    predictor = PredictionEngine(jyotish)

    category_map = {
        "BANKNIFTY": "index", "NIFTY50": "index", "SENSEX": "index",
        "NIFTYMIDCAP": "index", "NIFTYIT": "index",
        "GOLD": "gold", "GOLDM": "gold",
        "SILVER": "silver", "SILVERM": "silver",
        "CRUDEOIL": "commodity", "NATURALGAS": "commodity",
        "COPPER": "commodity", "ZINC": "commodity",
        "ALUMINIUM": "commodity", "NICKEL": "commodity", "LEAD": "commodity",
        "WHEAT": "agri", "COTTON": "agri", "SOYBEAN": "agri",
        "SUGAR": "agri", "MUSTARD": "agri", "TURMERIC": "agri",
        "JEERA": "agri", "CHANA": "agri",
    }
    # Default: equity
    def get_category(ticker):
        return category_map.get(ticker.upper(), "equity")

    results = {}
    print(f"\n{'='*60}")
    print(f"  Vyapar Ratna AI — Backtest ({days} days)")
    print(f"{'='*60}")

    for ticker in tickers:
        cat = get_category(ticker)
        results[ticker] = {}
        for horizon in horizons:
            print(f"  Testing {ticker} ({cat}) / {horizon} ...", end="", flush=True)
            try:
                r = predictor.backtest(ticker=ticker, horizon=horizon, days=days, category=cat)
                acc = r.get("accuracy")
                n   = r.get("total_days_tested", 0)
                results[ticker][horizon] = {"accuracy": acc, "n": n, "raw": r}
                if acc is not None:
                    print(f" {acc:.1f}% ({n} days)")
                else:
                    print(f" N/A (insufficient data)")
            except Exception as e:
                print(f" ERROR: {e}")
                results[ticker][horizon] = {"accuracy": None, "n": 0, "error": str(e)}

    # Print summary table
    print(f"\n{'─'*60}")
    print(f"  ACCURACY SUMMARY")
    print(f"{'─'*60}")

    col_w = max(len(t) for t in tickers) + 2
    header = f"  {'Ticker':<{col_w}}" + "".join(f"  {h:>6}" for h in horizons)
    print(header)
    print(f"  {'─'*col_w}" + "".join("  ──────" for _ in horizons))

    for ticker in tickers:
        row = f"  {ticker:<{col_w}}"
        for horizon in horizons:
            acc = results[ticker].get(horizon, {}).get("accuracy")
            row += f"  {f'{acc:.1f}%':>6}" if acc is not None else f"  {'N/A':>6}"
        print(row)

    print(f"{'─'*60}")
    print()

    # Detect best performing ticker/horizon
    best_acc  = 0
    best_pair = None
    for ticker in tickers:
        for horizon in horizons:
            acc = results[ticker].get(horizon, {}).get("accuracy") or 0
            if acc > best_acc:
                best_acc  = acc
                best_pair = (ticker, horizon)

    if best_pair:
        print(f"  Best: {best_pair[0]} / {best_pair[1]} at {best_acc:.1f}% accuracy")

    print(f"\n  Note: Accuracy = correct directional calls / total valid days.")
    print(f"  'Correct' = prediction signal matches actual ±0.5% close-to-close move.")
    print(f"  Data source: yfinance historical closes (mock if unavailable).")
    print()

    return results

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Vyapar Ratna Backtest Runner")
    parser.add_argument("--tickers",  default="BANKNIFTY,NIFTY50,GOLD",
                        help="Comma-separated tickers")
    parser.add_argument("--horizons", default="1D,1W",
                        help="Comma-separated horizons")
    parser.add_argument("--days",     type=int, default=90,
                        help="Days of history to test")
    parser.add_argument("--years",    type=int, default=0,
                        help="Years of history (overrides --days if set)")
    args = parser.parse_args()

    tickers  = [t.strip().upper() for t in args.tickers.split(",")]
    horizons = [h.strip() for h in args.horizons.split(",")]
    days     = args.years * 365 if args.years > 0 else args.days

    run_backtest(tickers, horizons, days)

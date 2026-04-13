#!/usr/bin/env python3
"""
run_backtest.py — VedicAlpha Enhanced Backtest Runner
======================================================
Runs all 6 Vedic engines against historical price data, reports per-engine
accuracy, compares against current rule_weights.json, and suggests revised
weights based on empirical performance.

Usage:
  python3 run_backtest.py                                  # default: 2 years, key tickers
  python3 run_backtest.py --tickers GOLD,SILVER --years 2
  python3 run_backtest.py --tickers BANKNIFTY --horizons 1D,1W --days 730
  python3 run_backtest.py --years 2 --save                 # save JSON report
  python3 run_backtest.py --tickers GOLD --years 3 --horizons 1D,1W,1M

Random directional baseline = 33.3%  (3-class: bull / bear / neutral)
Correct = prediction signal matches actual ±0.5% close-to-close move
"""

import argparse
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))

from prediction_engine import PredictionEngine
from jyotish_engine import JyotishEngine

# ── Constants ─────────────────────────────────────────────────────────────────

BASELINE      = 33.3   # random 3-class directional accuracy
ENGINE_LABELS = {
    "vyapar_ratna": "Vyapar Ratna",
    "bhavartha":    "Bhavartha Ratna.",
    "kalamrita":    "Uttara Kalamrita",
    "prasna":       "Prasna Marga",
    "brihat":       "Brihat Samhita",
    "mundane":      "Mediniya Jyotish",
}
CATEGORY_MAP = {
    "BANKNIFTY":  "index",   "NIFTY50":    "index",   "SENSEX":     "index",
    "NIFTYMIDCAP":"index",   "NIFTYIT":    "index",
    "GOLD":       "gold",    "GOLDM":      "gold",
    "SILVER":     "silver",  "SILVERM":    "silver",
    "CRUDEOIL":   "commodity","NATURALGAS":"commodity","COPPER":     "commodity",
    "ZINC":       "commodity","ALUMINIUM":  "commodity","NICKEL":    "commodity",
    "WHEAT":      "agri",    "COTTON":     "agri",    "SOYBEAN":    "agri",
    "SUGAR":      "agri",    "MUSTARD":    "agri",    "TURMERIC":   "agri",
    "JEERA":      "agri",    "CHANA":      "agri",
}

def get_category(ticker: str) -> str:
    return CATEGORY_MAP.get(ticker.upper(), "equity")


# ── Weight suggestion algorithm ───────────────────────────────────────────────

def suggest_weights(engine_acc: dict, horizon: str) -> dict:
    """
    Derive empirically-informed Vedic weight suggestions.

    Logic:
      lift[E] = accuracy[E] - BASELINE        (how much above random)
      Engines with positive lift contribute proportionally.
      Engines at/below random get a floor weight (0.02) so they aren't
      silenced entirely — the sample may be too short to judge them.
      Slow-planet engines (brihat, mundane) are not penalised at 1D/1W
      because they are not designed for short horizons.
    """
    SLOW = {"brihat", "mundane"}
    all_engines = list(ENGINE_LABELS.keys())

    lifts = {}
    for eng in all_engines:
        acc = engine_acc.get(eng)
        if acc is None or (eng == "prasna" and horizon in ("1M", "3M")):
            lifts[eng] = 0.0
            continue
        lift = acc - BASELINE
        # Don't punish slow engines for underperforming at short horizons
        if lift < 0 and eng in SLOW and horizon in ("1D", "1W"):
            lift = max(lift * 0.25, -1.0)
        lifts[eng] = lift

    # Floor negatives at 0.02 (min non-zero weight)
    raw = {e: max(0.02, lifts[e]) for e in all_engines}
    if horizon in ("1M", "3M"):
        raw["prasna"] = 0.0

    total = sum(raw.values()) or 1.0
    return {e: round(raw[e] / total, 4) for e in all_engines}


# ── Formatting helpers ────────────────────────────────────────────────────────

def bar(pct: float | None, width: int = 20) -> str:
    """ASCII accuracy bar. BASELINE marked with |."""
    if pct is None:
        return " " * width + " N/A"
    filled = int(round(pct / 100 * width))
    base_pos = int(round(BASELINE / 100 * width))
    b = list(" " * width)
    for i in range(min(filled, width)):
        b[i] = "█"
    if 0 <= base_pos < width:
        b[base_pos] = "|"   # baseline marker
    lift = pct - BASELINE
    sign = "+" if lift >= 0 else ""
    return "".join(b) + f"  {pct:5.1f}%  ({sign}{lift:.1f}pp)"


def delta_str(suggested: float, current: float) -> str:
    d = suggested - current
    if abs(d) < 0.005:
        return "  ——"
    return f"  {'▲' if d > 0 else '▼'} {abs(d)*100:.1f}pp"


# ── Core runner ───────────────────────────────────────────────────────────────

def run_backtest(tickers: list[str], horizons: list[str], days: int,
                 save: bool = False,
                 update_indicator_weights: bool = False) -> dict:

    jyotish   = JyotishEngine()
    predictor = PredictionEngine(jyotish)

    weights_path = os.path.join(os.path.dirname(__file__), "rule_weights.json")
    with open(weights_path) as f:
        rule_weights = json.load(f)
    # New 2D weight table — show current values for the reference horizon/category
    current_2d_weights = rule_weights.get("weights", {})

    all_results: dict = {}
    suggestions_by_horizon: dict = {}   # horizon → ticker-averaged Vedic weight suggestions
    # Per-ticker indicator accuracy: {ticker: {indicator_key: accuracy_pct}}
    ticker_indicator_results: dict = {}

    W = 70
    print(f"\n{'═'*W}")
    print(f"  VedicAlpha — Enhanced Backtest  ({days} days ≈ {days//365} yr {days%365} d)")
    print(f"  Tickers : {', '.join(tickers)}")
    print(f"  Horizons: {', '.join(horizons)}")
    print(f"  Baseline: {BASELINE}% (random 3-class direction)")
    print(f"  Correct = signal matches actual ±0.5% close-to-close")
    print(f"{'═'*W}\n")

    for ticker in tickers:
        cat = get_category(ticker)
        all_results[ticker] = {}

        for horizon in horizons:
            print(f"  ── {ticker} ({cat.upper()}) / {horizon} ", end="", flush=True)

            try:
                r = predictor.backtest(
                    ticker=ticker, horizon=horizon,
                    days=days, category=cat, verbose=False
                )
            except Exception as e:
                print(f"ERROR: {e}")
                all_results[ticker][horizon] = {"error": str(e)}
                continue

            if r.get("accuracy") is None:
                print("  ✗ no price data")
                all_results[ticker][horizon] = r
                continue

            n = r["total_days_tested"]
            print(f"  {n} windows tested")
            all_results[ticker][horizon] = r

            # ── Composite accuracy ────────────────────────────────────────────
            print(f"\n  Composite (6 engines)  {bar(r['accuracy'])}")

            # ── Per-engine accuracy ───────────────────────────────────────────
            eng_acc = r.get("engine_accuracy", {})
            print(f"\n  Per-engine breakdown:")
            for eng, label in ENGINE_LABELS.items():
                if eng == "prasna" and horizon in ("1M", "3M"):
                    continue
                acc = eng_acc.get(eng)
                print(f"    {label:<22}  {bar(acc)}")

            # ── Vedic weight comparison (2D table: current values for this horizon/cat) ──
            cur_w = current_2d_weights.get(horizon, {}).get(cat, {})
            sug_w = suggest_weights(eng_acc, horizon)

            # Accumulate suggested weights across tickers for this horizon
            if horizon not in suggestions_by_horizon:
                suggestions_by_horizon[horizon] = {e: [] for e in ENGINE_LABELS}
            for eng in ENGINE_LABELS:
                suggestions_by_horizon[horizon][eng].append(sug_w.get(eng, 0.0))

            print(f"\n  Vedic weight comparison  (current [{cat}] → suggested | Δ):")
            print(f"    {'Engine':<22}  {'Current':>8}  {'Suggested':>9}  {'Δ':>8}")
            print(f"    {'─'*22}  {'─'*8}  {'─'*9}  {'─'*8}")
            for eng, label in ENGINE_LABELS.items():
                if eng == "prasna" and horizon in ("1M", "3M"):
                    print(f"    {label:<22}  {'0.00':>8}  {'0.00':>9}  {'——':>8}")
                    continue
                c = cur_w.get(eng, 0.0)
                s = sug_w.get(eng, 0.0)
                print(f"    {label:<22}  {c:>8.4f}  {s:>9.4f}  {delta_str(s,c):>8}")
            print(f"    {'Technical (fixed)':22}  {cur_w.get('technical', 0.0):>8.4f}")

            # ── Per-indicator technical backtest ───────────────────────────────
            if update_indicator_weights and "1D" in horizons:
                print(f"\n  Technical indicator backtest  ({ticker} / {horizon})")
                try:
                    ir = predictor.backtest_technical(
                        ticker=ticker, horizon=horizon,
                        days=days, category=cat, verbose=False
                    )
                    ind_acc = ir.get("indicator_accuracy", {})
                    sug_ind = ir.get("suggested_weights", {})
                    if ind_acc:
                        print(f"    {'Indicator':<20}  {'Accuracy':>10}  {'Suggested W':>12}")
                        print(f"    {'─'*20}  {'─'*10}  {'─'*12}")
                        for ind_key, acc in sorted(ind_acc.items()):
                            acc_str = f"{acc:.1f}%" if acc is not None else "N/A"
                            sug_str = f"{sug_ind.get(ind_key, 1.0):.2f}"
                            print(f"    {ind_key:<20}  {acc_str:>10}  {sug_str:>12}")
                        if ticker not in ticker_indicator_results:
                            ticker_indicator_results[ticker] = {}
                        ticker_indicator_results[ticker][horizon] = ir
                except Exception as e:
                    print(f"    ERROR in technical backtest: {e}")

            print()

    # ── Cross-ticker summary table ────────────────────────────────────────────
    print(f"\n{'─'*W}")
    print("  ACCURACY SUMMARY  (composite 6-engine Jyotish)")
    print(f"{'─'*W}")
    col_w = max(len(t) for t in tickers) + 2
    header = f"  {'Ticker':<{col_w}}" + "".join(f"  {h:>7}" for h in horizons)
    print(header)
    print(f"  {'─'*col_w}" + "".join("  ───────" for _ in horizons))
    for ticker in tickers:
        row = f"  {ticker:<{col_w}}"
        for h in horizons:
            acc = all_results.get(ticker, {}).get(h, {}).get("accuracy")
            if acc is None:
                row += f"  {'N/A':>7}"
            else:
                lift = acc - BASELINE
                sign = "+" if lift >= 0 else ""
                row += f"  {acc:>5.1f}%"
        print(row)
    print(f"{'─'*W}")

    # ── Averaged Vedic weight suggestions ────────────────────────────────────
    print(f"\n{'─'*W}")
    print("  VEDIC ENGINE WEIGHT SUGGESTIONS  (averaged across tested tickers)")
    print("  These are Vedic-only weights — update rule_weights.json per-category.")
    print(f"{'─'*W}")

    averaged_suggestions: dict = {}
    for horizon in horizons:
        if horizon not in suggestions_by_horizon:
            continue
        avg_w: dict = {}
        for eng in ENGINE_LABELS:
            vals = [v for v in suggestions_by_horizon[horizon][eng] if v > 0]
            avg_w[eng] = round(sum(vals) / len(vals), 4) if vals else 0.0
        # Re-normalise to sum to 1.0 (excluding prasna=0 slots)
        total = sum(avg_w.values()) or 1.0
        avg_w = {e: round(v / total, 4) for e, v in avg_w.items()}
        averaged_suggestions[horizon] = avg_w
        print(f"\n  Horizon: {horizon}  (Vedic-only relative weights — not absolute)")
        print(f"    {'Engine':<22}  {'Suggested':>9}")
        print(f"    {'─'*22}  {'─'*9}")
        for eng, label in ENGINE_LABELS.items():
            s = avg_w.get(eng, 0.0)
            print(f"    {label:<22}  {s:>9.4f}")

    # ── Per-indicator weight update ───────────────────────────────────────────
    if update_indicator_weights and ticker_indicator_results:
        print(f"\n{'─'*W}")
        print("  INDICATOR WEIGHT UPDATE")
        print(f"{'─'*W}")

        ind_weights_path = os.path.join(os.path.dirname(__file__), "ticker_indicator_weights.json")
        with open(ind_weights_path) as f:
            current_ind_weights = json.load(f)

        # Average suggested weights across horizons for each ticker
        for ticker, horizon_data in ticker_indicator_results.items():
            merged: dict[str, list[float]] = {}
            for h, data in horizon_data.items():
                for ind_key, w in data.get("suggested_weights", {}).items():
                    merged.setdefault(ind_key, []).append(w)
            if not merged:
                continue
            avg_ind: dict[str, float] = {k: round(sum(v)/len(v), 2) for k, v in merged.items()}
            current_ind_weights[ticker] = {"_updated": datetime.now().strftime("%Y-%m-%d"), **avg_ind}
            print(f"\n  {ticker}:")
            for k, v in sorted(avg_ind.items()):
                print(f"    {k:<22}  → {v:.2f}")

        with open(ind_weights_path, "w") as f:
            json.dump(current_ind_weights, f, indent=2)
        print(f"\n  Saved → {ind_weights_path}")
        print(f"{'─'*W}")

    print(f"\n{'═'*W}")
    print("  Notes:")
    print("  • Vedic suggestions are directional. 1D data can't judge Brihat/Mundane.")
    print("  • Indicator weights: floor 0.2 (not 0) to avoid silencing on short data.")
    print("  • Re-run with --update-indicator-weights to refresh ticker_indicator_weights.json")
    print("  • Technical analysis NOT included in Vedic backtest — only in --update-indicator-weights")
    print(f"{'═'*W}\n")

    report = {
        "generated_at":   datetime.now().isoformat(),
        "days_tested":    days,
        "tickers":        tickers,
        "horizons":       horizons,
        "results":        all_results,
        "vedic_weight_suggestions": averaged_suggestions,
        "indicator_results": ticker_indicator_results,
        "methodology": {
            "correct_definition": "signal == actual ±0.5% close-to-close",
            "classification":     "3-class: bull (>+0.5%) / bear (<-0.5%) / neutral",
            "random_baseline":    f"{BASELINE}%",
            "vedic_mode":         "jyotish (all 6 Vedic engines, no technical)",
            "technical_mode":     "per-indicator OHLC backtest (requires --update-indicator-weights)",
            "price_source":       "yfinance historical closes",
        },
    }

    if save:
        out_path = os.path.join(os.path.dirname(__file__), "backtest_results.json")
        with open(out_path, "w") as f:
            json.dump(report, f, indent=2, default=str)
        print(f"  Saved full results → {out_path}\n")

    return report


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="VedicAlpha Enhanced Backtest Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--tickers",
        default="BANKNIFTY,NIFTY50,GOLD,SILVER,CRUDEOIL",
        help="Comma-separated tickers (default: BANKNIFTY,NIFTY50,GOLD,SILVER,CRUDEOIL)",
    )
    parser.add_argument(
        "--horizons",
        default="1D,1W",
        help="Comma-separated horizons (default: 1D,1W)",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=0,
        help="Days of history to test (overridden by --years)",
    )
    parser.add_argument(
        "--years",
        type=float,
        default=2.0,
        help="Years of history to test (default: 2.0)",
    )
    parser.add_argument(
        "--save",
        action="store_true",
        help="Save full JSON report to backtest_results.json",
    )
    parser.add_argument(
        "--update-indicator-weights",
        action="store_true",
        help=(
            "Run per-indicator technical backtest and write results to "
            "ticker_indicator_weights.json. Adds significant runtime."
        ),
    )
    args = parser.parse_args()

    tickers  = [t.strip().upper() for t in args.tickers.split(",")]
    horizons = [h.strip() for h in args.horizons.split(",")]
    days     = args.days if args.days > 0 else int(args.years * 365)

    run_backtest(tickers, horizons, days,
                 save=args.save,
                 update_indicator_weights=args.update_indicator_weights)

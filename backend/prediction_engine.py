"""
prediction_engine.py
Combines 6 Vedic engine signals with technical indicators to produce a final prediction.

6 Vedic engines (weights from rule_weights.json):
  1. Vyapar Ratna        — Vaar, Tithi, Sankranti rules
  2. Prasna Marga        — Horary/Gochara for query moment
  3. Bhavartha Ratnakara — Dhanayoga, Rajayoga, Maraka
  4. Uttara Kalamrita    — Karakatvas, Vimshottari Dasa
  5. Brihat Samhita      — Jupiter/Saturn/eclipse transits
  6. Mediniya Jyotish    — Samvatsara, Ritu, seasonal cycles

Technical analysis is a separate 7th channel weighted by category.
"""

import json
import math
import random
import os
from datetime import date, timedelta
from jyotish_engine import JyotishEngine
from bhavartha_engine import BhavarthaEngine
from kalamrita_engine import KalamritaEngine
from prasna_engine import PrasnaEngine
from brihat_engine import BrihatEngine
from mundane_engine import MundaneEngine

# ── Load weights from rule_weights.json ──────────────────────────────────────
_WEIGHTS_FILE = os.path.join(os.path.dirname(__file__), "rule_weights.json")
with open(_WEIGHTS_FILE) as _f:
    _RULE_WEIGHTS = json.load(_f)

HORIZON_VEDIC_WEIGHTS  = _RULE_WEIGHTS["horizon_weights"]
CATEGORY_TECH_WEIGHT   = _RULE_WEIGHTS["category_technical_weight"]

# Days lookup per horizon
HORIZON_DAYS = {"1D": 1, "1W": 7, "2W": 14, "1M": 30, "3M": 90}
# Keep backward-compat alias
HORIZON_WEIGHTS = {h: {"days": d} for h, d in HORIZON_DAYS.items()}

EXPECTED_MOVES = {
    "1D": "0.3–1.5%",  "1W": "1.0–3.5%",
    "2W": "2.0–6.0%",  "1M": "4.0–10%",  "3M": "8.0–20%",
}


class PredictionEngine:

    def __init__(self, jyotish: JyotishEngine):
        self.jyotish    = jyotish
        self.bhavartha  = BhavarthaEngine()
        self.kalamrita  = KalamritaEngine()
        self.prasna     = PrasnaEngine()
        self.brihat     = BrihatEngine()
        self.mundane    = MundaneEngine()

    def _resolve_weights(self, category: str, horizon: str) -> dict:
        """
        Compute final engine weights for 6 Vedic engines + technical.

        The technical weight is fixed per category (CATEGORY_TECH_WEIGHT).
        The remaining (1 - tech_weight) is distributed among the 6 Vedic engines
        according to the horizon_weights from rule_weights.json.

        Keys returned: jyotish, prasna, bhavartha, kalamrita, brihat, mundane, technical
        """
        tech_w    = CATEGORY_TECH_WEIGHT.get(category, 0.40)
        vedic_tot = 1.0 - tech_w

        h_weights = HORIZON_VEDIC_WEIGHTS.get(horizon, HORIZON_VEDIC_WEIGHTS["1W"])
        engine_keys = ["vyapar_ratna", "prasna", "bhavartha", "kalamrita", "brihat", "mundane"]

        # Normalise horizon weights (in case they don't sum to 1.0 exactly)
        h_sum = sum(h_weights.get(k, 0.0) for k in engine_keys)
        if h_sum == 0:
            h_sum = 1.0

        resolved = {}
        for k in engine_keys:
            resolved[k] = round(vedic_tot * h_weights.get(k, 0.0) / h_sum, 4)
        # jyotish alias for backward compat (Vyapar Ratna)
        resolved["jyotish"] = resolved["vyapar_ratna"]
        resolved["technical"] = round(tech_w, 4)
        return resolved

    def predict(self, ticker: str, category: str, horizon: str,
                mode: str, panchanga: dict, price_data: dict) -> dict:

        weights     = self._resolve_weights(category, horizon)
        factors     = []
        total_score = 0.0

        # ── Build unified kpanch dict for all Vedic engines ───────────────────
        # Normalise vaar string (e.g. "Ravivaar (Sun)") → index 0–6
        _vaar_map = {
            "sun":0, "ravi":0, "rav":0,
            "mon":1, "som":1,
            "tue":2, "man":2,
            "wed":3, "bud":3,
            "thu":4, "gur":4,
            "fri":5, "shu":5,
            "sat":6, "sha":6,
        }
        _vaar_raw = str(panchanga.get("vaar", "")).lower()
        _vaar_idx = next((v for k, v in _vaar_map.items() if _vaar_raw.startswith(k)), 0)
        kpanch = {
            "vaar_idx":  _vaar_idx,
            "tithi_num": panchanga.get("tithi", {}).get("number",
                         panchanga.get("tithi_num", 1)),
            "paksha":    panchanga.get("tithi", {}).get("paksha",
                         panchanga.get("paksha", "shukla")),
            "moon_age":  panchanga.get("tithi", {}).get("moon_age",
                         panchanga.get("moon_age", 0.0)),
            "sankranti": panchanga.get("sankranti", ""),
            "category":  category,
            "horizon":   horizon,
        }

        # ── JYOTISH SIGNALS ───────────────────────────────────────────────────
        if mode in ("both", "jyotish"):
            jyotish_signals = self.jyotish.get_all_signals(panchanga, category)

            # 1. Vaar factor
            vs = jyotish_signals["vaar"]
            vaar_score = vs["signal"] * vs["reliability"]
            factors.append({
                "name":        f"Vaar — {vs['vaar']}",
                "signal":      self._score_to_signal(vs["signal"]),
                "score":       round(vaar_score, 2),
                "confidence":  round(vs["reliability"] * 100),
                "description": vs["note"],
                "duration":    vs["duration"],
                "source":      "Vyapar Ratna · Vaar rules",
            })
            total_score += vaar_score * weights["jyotish"]

            # 2. Tithi factor
            ts = jyotish_signals["tithi"]
            tithi_score = ts["signal"] * 0.65
            factors.append({
                "name":        f"Tithi — {panchanga['tithi']['paksha'].title()} Paksha {panchanga['tithi']['name']}",
                "signal":      self._score_to_signal(ts["signal"]),
                "score":       round(tithi_score, 2),
                "confidence":  62,
                "description": ts["note"] if ts["note"] else "Neutral Tithi — no strong commodity signal for this period.",
                "source":      "Vyapar Ratna · Tithi rules",
            })
            total_score += tithi_score * weights["jyotish"] * 0.8

            # 3. Sankranti factor
            ss = jyotish_signals["sankranti"]
            sankranti_score = ss["signal"] * 0.55
            factors.append({
                "name":        f"Sankranti — {panchanga['sankranti']}",
                "signal":      self._score_to_signal(ss["signal"]),
                "score":       round(sankranti_score, 2),
                "confidence":  58,
                "description": ss["note"],
                "tezi_items":  ss["tezi"],
                "mandi_items": ss["mandi"],
                "source":      "Vyapar Ratna · Sankranti rules",
            })
            total_score += sankranti_score * weights["jyotish"] * 0.7

            # 4. Special five-weekday rule
            if panchanga["five_thursday"]:
                factors.append({
                    "name":        "Five-Thursday month",
                    "signal":      "bear",
                    "score":       -0.3,
                    "confidence":  55,
                    "description": "Vyapar Ratna: Five Thursdays this month — Western markets may see instability. Rasa/chemicals tezi. Other commodities volatile.",
                    "source":      "Vyapar Ratna · Vaar special rules",
                })
                total_score -= 0.3 * weights["jyotish"]

            if panchanga["five_saturday"]:
                factors.append({
                    "name":        "Five-Saturday month",
                    "signal":      "bull",
                    "score":       0.4,
                    "confidence":  58,
                    "description": "Vyapar Ratna: Five Saturdays — every commodity shows tezi at some point this month.",
                    "source":      "Vyapar Ratna · Vaar special rules",
                })
                total_score += 0.4 * weights["jyotish"]

        # ── BHAVARTHA RATNAKARA SIGNALS ───────────────────────────────────────
        if mode in ("both", "jyotish"):
            bsigs = self.bhavartha.get_bhavartha_signals(panchanga)

            # 1. Dhanayoga / Nirdhana
            ds = bsigs["dhanayoga"]
            factors.append({
                "name":        f"Dhanayoga — {panchanga['tithi']['paksha'].title()} {panchanga['tithi']['name']}",
                "signal":      self._score_to_signal(ds["signal"]),
                "score":       round(ds["score"], 2),
                "confidence":  ds["confidence"],
                "description": ds["note"],
                "source":      ds["source"],
            })
            total_score += ds["score"] * weights["bhavartha"] * 0.90

            # 2. Rajayoga
            rs = bsigs["rajayoga"]
            factors.append({
                "name":        f"Rajayoga — {panchanga['sankranti']} / Moon {panchanga['tithi']['moon_age']:.0f}d",
                "signal":      self._score_to_signal(rs["signal"]),
                "score":       round(rs["score"], 2),
                "confidence":  rs["confidence"],
                "description": rs["note"],
                "source":      rs["source"],
            })
            total_score += rs["score"] * weights["bhavartha"] * 0.85

            # 3. Maraka (loss) — inverted contribution: negative score → bear
            ms = bsigs["maraka"]
            if ms["signal"] != 0:
                factors.append({
                    "name":        "Maraka — Loss Combination",
                    "signal":      "bear",
                    "score":       round(ms["score"], 2),
                    "confidence":  ms["confidence"],
                    "description": ms["note"],
                    "source":      ms["source"],
                })
                total_score += ms["score"] * weights["bhavartha"] * 1.10  # Marakas weighted heavier

            # 4. Dasa result
            das = bsigs["dasa"]
            factors.append({
                "name":        f"Dasa — {das.get('planet','?')} Period",
                "signal":      self._score_to_signal(das["signal"]),
                "score":       round(das["score"], 2),
                "confidence":  das["confidence"],
                "description": das["note"],
                "source":      das["source"],
            })
            total_score += das["score"] * weights["bhavartha"] * 0.80

            # 5. Malika yoga
            mal = bsigs["malika"]
            factors.append({
                "name":        f"Malika Yoga — {mal.get('yoga_name','?')} (Bhava {mal.get('bhava','?')})",
                "signal":      self._score_to_signal(mal["signal"]),
                "score":       round(mal["score"], 2),
                "confidence":  mal["confidence"],
                "description": mal["note"],
                "source":      mal["source"],
            })
            total_score += mal["score"] * weights["bhavartha"] * 0.75

        # ── UTTARA KALAMRITA SIGNALS ──────────────────────────────────────────
        if mode in ("both", "jyotish"):
            # kpanch is built once at top of predict() and reused by all engines
            ksigs = self.kalamrita.get_kalamrita_signals(kpanch)

            # 1. Karakatva (planet significator alignment)
            ks = ksigs["karakatva"]
            ks_score = ks["score"] - 0.50  # centre around 0
            factors.append({
                "name":        f"Karakatva — {ks['note'].split('—')[0].strip()}",
                "signal":      ks["signal"],
                "score":       round(ks_score, 2),
                "confidence":  60,
                "description": ks["note"],
                "source":      "Uttara Kalamrita · Ch V (Karakatvas)",
            })
            total_score += ks_score * weights["kalamrita"] * 0.90

            # 2. Dhana Yoga (Ch IV)
            dys = ksigs["dhana_yoga"]
            dys_score = dys["score"] - 0.50
            factors.append({
                "name":        "Dhana Yoga — Kalamrita",
                "signal":      dys["signal"],
                "score":       round(dys_score, 2),
                "confidence":  65,
                "description": dys["note"],
                "source":      "Uttara Kalamrita · Ch IV (Dhana Yoga)",
            })
            total_score += dys_score * weights["kalamrita"] * 0.95

            # 3. Viparita Rajayoga (Ch IV — contrarian recovery signal)
            vrs = ksigs["viparita_raja"]
            vrs_score = vrs["score"] - 0.50
            if abs(vrs_score) > 0.05:   # only append if it has real signal
                factors.append({
                    "name":        "Viparita Rajayoga",
                    "signal":      vrs["signal"],
                    "score":       round(vrs_score, 2),
                    "confidence":  50,
                    "description": vrs["note"],
                    "source":      "Uttara Kalamrita · Ch IV (Viparita Rajayoga)",
                })
                total_score += vrs_score * weights["kalamrita"] * 0.60

            # 4. Vimshottari Dasa / antardasa timing (Ch VI)
            das2 = ksigs["dasa_antardasa"]
            das2_score = das2["score"] - 0.50
            factors.append({
                "name":        f"Dasa Timing — {das2.get('maha_planet','?').title()}/{das2.get('antar_planet','?').title()}",
                "signal":      das2["signal"],
                "score":       round(das2_score, 2),
                "confidence":  45,
                "description": das2["note"],
                "source":      "Uttara Kalamrita · Ch VI (Vimshottari Dasa)",
            })
            total_score += das2_score * weights["kalamrita"] * 0.75

            # 5. Prashna (Ch VII)
            # NOTE: Prashna is intentionally NOT folded into total_score.
            # It answers "what happens to this specific query right now" —
            # orthogonal to general market direction. Kept in factors list
            # for display only, tagged so the frontend can handle separately.
            ps = ksigs["prashna"]
            ps_score = ps["score"] - 0.50
            factors.append({
                "name":        f"Prashna — {ps.get('day_planet','?').title()} Vaar Query",
                "signal":      ps["signal"],
                "score":       round(ps_score, 2),
                "confidence":  55,
                "description": (
                    "⏱ Cast for this moment's query. "
                    + ps["note"]
                    + " — Prashna reflects your query's outcome, not overall market direction."
                ),
                "source":      "Uttara Kalamrita · Ch VII (Prashna/Horary)",
                "is_prashna":  True,   # frontend flag: render separately
            })

        # ── PRASNA MARGA SIGNALS (B.V. Raman) ────────────────────────────────
        if mode in ("both", "jyotish") and weights.get("prasna", 0) > 0:
            pm_sigs = self.prasna.get_prasna_signals(kpanch, category)
            pm_composite_score = pm_sigs["score"]
            # Add sub-signals as individual factors (first 4 most significant)
            sub_sigs = pm_sigs.get("sub_signals", [])
            for sub in sub_sigs[:4]:
                factors.append({
                    "name":        sub["name"],
                    "signal":      sub["signal"],
                    "score":       round(sub["score"], 2),
                    "confidence":  sub.get("confidence", 60),
                    "description": sub["description"],
                    "source":      "Prasna Marga · " + sub.get("source", "B.V. Raman"),
                    "is_prashna":  True,
                })
            total_score += pm_composite_score * weights["prasna"]

        # ── BRIHAT SAMHITA SIGNALS (Varahamihira) ─────────────────────────────
        if mode in ("both", "jyotish") and weights.get("brihat", 0) > 0:
            bs_sigs = self.brihat.get_brihat_signals(kpanch, category)
            bs_composite_score = bs_sigs["score"]
            for sub in bs_sigs.get("sub_signals", []):
                factors.append({
                    "name":        sub["name"],
                    "signal":      sub["signal"],
                    "score":       round(sub["score"], 2),
                    "confidence":  sub.get("confidence", 65),
                    "description": sub["description"],
                    "source":      "Brihat Samhita · " + sub.get("source", "Varahamihira"),
                })
            total_score += bs_composite_score * weights["brihat"]

        # ── MEDINIYA JYOTISH SIGNALS (Mundane) ────────────────────────────────
        if mode in ("both", "jyotish") and weights.get("mundane", 0) > 0:
            mu_sigs = self.mundane.get_mundane_signals(kpanch, category)
            mu_composite_score = mu_sigs["score"]
            for sub in mu_sigs.get("sub_signals", []):
                factors.append({
                    "name":        sub["name"],
                    "signal":      sub["signal"],
                    "score":       round(sub["score"], 2),
                    "confidence":  sub.get("confidence", 60),
                    "description": sub["description"],
                    "source":      "Mediniya Jyotish · " + sub.get("source", "Mundane"),
                })
            total_score += mu_composite_score * weights["mundane"]

        # ── TECHNICAL SIGNALS ─────────────────────────────────────────────────
        if mode in ("both", "technical"):
            tech = self._compute_technical(price_data, horizon, category)

            # Each indicator contributes equally within the technical weight
            tech_indicators = [
                ("rsi",         tech["rsi_score"],         tech["rsi_signal"],         tech["rsi_note"],         f"RSI-14 ({tech['rsi']})"),
                ("macd",        tech["macd_score"],        tech["macd_signal"],        tech["macd_note"],        f"MACD ({tech['macd_label']})"),
                ("supertrend",  tech["st_score"],          tech["st_signal"],          tech["st_note"],          f"Supertrend ({tech['st_label']})"),
                ("bollinger",   tech["bb_score"],          tech["bb_signal"],          tech["bb_note"],          f"Bollinger Bands ({tech['bb_label']})"),
                ("adx",         tech["adx_score"],         tech["adx_signal"],         tech["adx_note"],         f"ADX ({tech['adx']})"),
                ("india_vix",   tech["vix_score"],         tech["vix_signal"],         tech["vix_note"],         f"India VIX ({tech['vix']})"),
            ]
            if tech.get("pcr_score") is not None:
                tech_indicators.append(
                    ("pcr", tech["pcr_score"], tech["pcr_signal"], tech["pcr_note"], f"Put-Call Ratio ({tech['pcr']})")
                )
            if tech.get("ratio_score") is not None:
                tech_indicators.append(
                    ("ratio", tech["ratio_score"], tech["ratio_signal"], tech["ratio_note"], tech["ratio_label"])
                )
            # Price action indicators — always present when OHLC available
            if tech.get("candle_score") is not None:
                tech_indicators.append(
                    ("candle", tech["candle_score"], tech["candle_signal"], tech["candle_note"], f"Candle Pattern ({tech['candle_label']})")
                )
            if tech.get("ema_score") is not None:
                tech_indicators.append(
                    ("ema", tech["ema_score"], tech["ema_signal"], tech["ema_note"], f"EMA Positioning ({tech['ema_label']})")
                )
            if tech.get("pivot_score") is not None:
                tech_indicators.append(
                    ("pivot", tech["pivot_score"], tech["pivot_signal"], tech["pivot_note"], f"Pivot Points ({tech['pivot_label']})")
                )

            n = len(tech_indicators)
            tech_total = 0.0
            for _, score, signal, note, name in tech_indicators:
                factors.append({
                    "name":        name,
                    "signal":      signal,
                    "score":       round(score, 2),
                    "confidence":  round(tech["confidence"]),
                    "description": note,
                    "source":      "Technical analysis",
                })
                tech_total += score

            total_score += (tech_total / n) * weights["technical"] * n / 2

        # ── FINAL VERDICT ─────────────────────────────────────────────────────
        signal     = "bull" if total_score > 0.25 else "bear" if total_score < -0.25 else "neutral"
        confidence = min(93, max(42, int(50 + abs(total_score) * 22)))

        bull_count    = sum(1 for f in factors if f["signal"] == "bull")
        bear_count    = sum(1 for f in factors if f["signal"] == "bear")
        neutral_count = sum(1 for f in factors if f["signal"] == "neutral")

        # ── Signal alignment filter ────────────────────────────────────────────
        # Count how many distinct Vedic engines agree on the main direction.
        # Engines tracked: jyotish(VR), bhavartha, kalamrita, prasna, brihat, mundane
        # If fewer than 3 agree → cap confidence at 55%, flag mixed_signals.
        _engine_signals = []
        _non_prashna = [f for f in factors if not f.get("is_prashna")]
        engine_source_map = {
            "Vyapar Ratna": "bull" if total_score > 0 else "bear",  # approximation
        }
        # Score each named engine block by collecting their factor signals
        _vr_sigs     = [f["signal"] for f in _non_prashna if "Vyapar Ratna" in f.get("source","") or "Sankranti" in f.get("name","") or "Vaar" in f.get("name","") or "Tithi" in f.get("name","")]
        _bh_sigs     = [f["signal"] for f in _non_prashna if "Bhavartha" in f.get("source","")]
        _ka_sigs     = [f["signal"] for f in _non_prashna if "Kalamrita" in f.get("source","")]
        _bs_sigs     = [f["signal"] for f in _non_prashna if "Brihat" in f.get("source","")]
        _mu_sigs     = [f["signal"] for f in _non_prashna if "Mediniya" in f.get("source","")]
        _pm_sigs     = [f["signal"] for f in factors if f.get("is_prashna") and "Prasna Marga" in f.get("source","")]
        _ta_sigs     = [f["signal"] for f in _non_prashna if "Technical" in f.get("source","") or "technical" in f.get("source","")]

        def _dominant(sigs: list) -> str | None:
            if not sigs: return None
            b = sigs.count("bull"); br = sigs.count("bear")
            if b > br: return "bull"
            if br > b: return "bear"
            return "neutral"

        engine_votes = [
            _dominant(_vr_sigs),
            _dominant(_bh_sigs),
            _dominant(_ka_sigs),
            _dominant(_bs_sigs),
            _dominant(_mu_sigs),
            _dominant(_ta_sigs),
        ]
        engines_agreeing = sum(1 for v in engine_votes if v == signal)
        mixed_signals = engines_agreeing < 3

        if mixed_signals and confidence > 55:
            confidence = 55

        return {
            "signal":        signal,
            "signal_label":  "Tezi ↑" if signal == "bull" else "Mandi ↓" if signal == "bear" else "Sama →",
            "confidence":    confidence,
            "score":         round(total_score, 3),
            "expected_move": EXPECTED_MOVES.get(horizon, "1–5%"),
            "mixed_signals": mixed_signals,
            "engines_agreeing": engines_agreeing,
            "factors":       factors,
            "factor_summary": {
                "bull":    bull_count,
                "bear":    bear_count,
                "neutral": neutral_count,
            },
            "engine_weights": {
                "vyapar_ratna": round(weights["vyapar_ratna"] * 100),
                "prasna":       round(weights.get("prasna", 0) * 100),
                "bhavartha":    round(weights["bhavartha"] * 100),
                "kalamrita":    round(weights["kalamrita"] * 100),
                "brihat":       round(weights.get("brihat", 0) * 100),
                "mundane":      round(weights.get("mundane", 0) * 100),
                "technical":    round(weights["technical"] * 100),
                "category":     category,
                "horizon":      horizon,
            },
            "chart_data":    self._build_chart_data(signal, horizon),
            "disclaimer":    "For educational purposes only. Not SEBI-registered financial advice.",
        }

    # ── Technical computation ──────────────────────────────────────────────────

    def _compute_technical(self, price_data: dict, horizon: str, category: str = "equity") -> dict:
        """
        Indian-market technical indicator suite:
          1. RSI-14           — momentum oscillator
          2. MACD (12/26/9)   — trend/momentum crossover
          3. Supertrend       — ATR-based trend filter (period=7, mult=3); very popular on NSE
          4. Bollinger Bands  — volatility envelope (20-period, 2σ)
          5. ADX-14           — trend strength (no direction)
          6. India VIX proxy  — market fear; fetched live or simulated
          7. Put-Call Ratio   — NSE options sentiment (index/equity only)
          8. Gold:Silver ratio — for MCX gold/silver category
        """
        closes = price_data.get("closes", [])
        highs  = price_data.get("highs",  [])
        lows   = price_data.get("lows",   [])
        live   = len(closes) >= 14

        # ── 1. RSI ────────────────────────────────────────────────────────────
        rsi       = self._calc_rsi(closes, 14) if live else round(40 + random.random() * 25, 1)
        rsi_score  = (rsi - 50) / 50
        rsi_signal = "bull" if rsi > 60 else "bear" if rsi < 40 else "neutral"
        rsi_note   = (
            f"RSI-14 at {rsi:.1f} — "
            + ("Overbought zone (>70). Profit-booking likely." if rsi > 70
               else "Oversold zone (<30). Bounce/reversal likely." if rsi < 30
               else "Neutral band (30–60). Wait for breakout confirmation." if rsi < 60
               else "Momentum building (60–70). Continuation probable.")
        )

        # ── 2. MACD ───────────────────────────────────────────────────────────
        macd_val   = self._calc_macd(closes) if live else random.uniform(-2, 2)
        # Normalise by price level so ₹-priced commodities don't saturate tanh
        _price_ref = closes[-1] if closes else 100.0
        _macd_norm = macd_val / (_price_ref * 0.01) if _price_ref > 0 else macd_val / 3
        macd_score  = math.tanh(_macd_norm)
        macd_signal = "bull" if macd_val > 0.3 else "bear" if macd_val < -0.3 else "neutral"
        macd_label  = f"{'+'if macd_val>=0 else ''}{macd_val:.2f}"
        macd_note   = (
            f"MACD {macd_label}: "
            + ("Positive crossover — bullish momentum confirmed." if macd_val > 0.5
               else "Negative crossover — bearish pressure." if macd_val < -0.5
               else "MACD near zero — sideways/consolidation phase.")
        )

        # ── 3. Supertrend (ATR-based, period=7, multiplier=3) ─────────────────
        # Very popular on NSE/MCX; used heavily by Indian retail traders.
        # Requires OHLC; falls back to close-only approximation.
        st_val, st_bull = self._calc_supertrend(closes, highs, lows)
        st_score  = 0.40 if st_bull else -0.40
        st_signal = "bull" if st_bull else "bear"
        st_label  = "Above ST (Bullish)" if st_bull else "Below ST (Bearish)"
        st_note   = (
            ("Price is above Supertrend line — uptrend active. Hold longs, buy dips." if st_bull
             else "Price is below Supertrend line — downtrend active. Hold shorts, sell rallies.")
            + " (7-period, 3× ATR multiplier)"
        )

        # ── 4. Bollinger Bands (20-period, 2σ) ────────────────────────────────
        bb_pct, bb_width = self._calc_bollinger(closes)
        if bb_pct > 0.85:
            bb_score, bb_signal = -0.35, "bear"
            bb_label = f"%B {bb_pct:.2f} (Near Upper)"
            bb_note  = f"Price near upper Bollinger Band (%B={bb_pct:.2f}). Overbought — mean reversion risk. Band width={bb_width:.1f}%."
        elif bb_pct < 0.15:
            bb_score, bb_signal = 0.35, "bull"
            bb_label = f"%B {bb_pct:.2f} (Near Lower)"
            bb_note  = f"Price near lower Bollinger Band (%B={bb_pct:.2f}). Oversold — bounce likely. Band width={bb_width:.1f}%."
        elif bb_width < 1.5:
            bb_score, bb_signal = 0.10, "neutral"
            bb_label = f"Squeeze (width={bb_width:.1f}%)"
            bb_note  = f"Bollinger Band squeeze detected (width={bb_width:.1f}%). Low volatility precedes sharp breakout — direction unclear."
        else:
            bb_score, bb_signal = 0.05, "neutral"
            bb_label = f"%B {bb_pct:.2f} (Mid)"
            bb_note  = f"Price in mid Bollinger Band range (%B={bb_pct:.2f}). No extreme signal."

        # ── 5. ADX-14 (trend strength) ────────────────────────────────────────
        # ADX measures trend strength, not direction. Used with Supertrend direction.
        adx = self._calc_adx(closes, highs, lows)
        if adx >= 35:
            adx_score  = 0.30 if st_bull else -0.30   # strong trend, ride it
            adx_signal = "bull" if st_bull else "bear"
            adx_note   = f"ADX {adx:.0f} — Strong trend (>35). {'Uptrend' if st_bull else 'Downtrend'} well-established. High-conviction move."
        elif adx >= 20:
            adx_score  = 0.15 if st_bull else -0.15
            adx_signal = "bull" if st_bull else "bear"
            adx_note   = f"ADX {adx:.0f} — Moderate trend (20–35). Trend developing, not yet mature."
        else:
            adx_score  = 0.0
            adx_signal = "neutral"
            adx_note   = f"ADX {adx:.0f} — Weak/no trend (<20). Range-bound market. Breakout indicators more useful than trend-followers."

        # ── 6. India VIX proxy ────────────────────────────────────────────────
        # India VIX = NSE volatility index. >20 = high fear, market likely to fall/whipsaw.
        # <13 = complacency, often precedes correction. 13–20 = normal.
        vix = self._fetch_india_vix()
        if vix > 22:
            vix_score, vix_signal = -0.45, "bear"
            vix_note = f"India VIX {vix:.1f} — High fear (>22). Elevated volatility; institutional hedging active. Bearish bias."
        elif vix > 17:
            vix_score, vix_signal = -0.15, "neutral"
            vix_note = f"India VIX {vix:.1f} — Elevated (17–22). Some uncertainty. Trade with tighter stops."
        elif vix < 12:
            vix_score, vix_signal = -0.20, "neutral"
            vix_note = f"India VIX {vix:.1f} — Very low (<12). Complacency warning. Markets calm but prone to sudden spike."
        else:
            vix_score, vix_signal = 0.20, "bull"
            vix_note = f"India VIX {vix:.1f} — Normal range (12–17). Healthy bull market environment."

        result = {
            "rsi": round(rsi, 1), "rsi_score": rsi_score, "rsi_signal": rsi_signal, "rsi_note": rsi_note,
            "macd_val": macd_val, "macd_score": macd_score, "macd_signal": macd_signal,
            "macd_label": macd_label, "macd_note": macd_note,
            "st_score": st_score, "st_signal": st_signal, "st_label": st_label, "st_note": st_note,
            "bb_score": bb_score, "bb_signal": bb_signal, "bb_label": bb_label, "bb_note": bb_note,
            "adx": round(adx, 1), "adx_score": adx_score, "adx_signal": adx_signal, "adx_note": adx_note,
            "vix": round(vix, 1), "vix_score": vix_score, "vix_signal": vix_signal, "vix_note": vix_note,
            "confidence": 65,
        }

        # ── 7. Put-Call Ratio (index/equity only) ─────────────────────────────
        # NSE PCR > 1.2 → excessive put buying → contrarian bullish.
        # PCR < 0.7  → excessive call buying → contrarian bearish.
        if category in ("index", "equity"):
            pcr = self._fetch_pcr()
            if pcr > 1.3:
                pcr_score, pcr_signal = 0.35, "bull"
                pcr_note = f"NSE Put-Call Ratio {pcr:.2f} — Extreme put-buying (>1.3). Contrarian BUY signal; market may have bottomed."
            elif pcr > 1.0:
                pcr_score, pcr_signal = 0.15, "bull"
                pcr_note = f"NSE Put-Call Ratio {pcr:.2f} — Moderate put bias (1.0–1.3). Slightly bullish contrarian signal."
            elif pcr < 0.65:
                pcr_score, pcr_signal = -0.35, "bear"
                pcr_note = f"NSE Put-Call Ratio {pcr:.2f} — Extreme call-buying (<0.65). Contrarian SELL signal; market may be topping."
            elif pcr < 0.85:
                pcr_score, pcr_signal = -0.15, "bear"
                pcr_note = f"NSE Put-Call Ratio {pcr:.2f} — Call bias (0.65–0.85). Slightly bearish contrarian signal."
            else:
                pcr_score, pcr_signal = 0.0, "neutral"
                pcr_note = f"NSE Put-Call Ratio {pcr:.2f} — Balanced options market (0.85–1.0). No extreme sentiment."
            result.update({
                "pcr": round(pcr, 2), "pcr_score": pcr_score,
                "pcr_signal": pcr_signal, "pcr_note": pcr_note,
            })

        # ── 8. Gold:Silver ratio (MCX gold/silver only) ───────────────────────
        if category in ("gold", "silver"):
            ratio = self._fetch_gold_silver_ratio()
            ratio_label = f"Gold:Silver Ratio {ratio:.0f}"
            if ratio > 85:
                ratio_score  = 0.30 if category == "silver" else -0.15
                ratio_signal = "bull" if category == "silver" else "neutral"
                ratio_note   = (f"Gold:Silver ratio at {ratio:.0f} (historically high >85). "
                                + ("Silver historically undervalued relative to gold — mean reversion bullish for silver." if category == "silver"
                                   else "Silver may outperform gold from here."))
            elif ratio < 70:
                ratio_score  = 0.25 if category == "gold" else -0.10
                ratio_signal = "bull" if category == "gold" else "neutral"
                ratio_note   = (f"Gold:Silver ratio at {ratio:.0f} (low <70). "
                                + ("Gold relatively undervalued — bullish for gold." if category == "gold"
                                   else "Gold may outperform silver from here."))
            else:
                ratio_score, ratio_signal = 0.0, "neutral"
                ratio_note = f"Gold:Silver ratio at {ratio:.0f} — within normal range (70–85). No extreme signal."
            result.update({
                "ratio": round(ratio, 1), "ratio_score": ratio_score,
                "ratio_signal": ratio_signal, "ratio_note": ratio_note,
                "ratio_label": ratio_label,
            })

        # ── 9. Price action — Candlestick patterns ────────────────────────────
        candle = self._detect_candle_pattern(closes, highs, lows,
                                             price_data.get("opens", []))
        result.update(candle)

        # ── 10. Price action — EMA positioning ───────────────────────────────
        ema_pa = self._calc_ema_positioning(closes)
        result.update(ema_pa)

        # ── 11. Price action — Pivot points ──────────────────────────────────
        pivot_pa = self._calc_pivot_points(closes, highs, lows)
        result.update(pivot_pa)

        return result

    # ── Individual indicator calculators ──────────────────────────────────────

    def _calc_rsi(self, closes: list, period: int = 14) -> float:
        if len(closes) < period + 1:
            return 50.0
        gains, losses = [], []
        for i in range(1, period + 1):
            d = closes[-i] - closes[-i - 1]
            (gains if d > 0 else losses).append(abs(d))
        avg_gain = sum(gains) / period if gains else 0
        avg_loss = sum(losses) / period if losses else 0
        if avg_loss == 0:
            return 100.0
        return round(100 - (100 / (1 + avg_gain / avg_loss)), 2)

    def _calc_macd(self, closes: list) -> float:
        def ema(data, n):
            k = 2 / (n + 1); e = data[0]
            for v in data[1:]: e = v * k + e * (1 - k)
            return e
        if len(closes) < 26:
            return 0.0
        return round(ema(closes[-12:], 12) - ema(closes[-26:], 26), 2)

    def _calc_supertrend(self, closes: list, highs: list, lows: list,
                         period: int = 7, mult: float = 3.0) -> tuple[float, bool]:
        """
        Supertrend: ATR-based trend indicator. Returns (last_supertrend_value, is_bullish).
        Falls back to a close-price momentum proxy when OHLC unavailable.
        """
        n = min(len(closes), len(highs), len(lows))
        if n < period + 1:
            # Proxy: if last close > SMA(closes), treat as bullish
            if len(closes) >= 5:
                sma = sum(closes[-5:]) / 5
                return sma, closes[-1] > sma
            return 0.0, random.random() > 0.5

        # True Range
        trs = []
        for i in range(1, n):
            tr = max(highs[i] - lows[i],
                     abs(highs[i] - closes[i-1]),
                     abs(lows[i]  - closes[i-1]))
            trs.append(tr)

        # ATR (simple average over period)
        atr = sum(trs[-period:]) / period

        # Basic upper/lower bands
        hl2 = (highs[-1] + lows[-1]) / 2
        upper = hl2 + mult * atr
        lower = hl2 - mult * atr

        # Simple Supertrend: bullish if close > midpoint band
        mid = (upper + lower) / 2
        is_bullish = closes[-1] > mid
        return round(mid, 2), is_bullish

    def _calc_bollinger(self, closes: list, period: int = 20, std_mult: float = 2.0) -> tuple[float, float]:
        """
        Returns (%B, band_width_pct).
        %B = (price - lower) / (upper - lower); 0=at lower, 1=at upper.
        """
        if len(closes) < period:
            return 0.5, 3.0
        window = closes[-period:]
        sma  = sum(window) / period
        std  = (sum((x - sma) ** 2 for x in window) / period) ** 0.5
        if std == 0:
            return 0.5, 0.0
        upper = sma + std_mult * std
        lower = sma - std_mult * std
        price = closes[-1]
        pct_b = (price - lower) / (upper - lower)
        width = (upper - lower) / sma * 100
        return round(min(max(pct_b, 0), 1), 3), round(width, 2)

    def _calc_adx(self, closes: list, highs: list, lows: list, period: int = 14) -> float:
        """
        Average Directional Index (ADX). Returns ADX value (0–100).
        Falls back to a volatility proxy when OHLC unavailable.
        """
        n = min(len(closes), len(highs), len(lows))
        if n < period + 2:
            # Proxy: use close-range volatility as trend-strength estimate
            if len(closes) >= 5:
                changes = [abs(closes[i] - closes[i-1]) / closes[i-1] * 100
                           for i in range(1, len(closes))]
                return round(min(sum(changes[-5:]) / 5 * 20, 50), 1)
            return round(15 + random.random() * 15, 1)

        def smooth(data, p):
            s = sum(data[:p])
            result = [s]
            for v in data[p:]:
                s = s - s / p + v
                result.append(s)
            return result

        plus_dm, minus_dm, trs = [], [], []
        for i in range(1, n):
            up   = highs[i]  - highs[i-1]
            down = lows[i-1] - lows[i]
            plus_dm.append(up   if up > down and up > 0   else 0)
            minus_dm.append(down if down > up and down > 0 else 0)
            tr = max(highs[i] - lows[i],
                     abs(highs[i] - closes[i-1]),
                     abs(lows[i]  - closes[i-1]))
            trs.append(tr)

        atr14  = smooth(trs, period)
        pdm14  = smooth(plus_dm, period)
        mdm14  = smooth(minus_dm, period)

        dx_vals = []
        for a, p, m in zip(atr14, pdm14, mdm14):
            if a == 0:
                continue
            pdi = 100 * p / a
            mdi = 100 * m / a
            if pdi + mdi == 0:
                continue
            dx_vals.append(100 * abs(pdi - mdi) / (pdi + mdi))

        if not dx_vals:
            return 20.0
        adx = sum(dx_vals[-period:]) / min(len(dx_vals), period)
        return round(adx, 1)

    def _fetch_india_vix(self) -> float:
        """
        Fetch India VIX from NSE. Falls back to a realistic simulated value.
        India VIX typically trades 10–30; normal range 12–18.
        """
        try:
            from nsepython import nse_get_index_data
            # India VIX is index symbol "INDIA VIX" on NSE
            data = nse_get_index_data("INDIA VIX")
            return float(data.get("last", 15.5))
        except Exception:
            pass
        try:
            import yfinance as yf
            hist = yf.Ticker("^INDIAVIX").history(period="2d")
            if not hist.empty:
                return round(float(hist["Close"].iloc[-1]), 2)
        except Exception:
            pass
        # Simulated: log-normal around 15 with realistic range
        return round(max(9.0, min(35.0, 14.5 + random.gauss(0, 2.5))), 1)

    def _fetch_pcr(self) -> float:
        """
        NSE Put-Call Ratio for index options. Typical range 0.6–1.4.
        Tries NSE OI data; falls back to simulation.
        """
        try:
            from nsepython import nse_optionchain_scrapper
            oc = nse_optionchain_scrapper("NIFTY")
            total_put_oi  = sum(r.get("PE", {}).get("openInterest", 0) for r in oc.get("records", {}).get("data", []))
            total_call_oi = sum(r.get("CE", {}).get("openInterest", 0) for r in oc.get("records", {}).get("data", []))
            if total_call_oi > 0:
                return round(total_put_oi / total_call_oi, 3)
        except Exception:
            pass
        return round(max(0.5, min(1.8, 0.95 + random.gauss(0, 0.15))), 2)

    def _fetch_gold_silver_ratio(self) -> float:
        """
        Gold price (USD/oz) ÷ Silver price (USD/oz). Historical range 50–100.
        """
        try:
            import yfinance as yf
            gold  = yf.Ticker("GC=F").history(period="2d")["Close"].iloc[-1]
            silver = yf.Ticker("SI=F").history(period="2d")["Close"].iloc[-1]
            if silver > 0:
                return round(gold / silver, 1)
        except Exception:
            pass
        return round(max(55.0, min(100.0, 78 + random.gauss(0, 4))), 1)

    # ── Price action calculators ──────────────────────────────────────────────

    def _detect_candle_pattern(self, closes: list, highs: list, lows: list,
                                opens: list) -> dict:
        """
        Detect the most significant candlestick pattern in the last 1–3 bars.

        Patterns checked (in priority order — strongest overrides weaker):
          Three-bar: Morning Star, Evening Star
          Two-bar:   Bullish Engulfing, Bearish Engulfing, Tweezer Top/Bottom
          One-bar:   Hammer, Shooting Star, Doji, Marubozu (Bull/Bear), Spinning Top

        Returns keys: candle_score, candle_signal, candle_label, candle_note
        """
        n = min(len(closes), len(highs), len(lows), len(opens) if opens else len(closes))
        # Need at least 1 complete bar
        if n < 1:
            # Simulate a basic pattern when no OHLC available
            roll = random.random()
            if roll > 0.65:
                return {"candle_score": 0.30, "candle_signal": "bull",
                        "candle_label": "Bullish Candle",
                        "candle_note": "Recent candle structure appears bullish (simulated — connect live data for real pattern detection)."}
            elif roll < 0.35:
                return {"candle_score": -0.30, "candle_signal": "bear",
                        "candle_label": "Bearish Candle",
                        "candle_note": "Recent candle structure appears bearish (simulated)."}
            else:
                return {"candle_score": 0.0, "candle_signal": "neutral",
                        "candle_label": "Doji / Indecision",
                        "candle_note": "Indecisive candle — no clear directional bias (simulated)."}

        # If opens not provided, approximate as previous close
        if not opens:
            opens = [closes[max(0, i-1)] for i in range(n)]

        def body(i):    return abs(closes[i] - opens[i])
        def range_(i):  return highs[i] - lows[i]
        def is_bull(i): return closes[i] >= opens[i]
        def upper_wick(i): return highs[i] - max(closes[i], opens[i])
        def lower_wick(i): return min(closes[i], opens[i]) - lows[i]

        i = n - 1   # most recent bar

        # ── Three-bar patterns ────────────────────────────────────────────────
        if n >= 3:
            i1, i2 = n - 3, n - 2

            # Morning Star: large bear → small body (gap or doji) → large bull
            if (not is_bull(i1) and body(i1) > range_(i1) * 0.5
                    and body(i2) < range_(i2) * 0.35
                    and is_bull(i) and body(i) > range_(i) * 0.5
                    and closes[i] > (opens[i1] + closes[i1]) / 2):
                return {"candle_score": 0.70, "candle_signal": "bull",
                        "candle_label": "Morning Star",
                        "candle_note": "Morning Star pattern (3-bar reversal): large bear candle → indecision → large bull candle. Strong bullish reversal signal after a downtrend."}

            # Evening Star: large bull → small body → large bear
            if (is_bull(i1) and body(i1) > range_(i1) * 0.5
                    and body(i2) < range_(i2) * 0.35
                    and not is_bull(i) and body(i) > range_(i) * 0.5
                    and closes[i] < (opens[i1] + closes[i1]) / 2):
                return {"candle_score": -0.70, "candle_signal": "bear",
                        "candle_label": "Evening Star",
                        "candle_note": "Evening Star pattern (3-bar reversal): large bull candle → indecision → large bear candle. Strong bearish reversal signal after an uptrend."}

        # ── Two-bar patterns ──────────────────────────────────────────────────
        if n >= 2:
            prev = n - 2

            # Bullish Engulfing
            if (not is_bull(prev) and is_bull(i)
                    and opens[i] <= closes[prev]
                    and closes[i] >= opens[prev]
                    and body(i) > body(prev)):
                return {"candle_score": 0.60, "candle_signal": "bull",
                        "candle_label": "Bullish Engulfing",
                        "candle_note": "Bullish Engulfing: today's bull candle fully covers yesterday's bear body. High-probability reversal to upside — institutional buying likely."}

            # Bearish Engulfing
            if (is_bull(prev) and not is_bull(i)
                    and opens[i] >= closes[prev]
                    and closes[i] <= opens[prev]
                    and body(i) > body(prev)):
                return {"candle_score": -0.60, "candle_signal": "bear",
                        "candle_label": "Bearish Engulfing",
                        "candle_note": "Bearish Engulfing: today's bear candle fully covers yesterday's bull body. High-probability reversal to downside — distribution/selling pressure."}

            # Tweezer Bottom (two lows nearly equal → support holding)
            if (abs(lows[i] - lows[prev]) / (lows[prev] or 1) < 0.002
                    and not is_bull(prev) and is_bull(i)):
                return {"candle_score": 0.45, "candle_signal": "bull",
                        "candle_label": "Tweezer Bottom",
                        "candle_note": "Tweezer Bottom: two equal lows — price rejected at this support level twice. Buyers defending the zone."}

            # Tweezer Top
            if (abs(highs[i] - highs[prev]) / (highs[prev] or 1) < 0.002
                    and is_bull(prev) and not is_bull(i)):
                return {"candle_score": -0.45, "candle_signal": "bear",
                        "candle_label": "Tweezer Top",
                        "candle_note": "Tweezer Top: two equal highs — price rejected at this resistance twice. Sellers defending the zone."}

        # ── Single-bar patterns ───────────────────────────────────────────────
        r = range_(i)
        b = body(i)
        uw = upper_wick(i)
        lw = lower_wick(i)

        if r == 0:
            return {"candle_score": 0.0, "candle_signal": "neutral",
                    "candle_label": "Flat Bar", "candle_note": "No price movement — no candle signal."}

        # Doji: body < 5% of range
        if b < r * 0.05:
            return {"candle_score": 0.0, "candle_signal": "neutral",
                    "candle_label": "Doji",
                    "candle_note": "Doji: open ≈ close — indecision between buyers and sellers. Wait for next bar to confirm direction."}

        # Hammer (bullish reversal): long lower wick (≥2× body), tiny upper wick, body at top
        if lw >= 2 * b and uw < b * 0.5 and not is_bull(i) is False:
            return {"candle_score": 0.50, "candle_signal": "bull",
                    "candle_label": "Hammer",
                    "candle_note": "Hammer: long lower wick shows sellers pushed price down sharply but buyers recovered. Bullish reversal signal — watch for confirmation."}

        # Shooting Star (bearish reversal): long upper wick (≥2× body), tiny lower wick
        if uw >= 2 * b and lw < b * 0.5:
            return {"candle_score": -0.50, "candle_signal": "bear",
                    "candle_label": "Shooting Star",
                    "candle_note": "Shooting Star: long upper wick shows buyers pushed price high but sellers took control. Bearish reversal signal — watch for confirmation."}

        # Bull Marubozu: body ≥ 90% of range, bullish
        if b >= r * 0.90 and is_bull(i):
            return {"candle_score": 0.55, "candle_signal": "bull",
                    "candle_label": "Bull Marubozu",
                    "candle_note": "Bull Marubozu: strong full-body bull candle with almost no wicks. Unambiguous buying dominance — high-momentum up move."}

        # Bear Marubozu: body ≥ 90% of range, bearish
        if b >= r * 0.90 and not is_bull(i):
            return {"candle_score": -0.55, "candle_signal": "bear",
                    "candle_label": "Bear Marubozu",
                    "candle_note": "Bear Marubozu: strong full-body bear candle with almost no wicks. Unambiguous selling dominance — high-momentum down move."}

        # Spinning Top: body 5–35% of range, roughly equal wicks
        if b < r * 0.35 and abs(uw - lw) < r * 0.20:
            direction = "bull" if is_bull(i) else "bear"
            return {"candle_score": 0.10 if is_bull(i) else -0.10, "candle_signal": "neutral",
                    "candle_label": "Spinning Top",
                    "candle_note": "Spinning Top: small body with long wicks in both directions — indecision. Neither bulls nor bears in control; consolidation likely."}

        # Generic bull/bear candle
        score = (b / r) * (0.35 if is_bull(i) else -0.35)
        return {"candle_score": round(score, 2),
                "candle_signal": "bull" if is_bull(i) else "bear",
                "candle_label": "Bull Candle" if is_bull(i) else "Bear Candle",
                "candle_note": (f"{'Bullish' if is_bull(i) else 'Bearish'} candle — body is "
                                f"{b/r*100:.0f}% of range. "
                                + ("Moderate buying pressure." if is_bull(i) else "Moderate selling pressure."))}

    def _calc_ema_positioning(self, closes: list) -> dict:
        """
        Check where price sits relative to key EMAs: 9, 20, 50, 200.
        Each EMA above which price closes = +1 bullish point.
        Score normalised to [-1, +1].

        EMA positioning is the most widely used price action filter in India:
          Price above 200 EMA = secular bull trend (mutual funds, SIPs buying)
          Price above 50 EMA  = intermediate bull trend
          Price above 20 EMA  = short-term bull trend
          Price above 9 EMA   = very short-term / intraday bull
        """
        def ema(data: list, n: int) -> float | None:
            if len(data) < n:
                return None
            k = 2 / (n + 1)
            e = data[0]
            for v in data[1:]:
                e = v * k + e * (1 - k)
            return e

        periods   = [9, 20, 50, 200]
        labels_p  = ["9 EMA", "20 EMA", "50 EMA", "200 EMA"]
        price     = closes[-1] if closes else 0
        above     = []
        below     = []

        for p, lbl in zip(periods, labels_p):
            val = ema(closes, p)
            if val is None:
                continue
            if price > val:
                above.append(lbl)
            else:
                below.append(lbl)

        total = len(above) + len(below)
        if total == 0:
            return {"ema_score": 0.0, "ema_signal": "neutral",
                    "ema_label": "Insufficient data",
                    "ema_note": "Not enough price history to compute EMAs."}

        bull_count = len(above)
        raw_score  = (bull_count / total - 0.5) * 2   # -1 to +1
        ema_score  = round(raw_score * 0.50, 3)        # cap contribution at 0.50

        if bull_count == total:
            signal  = "bull"
            label   = f"Above all EMAs ({', '.join(above)})"
            note    = (f"Price is above all key EMAs ({', '.join(above)}). "
                       "Strong bullish structure — all timeframes aligned. "
                       "Institutional buyers are likely active.")
        elif bull_count >= total * 0.75:
            signal  = "bull"
            label   = f"Above {bull_count}/{total} EMAs"
            note    = (f"Price above {', '.join(above)}; below {', '.join(below)}. "
                       "Short-to-medium term uptrend intact. "
                       "Pullback to 50 EMA would be a buying opportunity.")
        elif bull_count == 0:
            signal  = "bear"
            label   = f"Below all EMAs ({', '.join(below)})"
            note    = (f"Price is below all key EMAs ({', '.join(below)}). "
                       "Bearish structure across all timeframes — avoid fresh longs. "
                       "Wait for reclaim of at least the 20 EMA.")
        elif bull_count <= total * 0.25:
            signal  = "bear"
            label   = f"Below {len(below)}/{total} EMAs"
            note    = (f"Price below {', '.join(below)}; above only {', '.join(above)}. "
                       "Predominantly bearish EMA structure.")
        else:
            signal  = "neutral"
            label   = f"Mixed EMAs ({bull_count} above / {len(below)} below)"
            note    = (f"Price above {', '.join(above) or 'none'} but below {', '.join(below) or 'none'}. "
                       "Mixed EMA picture — no clean trend. Favour range-trading strategies.")

        return {"ema_score": ema_score, "ema_signal": signal,
                "ema_label": label, "ema_note": note}

    def _calc_pivot_points(self, closes: list, highs: list, lows: list) -> dict:
        """
        Standard daily Pivot Points from the PREVIOUS session's High, Low, Close.
        P  = (H + L + C) / 3
        R1 = 2P − L,    R2 = P + (H − L)
        S1 = 2P − H,    S2 = P − (H − L)

        Signal: price relative to P, R1, S1.
        Proximity to R2/S2 = strong overbought/oversold extreme.

        Widely used by NSE/MCX traders for intraday and swing entries.
        """
        n = min(len(closes), len(highs), len(lows))
        if n < 2:
            return {}   # not enough data — omit pivot indicator

        # Previous session OHLC (index -2)
        prev_h = highs[-2]
        prev_l = lows[-2]
        prev_c = closes[-2]
        price  = closes[-1]

        P  = (prev_h + prev_l + prev_c) / 3
        R1 = 2 * P - prev_l
        R2 = P + (prev_h - prev_l)
        S1 = 2 * P - prev_h
        S2 = P - (prev_h - prev_l)

        range_pp = R2 - S2 if R2 != S2 else 1.0

        # Position score: where price sits in the S2–R2 band, centred at P
        pos = (price - P) / (range_pp / 2)   # -1 (at S2) to +1 (at R2)
        pos = max(-1.0, min(1.0, pos))

        pivot_score = round(pos * 0.45, 3)   # max contribution ±0.45

        if price >= R2:
            signal = "bear"    # at or above R2 → overbought relative to pivot
            label  = f"At/Above R2 ({R2:.0f})"
            note   = (f"Price {price:.0f} ≥ R2 {R2:.0f} — Extreme pivot resistance. "
                      "Overbought relative to yesterday's range. "
                      "High probability of short-term pullback or consolidation.")
        elif price >= R1:
            signal = "bull"
            label  = f"Between P–R1 ({P:.0f}–{R1:.0f})"
            note   = (f"Price {price:.0f} between Pivot {P:.0f} and R1 {R1:.0f}. "
                      "Above pivot — bullish intraday bias. "
                      f"Next resistance at R1 {R1:.0f}, then R2 {R2:.0f}.")
        elif price >= P:
            signal = "bull"
            label  = f"Above Pivot ({P:.0f})"
            note   = (f"Price {price:.0f} above Pivot {P:.0f} — bullish bias for the session. "
                      f"R1 at {R1:.0f} is first resistance. "
                      "Strong opens above pivot often hold through the day on NSE.")
        elif price >= S1:
            signal = "bear"
            label  = f"Between S1–P ({S1:.0f}–{P:.0f})"
            note   = (f"Price {price:.0f} below Pivot {P:.0f}, above S1 {S1:.0f}. "
                      "Bearish intraday bias. "
                      f"S1 {S1:.0f} is first support — a bounce from here is possible.")
        else:
            signal = "bear"
            label  = f"At/Below S2 ({S2:.0f})"
            note   = (f"Price {price:.0f} ≤ S2 {S2:.0f} — Extreme pivot support break. "
                      "Oversold relative to yesterday's range. "
                      "Possible capitulation — watch for reversal candle at S2.")

        return {
            "pivot_score":  pivot_score,
            "pivot_signal": signal,
            "pivot_label":  label,
            "pivot_note":   note,
            "pivot_P":  round(P, 1),
            "pivot_R1": round(R1, 1), "pivot_R2": round(R2, 1),
            "pivot_S1": round(S1, 1), "pivot_S2": round(S2, 1),
        }

    def _score_to_signal(self, score: float) -> str:
        return "bull" if score > 0 else "bear" if score < 0 else "neutral"

    def _build_chart_data(self, signal: str, horizon: str) -> list:
        """Simulate a projected price path for display in iOS chart."""
        labels_map = {
            "1D": ["9am", "10am", "11am", "12pm", "1pm", "2pm", "3pm"],
            "1W": ["Mon", "Tue", "Wed", "Thu", "Fri"],
            "2W": ["W1 Mon", "W1 Wed", "W1 Fri", "W2 Mon", "W2 Wed", "W2 Fri"],
            "1M": ["W1", "W2", "W3", "W4"],
            "3M": ["M1", "M2", "M3"],
        }
        labels = labels_map.get(horizon, ["D1", "D2", "D3", "D4", "D5"])
        direction = 1 if signal == "bull" else -1 if signal == "bear" else 0
        base = 100.0
        points = []
        for i, lbl in enumerate(labels):
            noise = random.uniform(-0.5, 0.5)
            base += direction * (0.4 + i * 0.15) + noise
            points.append({"label": lbl, "value": round(base, 2)})
        return points

    def backtest(self, ticker: str, horizon: str, days: int, category: str = "equity") -> dict:
        """
        Back-test Jyotish rules against real historical price data from yfinance.
        Actual outcome = price direction over the horizon window starting from `target`.
        """
        price_map = self._load_price_history(ticker, days + 30)

        trading_days = sorted(price_map.keys())
        if len(trading_days) < 2:
            return {
                "ticker": ticker, "horizon": horizon, "days": days,
                "accuracy": None, "results": [],
                "note": f"Could not fetch price history for {ticker} from yfinance."
            }

        horizon_days = HORIZON_DAYS.get(horizon, HORIZON_DAYS["1W"])
        results = []
        correct = 0

        for idx, target in enumerate(trading_days[:-1]):
            # Find closing price `horizon_days` ahead
            future_idx = min(idx + horizon_days, len(trading_days) - 1)
            future_day = trading_days[future_idx]
            if future_day == target:
                continue

            start_price  = price_map[target]
            end_price    = price_map[future_day]
            pct_change   = (end_price - start_price) / start_price * 100

            # Label actual direction: >0.5% = bull, <-0.5% = bear, else neutral
            if pct_change > 0.5:
                actual = "bull"
            elif pct_change < -0.5:
                actual = "bear"
            else:
                actual = "neutral"

            panch = self.jyotish.get_panchanga(target)
            pred  = self.predict(ticker, category, horizon, "jyotish", panch, {})
            hit   = pred["signal"] == actual
            correct += 1 if hit else 0
            results.append({
                "date":      str(target),
                "predicted": pred["signal"],
                "actual":    actual,
                "pct_change": round(pct_change, 2),
                "correct":   hit,
            })

        if not results:
            accuracy = None
        else:
            accuracy = round(correct / len(results) * 100, 1)

        return {
            "ticker":   ticker,
            "horizon":  horizon,
            "days":     days,
            "accuracy": accuracy,
            "total_days_tested": len(results),
            "results":  results[-10:],
            "note": "Actual outcome derived from real yfinance closing prices."
        }

    def _load_price_history(self, ticker: str, days: int) -> dict:
        """Returns {date: close_price} for `days` of history via yfinance."""
        try:
            import yfinance as yf
            from datetime import timedelta
            end   = date.today()
            start = end - timedelta(days=days)
            yf_map = {
                "GOLD": "GC=F", "SILVER": "SI=F", "CRUDEOIL": "CL=F",
                "COPPER": "HG=F", "NATURALGAS": "NG=F",
                "NIFTY50": "^NSEI", "BANKNIFTY": "^NSEBANK",
            }
            symbol = yf_map.get(ticker.upper(), f"{ticker}.NS")
            hist   = yf.Ticker(symbol).history(start=str(start), end=str(end))
            if hist.empty:
                return {}
            return {d.date(): round(float(c), 2) for d, c in zip(hist.index, hist["Close"])}
        except Exception:
            return {}

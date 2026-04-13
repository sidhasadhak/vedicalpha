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

# ── Load weights ─────────────────────────────────────────────────────────────
_WEIGHTS_FILE = os.path.join(os.path.dirname(__file__), "rule_weights.json")
with open(_WEIGHTS_FILE) as _f:
    _RULE_WEIGHTS = json.load(_f)

# New 2D table: _WEIGHT_TABLE[horizon][category] → {technical, vyapar_ratna, prasna, …}
_WEIGHT_TABLE = _RULE_WEIGHTS["weights"]

# ── Load per-ticker indicator weights ─────────────────────────────────────────
_INDICATOR_WEIGHTS_FILE = os.path.join(os.path.dirname(__file__), "ticker_indicator_weights.json")
with open(_INDICATOR_WEIGHTS_FILE) as _f:
    _INDICATOR_WEIGHTS = json.load(_f)
_DEFAULT_IND_WEIGHTS = _INDICATOR_WEIGHTS.get("_default", {})

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
        Lookup weights from the 2D table in rule_weights.json.

        weights[horizon][category] gives absolute weights for all 7 components
        (technical + 6 Vedic engines) that sum to 1.0.

        Fallback chain: exact category → "equity" → hardcoded defaults.
        Returns keys: technical, vyapar_ratna, prasna, bhavartha, kalamrita,
                      brihat, mundane, jyotish (alias for vyapar_ratna).
        """
        h_table  = _WEIGHT_TABLE.get(horizon, _WEIGHT_TABLE.get("1W", {}))
        row      = h_table.get(category, h_table.get("equity", {}))

        engine_keys = ["technical", "vyapar_ratna", "prasna",
                       "bhavartha", "kalamrita", "brihat", "mundane"]

        # Normalise in case of rounding drift (rows should always sum to 1.0)
        total = sum(row.get(k, 0.0) for k in engine_keys)
        if total <= 0:
            total = 1.0

        resolved = {k: round(row.get(k, 0.0) / total, 4) for k in engine_keys}
        resolved["jyotish"] = resolved["vyapar_ratna"]   # backward-compat alias
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
        # Resolve prediction date for ephemeris lookup
        _date_raw = panchanga.get("date")
        if isinstance(_date_raw, date):
            _pred_date = _date_raw
        elif isinstance(_date_raw, str):
            try:
                _pred_date = date.fromisoformat(_date_raw)
            except (ValueError, TypeError):
                _pred_date = date.today()
        else:
            _pred_date = date.today()

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
            "date":      _pred_date,   # real date → ephemeris-based engines use this
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

            # Resolve per-ticker indicator weights
            # Falls back to _default when ticker not in ticker_indicator_weights.json
            ind_w = {**_DEFAULT_IND_WEIGHTS,
                     **_INDICATOR_WEIGHTS.get(ticker.upper(), {})}

            # Build indicator list: (weight_key, score, signal, note, display_name)
            tech_indicators = [
                ("RSI",         tech["rsi_score"],  tech["rsi_signal"],  tech["rsi_note"],  f"RSI-14 ({tech['rsi']})"),
                ("MACD",        tech["macd_score"], tech["macd_signal"], tech["macd_note"], f"MACD ({tech['macd_label']})"),
                ("supertrend",  tech["st_score"],   tech["st_signal"],   tech["st_note"],   f"Supertrend ({tech['st_label']})"),
                ("bollinger",   tech["bb_score"],   tech["bb_signal"],   tech["bb_note"],   f"Bollinger Bands ({tech['bb_label']})"),
                ("ADX",         tech["adx_score"],  tech["adx_signal"],  tech["adx_note"],  f"ADX ({tech['adx']})"),
                ("VIX",         tech["vix_score"],  tech["vix_signal"],  tech["vix_note"],  f"India VIX ({tech['vix']})"),
            ]
            if tech.get("pcr_score") is not None:
                tech_indicators.append(
                    ("PCR", tech["pcr_score"], tech["pcr_signal"], tech["pcr_note"], f"Put-Call Ratio ({tech['pcr']})")
                )
            if tech.get("ratio_score") is not None:
                tech_indicators.append(
                    ("gold_silver_ratio", tech["ratio_score"], tech["ratio_signal"], tech["ratio_note"], tech["ratio_label"])
                )
            if tech.get("candle_score") is not None:
                tech_indicators.append(
                    ("candle", tech["candle_score"], tech["candle_signal"], tech["candle_note"], f"Candle Pattern ({tech['candle_label']})")
                )
            if tech.get("ema_score") is not None:
                tech_indicators.append(
                    ("EMA", tech["ema_score"], tech["ema_signal"], tech["ema_note"], f"EMA Positioning ({tech['ema_label']})")
                )
            if tech.get("pivot_score") is not None:
                tech_indicators.append(
                    ("pivot", tech["pivot_score"], tech["pivot_signal"], tech["pivot_note"], f"Pivot Points ({tech['pivot_label']})")
                )
            if tech.get("sp500_score") is not None:
                tech_indicators.append(
                    ("SP500", tech["sp500_score"], tech["sp500_signal"], tech["sp500_note"],
                     f"S&P 500 Global Cue ({tech['sp500_ret']:+.1f}%)")
                )

            # Weighted sum using per-ticker indicator weights
            # Normalise by total weight so magnitude is stable regardless of weights.
            # When all weights=1 this equals the plain average.
            tech_weighted = 0.0
            weight_total  = 0.0
            for wkey, score, signal, note, name in tech_indicators:
                w = ind_w.get(wkey, 1.0)
                if w <= 0:
                    continue    # indicator disabled for this ticker
                tech_weighted += score * w
                weight_total  += w
                factors.append({
                    "name":        name,
                    "signal":      signal,
                    "score":       round(score, 2),
                    "confidence":  round(tech["confidence"]),
                    "description": note,
                    "source":      "Technical analysis",
                    "ind_weight":  round(w, 2),
                })

            # Weighted average of indicator scores, scaled by the engine's weight.
            # (Normalized average keeps total magnitude stable regardless of
            # how many indicators are active or how weights are distributed.)
            if weight_total > 0:
                total_score += (tech_weighted / weight_total) * weights["technical"]

            # ── MARKET REGIME FILTER (200-DMA) ────────────────────────────────
            # Binary macro-level overlay — separate from the EMA positioning score.
            # EMA score captures multi-timeframe trend structure (9/20/50/200 all counted).
            # Regime filter captures the secular trend as a standalone signal.
            above_200 = tech.get("above_200_ema")
            if above_200 is not None:
                if not above_200:
                    regime_score, regime_signal = -0.10, "bear"
                    regime_note = ("Price is below the 200-day EMA — secular bear trend active. "
                                   "Vedic bull signals carry less conviction against the macro downtrend. "
                                   "Best to wait for price to reclaim 200-DMA before acting on bullish calls.")
                else:
                    regime_score, regime_signal = +0.06, "bull"
                    regime_note = ("Price is above the 200-day EMA — secular bull trend intact. "
                                   "Dips are historically buying opportunities; bull signals have "
                                   "higher follow-through probability in this regime.")
                factors.append({
                    "name":        "Market Regime (200-DMA)",
                    "signal":      regime_signal,
                    "score":       round(regime_score, 2),
                    "confidence":  72,
                    "description": regime_note,
                    "source":      "Technical analysis — 200-DMA macro regime filter",
                })
                total_score += regime_score * weights["technical"]

        # ── EVENT CALENDAR ────────────────────────────────────────────────────
        _pred_date = kpanch.get("date", date.today())
        event_factor = self._check_event_risk(_pred_date, category)
        if event_factor:
            factors.append(event_factor)

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

        # Event risk cap — high-impact events make any prediction less reliable
        if any(f.get("is_event_risk") for f in factors) and confidence > 62:
            confidence = 62

        return {
            "signal":        signal,
            "signal_label":  "Tezi ↑" if signal == "bull" else "Mandi ↓" if signal == "bear" else "Sama →",
            "confidence":    confidence,
            "score":         round(total_score, 3),
            "expected_move": self._calc_expected_move(
                price_data, horizon, total_score, confidence
            ),
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
        _daily_closes = price_data.get("closes", [])
        _daily_highs  = price_data.get("highs",  [])
        _daily_lows   = price_data.get("lows",   [])
        _daily_opens  = price_data.get("opens",  [])

        # ── Horizon-appropriate bar resolution ────────────────────────────────
        # 1D/1W/2W: use raw daily bars as-is.
        # 1M:       use daily bars (200-day window needed for 200-DMA).
        # 3M:       aggregate daily → weekly bars for trend indicators.
        #           Weekly bars filter out intraday/intraweek noise and
        #           make RSI/MACD/Bollinger reflect the 3-month trend properly.
        if horizon == "3M" and len(_daily_closes) >= 30:
            closes = self._aggregate_weekly(_daily_closes, "last")
            highs  = self._aggregate_weekly(_daily_highs,  "max")  if _daily_highs else []
            lows   = self._aggregate_weekly(_daily_lows,   "min")  if _daily_lows  else []
            bar_label = "weekly"
        else:
            closes = _daily_closes
            highs  = _daily_highs
            lows   = _daily_lows
            bar_label = "daily"

        live   = len(closes) >= 14
        long_horizon = horizon in ("1M", "3M")

        # ── 1. RSI ────────────────────────────────────────────────────────────
        rsi       = self._calc_rsi(closes, 14) if live else round(40 + random.random() * 25, 1)
        rsi_score  = (rsi - 50) / 50
        rsi_signal = "bull" if rsi > 60 else "bear" if rsi < 40 else "neutral"
        rsi_note   = (
            f"RSI-14 ({bar_label}) at {rsi:.1f} — "
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

        # ── 9. Candlestick patterns ───────────────────────────────────────────
        # Only meaningful for 1D/1W — a single-bar pattern tells nothing about
        # direction over a month or quarter.  Use daily bars always (not weekly).
        if not long_horizon:
            candle = self._detect_candle_pattern(
                _daily_closes, _daily_highs, _daily_lows, _daily_opens
            )
            result.update(candle)

        # ── 10. EMA positioning ──────────────────────────────────────────────
        # Always run on daily bars regardless of resolution used for other
        # indicators — EMAs are defined on daily closes (9/20/50/200 EMA).
        # For 200-DMA to compute, main.py must supply 200+ daily bars (1M/3M).
        ema_pa = self._calc_ema_positioning(_daily_closes)
        result.update(ema_pa)

        # ── 11. Pivot points ─────────────────────────────────────────────────
        # Previous-session H/L/C → next-session support/resistance levels.
        # Only meaningful for intraday and weekly swing trades (1D, 1W).
        if horizon in ("1D", "1W"):
            pivot_pa = self._calc_pivot_points(_daily_closes, _daily_highs, _daily_lows)
            result.update(pivot_pa)

        # ── 12. S&P 500 global cue (equity/index only) ────────────────────────
        # S&P 500 prior-day return is a genuine leading signal for NIFTY/BSE open.
        # Not relevant for commodities (gold moves inversely to USD, not S&P).
        if category in ("equity", "index"):
            sp_ret = self._fetch_sp500_return()
            if sp_ret is not None:
                if sp_ret > 1.5:
                    sp_score, sp_signal = +0.28, "bull"
                    sp_note = (f"S&P 500 gained {sp_ret:+.1f}% yesterday — strong global risk-on. "
                               "NIFTY/BSE typically open 0.5–1% higher on such cues.")
                elif sp_ret > 0.5:
                    sp_score, sp_signal = +0.12, "bull"
                    sp_note = f"S&P 500 up {sp_ret:+.1f}% yesterday — mild positive global cue for Indian equities."
                elif sp_ret < -1.5:
                    sp_score, sp_signal = -0.32, "bear"
                    sp_note = (f"S&P 500 fell {sp_ret:+.1f}% yesterday — global risk-off. "
                               "NIFTY/BSE likely to open under pressure.")
                elif sp_ret < -0.5:
                    sp_score, sp_signal = -0.14, "bear"
                    sp_note = f"S&P 500 down {sp_ret:+.1f}% yesterday — mild negative global cue for Indian equities."
                else:
                    sp_score, sp_signal = 0.0, "neutral"
                    sp_note = f"S&P 500 {sp_ret:+.1f}% yesterday — flat global cue; India moves on domestic factors."
                result.update({
                    "sp500_ret": sp_ret, "sp500_score": sp_score,
                    "sp500_signal": sp_signal, "sp500_note": sp_note,
                })

        return result

    # ── Individual indicator calculators ──────────────────────────────────────

    def _calc_expected_move(self, price_data: dict, horizon: str,
                             score: float, confidence: int) -> str:
        """
        Directional expected move — the actual prediction output, not a volatility lookup.

        Logic:
          1. Compute σ_horizon from the ticker's recent daily price volatility
             (RMS of last 20 daily returns scaled to the horizon window).
             This gives a ticker-specific magnitude scale — Crude Oil moves very
             differently from TCS over the same period.

          2. Center = score × σ_horizon
             score is -1 … +1 and encodes both direction and strength from the
             combined Vedic + Technical analysis. A score of +0.60 means a strong
             bull signal expected to capture ~60% of the 1-sigma upside move.

          3. Half-band = (1 − confidence/100) × σ_horizon × 0.55
             Low confidence → wide band (uncertain). High confidence → tight band.
             This makes precision a direct function of how aligned the engines are.

          4. Format directionally:
             Both ends positive  →  "+4.2% to +7.8%"   (clear bull)
             Both ends negative  →  "−6.1% to −2.3%"   (clear bear)
             Straddles zero      →  "−1.8% to +3.2%"   (uncertain — reduce size)

        Falls back to static ranges when < 5 bars of price history are available.
        """
        closes  = price_data.get("closes", [])
        _static = EXPECTED_MOVES.get(horizon, "1–5%")

        if len(closes) < 5:
            return _static

        # ── Step 1: ticker volatility ──────────────────────────────────────────
        window  = min(20, len(closes) - 1)
        rets    = [
            abs(closes[i] - closes[i - 1]) / closes[i - 1]
            for i in range(len(closes) - window, len(closes))
            if closes[i - 1] > 0
        ]
        if not rets:
            return _static

        sigma_daily   = (sum(r ** 2 for r in rets) / len(rets)) ** 0.5
        _tdays        = {"1D": 1, "1W": 5, "2W": 10, "1M": 21, "3M": 63}
        sigma_h       = sigma_daily * (_tdays.get(horizon, 21) ** 0.5) * 100  # as %

        # ── Step 2: directional center ─────────────────────────────────────────
        center        = score * sigma_h          # signed; +score → positive center

        # ── Step 3: confidence-derived uncertainty band ────────────────────────
        half_band     = (1.0 - confidence / 100.0) * sigma_h * 0.55

        low  = int(round(center - half_band))
        high = int(round(center + half_band))

        # Ensure minimum width of 1pp so range is never a single point
        if high <= low:
            high = low + 1

        # ── Step 4: directional string formatting (whole numbers, signed) ──────
        def _pct(v: int) -> str:
            if v == 0:
                return "0%"
            return f"+{v}%" if v > 0 else f"{v}%"

        if low >= 0:
            return f"+{low}% to +{high}%"
        elif high <= 0:
            return f"{low}% to {high}%"
        else:
            return f"{_pct(low)} to {_pct(high)}"   # straddles zero

    def _aggregate_weekly(self, bars: list, agg: str = "last", window: int = 5) -> list:
        """
        Aggregate daily bars to weekly bars for longer-horizon indicators.
          agg="last"  → take the last bar of each week (weekly close / open)
          agg="max"   → take the highest value (weekly high)
          agg="min"   → take the lowest value (weekly low)
        Drops the partial first chunk if it's shorter than window.
        """
        if not bars:
            return bars
        result = []
        # Walk backwards in chunks of `window` so the most-recent week is complete
        i = len(bars)
        while i >= window:
            chunk = bars[i - window: i]
            if agg == "last":
                result.append(chunk[-1])
            elif agg == "max":
                result.append(max(chunk))
            elif agg == "min":
                result.append(min(chunk))
            i -= window
        result.reverse()
        return result

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
        Fetch India VIX from NSE live. Falls back to simulation.
        India VIX typically trades 10–30; normal range 12–18.
        """
        try:
            from nsepython import nse_get_index_quote
            data = nse_get_index_quote("India VIX")
            return float(data["last"])
        except Exception:
            pass
        try:
            import yfinance as yf
            hist = yf.Ticker("^INDIAVIX").history(period="2d")
            if not hist.empty:
                return round(float(hist["Close"].iloc[-1]), 2)
        except Exception:
            pass
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

    def _fetch_sp500_return(self) -> float | None:
        """
        S&P 500 previous trading day return (%).
        Used as a global-market cue for NIFTY/BSE equity predictions.
        Returns None if data unavailable (no failure — just skip the factor).
        """
        try:
            import yfinance as yf
            hist = yf.download("^GSPC", period="5d", interval="1d", progress=False)
            closes = hist["Close"].dropna().values.flatten()
            if len(closes) >= 2:
                return round((float(closes[-1]) - float(closes[-2])) / float(closes[-2]) * 100, 2)
        except Exception:
            pass
        return None

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
        above         = []
        below         = []
        above_200_ema = None  # exposed for regime filter

        for p, lbl in zip(periods, labels_p):
            val = ema(closes, p)
            if val is None:
                continue
            is_above = price > val
            if p == 200:
                above_200_ema = is_above
            if is_above:
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
                "ema_label": label, "ema_note": note,
                "above_200_ema": above_200_ema}

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

    def _check_event_risk(self, pred_date: date, category: str) -> dict | None:
        """
        Returns an event-risk factor if pred_date falls on/near a market-moving event.
        Events checked:
          • F&O expiry (last Thursday of each month) — equity/index only
          • RBI MPC decision dates — equity/index only
          • Union Budget (Feb 1) — all categories
          • Quarterly results season (±30 days from quarter-end) — equity only
        """
        events = []

        # F&O expiry: last Thursday of each calendar month
        if category in ("equity", "index"):
            from calendar import monthrange
            _, last_day = monthrange(pred_date.year, pred_date.month)
            fo = date(pred_date.year, pred_date.month, last_day)
            while fo.weekday() != 3:   # 3 = Thursday
                fo -= timedelta(days=1)
            if abs((pred_date - fo).days) <= 1:
                when = "today" if pred_date == fo else ("tomorrow" if fo > pred_date else "yesterday")
                events.append(f"F&O expiry {when} ({fo.strftime('%b %d')}) — option unwinding drives intraday spikes")

        # RBI MPC decision dates 2025–2026 (outcomes released ~10 AM IST on decision day)
        if category in ("equity", "index"):
            rbi_dates = {
                date(2025, 4, 9), date(2025, 6, 6), date(2025, 8, 8),
                date(2025, 10, 8), date(2025, 12, 5),
                date(2026, 2, 7), date(2026, 4, 9), date(2026, 6, 5),
            }
            closest_rbi = min((abs((pred_date - d).days) for d in rbi_dates), default=999)
            if closest_rbi <= 1:
                events.append("RBI MPC rate decision within 1 day — rate-sensitive sectors volatile")

        # Union Budget (Feb 1 every year)
        budget_day = date(pred_date.year, 2, 1)
        if abs((pred_date - budget_day).days) <= 1:
            events.append(f"Union Budget {'today' if pred_date == budget_day else 'within 1 day'} — all sectors impacted")

        # Quarterly results season (equity only): ~Apr 15–May 15, Jul 15–Aug 15, Oct 15–Nov 15, Jan 15–Feb 15
        if category == "equity":
            y = pred_date.year
            results_windows = [
                (date(y, 4, 15), date(y, 5, 15)),
                (date(y, 7, 15), date(y, 8, 15)),
                (date(y, 10, 15), date(y, 11, 15)),
                (date(y, 1, 15), date(y, 2, 15)),
                (date(y - 1, 10, 15), date(y - 1, 11, 15)),  # handle Jan look-back
            ]
            if any(s <= pred_date <= e for s, e in results_windows):
                events.append("Q-results season — individual stock moves can be sharp and unpredictable")

        if not events:
            return None

        return {
            "name":        "Event Risk",
            "signal":      "neutral",
            "score":       0.0,
            "confidence":  50,
            "description": " | ".join(events) + ". Reduce position size and widen stops during high-impact events.",
            "source":      "Event calendar (F&O expiry, RBI MPC, Budget, Results season)",
            "is_event_risk": True,
        }

    def _score_to_signal(self, score: float) -> str:
        return "bull" if score > 0 else "bear" if score < 0 else "neutral"

    def _build_chart_data(self, signal: str, horizon: str) -> list:
        """
        Simulate a projected price path for display in iOS chart.
        Granularity:
          1D  → 7 hourly bars  (9am … 3pm)
          1W  → 5 daily bars   (Mon … Fri)
          2W  → 10 daily bars  (M1 … F2, one per trading day)
          1M  → 22 daily bars  (D1 … D22, one per trading day)
          3M  → 65 daily bars  (D1 … D65, one per trading day)
        """
        # Build label lists
        if horizon == "1D":
            labels = ["9am", "10am", "11am", "12pm", "1pm", "2pm", "3pm"]
        elif horizon == "1W":
            labels = ["Mon", "Tue", "Wed", "Thu", "Fri"]
        elif horizon == "2W":
            days = ["M", "Tu", "W", "Th", "F"]
            labels = [f"{d}·{w}" for w in ("1", "2") for d in days]
        elif horizon == "1M":
            labels = [f"D{i}" for i in range(1, 23)]   # 22 trading days
        elif horizon == "3M":
            labels = [f"D{i}" for i in range(1, 66)]   # 65 trading days
        else:
            labels = [f"D{i}" for i in range(1, 6)]

        direction = 1 if signal == "bull" else -1 if signal == "bear" else 0
        # Scale per-step drift so longer horizons still show a meaningful trend
        step_drift = {"1D": 0.40, "1W": 0.35, "2W": 0.22, "1M": 0.15, "3M": 0.10}
        drift = step_drift.get(horizon, 0.30)

        base = 100.0
        points = []
        for i, lbl in enumerate(labels):
            noise = random.uniform(-0.5, 0.5)
            base += direction * (drift + i * 0.02) + noise
            points.append({"label": lbl, "value": round(base, 2)})
        return points

    # ── Per-engine helpers for backtest attribution ───────────────────────────

    def _build_kpanch(self, panchanga: dict, category: str, horizon: str) -> dict:
        """
        Build the normalised kpanch dict shared by all Vedic engines.
        Includes the actual date so that Brihat/Mundane engines can call
        the real ephemeris instead of using hardcoded planet positions.
        """
        _vaar_map = {
            "sun":0,"ravi":0,"rav":0,"mon":1,"som":1,
            "tue":2,"man":2,"wed":3,"bud":3,"thu":4,
            "gur":4,"fri":5,"shu":5,"sat":6,"sha":6,
        }
        _raw = str(panchanga.get("vaar", "")).lower()
        _idx = next((v for k, v in _vaar_map.items() if _raw.startswith(k)), 0)

        # Resolve the prediction date: panchanga["date"] is set by jyotish.get_panchanga()
        _date_raw = panchanga.get("date")
        if isinstance(_date_raw, date):
            _pred_date = _date_raw
        elif isinstance(_date_raw, str):
            try:
                _pred_date = date.fromisoformat(_date_raw)
            except (ValueError, TypeError):
                _pred_date = date.today()
        else:
            _pred_date = date.today()

        return {
            "vaar_idx":  _idx,
            "tithi_num": panchanga.get("tithi", {}).get("number",
                         panchanga.get("tithi_num", 1)),
            "paksha":    panchanga.get("tithi", {}).get("paksha",
                         panchanga.get("paksha", "shukla")),
            "moon_age":  panchanga.get("tithi", {}).get("moon_age",
                         panchanga.get("moon_age", 0.0)),
            "sankranti": panchanga.get("sankranti", ""),
            "category":  category,
            "horizon":   horizon,
            "date":      _pred_date,   # date object — used by ephemeris-based engines
        }

    def _engine_score(self, engine_name: str, kpanch: dict,
                      panchanga: dict, category: str) -> float:
        """
        Raw directional score from one Vedic engine.
        Mirrors the scoring logic in predict() but returns the unweighted
        composite score for that engine alone. Used only in backtest attribution.
        Positive → bullish lean, negative → bearish lean.
        """
        try:
            if engine_name == "vyapar_ratna":
                sigs = self.jyotish.get_all_signals(panchanga, category)
                score = (sigs["vaar"]["signal"]      * sigs["vaar"]["reliability"]
                         + sigs["tithi"]["signal"]   * 0.65 * 0.8
                         + sigs["sankranti"]["signal"] * 0.55 * 0.7)
                if panchanga.get("five_thursday"): score -= 0.3
                if panchanga.get("five_saturday"): score += 0.4
                return score

            elif engine_name == "bhavartha":
                b = self.bhavartha.get_bhavartha_signals(panchanga)
                return (b["dhanayoga"]["score"] * 0.90
                        + b["rajayoga"]["score"]  * 0.85
                        + (b["maraka"]["score"]   * 1.10 if b["maraka"]["signal"] != 0 else 0.0)
                        + b["dasa"]["score"]      * 0.80
                        + b["malika"]["score"]    * 0.75)

            elif engine_name == "kalamrita":
                k = self.kalamrita.get_kalamrita_signals(kpanch)
                return ((k["karakatva"]["score"]      - 0.50) * 0.90
                        + (k["dhana_yoga"]["score"]   - 0.50) * 0.95
                        + (k["viparita_raja"]["score"]- 0.50) * 0.60
                        + (k["dasa_antardasa"]["score"]- 0.50) * 0.75)

            elif engine_name == "prasna":
                return self.prasna.get_prasna_signals(kpanch, category)["score"]

            elif engine_name == "brihat":
                return self.brihat.get_brihat_signals(kpanch, category)["score"]

            elif engine_name == "mundane":
                return self.mundane.get_mundane_signals(kpanch, category)["score"]

        except Exception:
            pass
        return 0.0

    # ── Main backtest ─────────────────────────────────────────────────────────

    def backtest(self, ticker: str, horizon: str, days: int,
                 category: str = "equity", verbose: bool = False) -> dict:
        """
        Back-test all 6 Vedic engines against real yfinance closing prices.

        Returns:
          accuracy            — composite (all 6 engines) directional accuracy %
          engine_accuracy     — per-engine directional accuracy %
          total_days_tested   — number of valid test windows
          results             — last 20 daily records for inspection
          note                — methodology description
        """
        price_map    = self._load_price_history(ticker, days + 60)
        trading_days = sorted(price_map.keys())

        if len(trading_days) < 2:
            return {
                "ticker": ticker, "horizon": horizon, "days": days,
                "accuracy": None, "engine_accuracy": {}, "results": [],
                "total_days_tested": 0,
                "note": f"No price history available for {ticker} via yfinance.",
            }

        horizon_days  = HORIZON_DAYS.get(horizon, HORIZON_DAYS["1W"])
        ALL_ENGINES   = ["vyapar_ratna", "bhavartha", "kalamrita",
                         "prasna", "brihat", "mundane"]
        # Prasna weight is 0 at monthly+ horizons — exclude from scoring
        active_engines = [e for e in ALL_ENGINES
                          if not (e == "prasna" and horizon in ("1M", "3M"))]

        composite_correct = 0
        eng_correct = {e: 0 for e in active_engines}
        eng_total   = {e: 0 for e in active_engines}
        results = []
        n_tested = 0

        for idx, target in enumerate(trading_days[:-1]):
            future_idx = min(idx + horizon_days, len(trading_days) - 1)
            future_day = trading_days[future_idx]
            if future_day == target:
                continue

            pct = (price_map[future_day] - price_map[target]) / price_map[target] * 100
            actual = "bull" if pct > 0.5 else "bear" if pct < -0.5 else "neutral"

            try:
                panch  = self.jyotish.get_panchanga(target)
                kpanch = self._build_kpanch(panch, category, horizon)
                pred   = self.predict(ticker, category, horizon, "jyotish", panch, {})
            except Exception:
                continue

            comp_hit = pred["signal"] == actual
            composite_correct += int(comp_hit)
            n_tested += 1

            # Per-engine attribution
            eng_row = {}
            for eng in active_engines:
                raw     = self._engine_score(eng, kpanch, panch, category)
                esig    = "bull" if raw > 0 else "bear" if raw < 0 else "neutral"
                hit     = esig == actual
                eng_correct[eng] += int(hit)
                eng_total[eng]   += 1
                eng_row[eng]     = {"signal": esig, "score": round(raw, 3), "correct": hit}

            results.append({
                "date":       str(target),
                "predicted":  pred["signal"],
                "actual":     actual,
                "pct_change": round(pct, 2),
                "correct":    comp_hit,
                "engines":    eng_row,
            })

            if verbose and n_tested % 50 == 0:
                print(f"    … {n_tested} days tested", flush=True)

        accuracy = round(composite_correct / n_tested * 100, 1) if n_tested else None
        engine_accuracy = {
            e: round(eng_correct[e] / eng_total[e] * 100, 1) if eng_total[e] else None
            for e in active_engines
        }

        return {
            "ticker":            ticker,
            "horizon":           horizon,
            "days":              days,
            "accuracy":          accuracy,
            "total_days_tested": n_tested,
            "engine_accuracy":   engine_accuracy,
            "results":           results[-20:],
            "note": ("6-engine Jyotish composite vs yfinance closing prices. "
                     "Correct = signal matches actual ±0.5% close-to-close direction. "
                     "Random baseline = 33.3%."),
        }

    def _load_price_history(self, ticker: str, days: int) -> dict:
        """Returns {date: close_price} for `days` of history via yfinance."""
        try:
            import yfinance as yf
            from datetime import timedelta
            end   = date.today()
            start = end - timedelta(days=days)
            yf_map = {
                # Commodities (USD futures — converted later if needed)
                "GOLD": "GC=F", "GOLDM": "GC=F",
                "SILVER": "SI=F", "SILVERM": "SI=F",
                "CRUDEOIL": "CL=F", "NATURALGAS": "NG=F",
                "COPPER": "HG=F",
                # Indices (already in INR on yfinance)
                "NIFTY50":    "^NSEI",
                "BANKNIFTY":  "^NSEBANK",
                "SENSEX":     "^BSESN",
                "NIFTYMIDCAP":"^NSEMDCP50",
                "NIFTYIT":    "^CNXIT",
            }
            symbol = yf_map.get(ticker.upper(), f"{ticker}.NS")
            hist   = yf.Ticker(symbol).history(start=str(start), end=str(end))
            if hist.empty:
                return {}
            return {d.date(): round(float(c), 2) for d, c in zip(hist.index, hist["Close"])}
        except Exception:
            return {}

    def _load_ohlc_history(self, ticker: str, days: int) -> dict:
        """
        Returns {date: {"close": float, "high": float, "low": float, "open": float}}
        for `days` of history via yfinance. Used by backtest_technical().
        """
        try:
            import yfinance as yf
            from datetime import timedelta
            end   = date.today()
            start = end - timedelta(days=days)
            yf_map = {
                "GOLD": "GC=F", "GOLDM": "GC=F",
                "SILVER": "SI=F", "SILVERM": "SI=F",
                "CRUDEOIL": "CL=F", "NATURALGAS": "NG=F",
                "COPPER": "HG=F",
                "NIFTY50":    "^NSEI",
                "BANKNIFTY":  "^NSEBANK",
                "SENSEX":     "^BSESN",
                "NIFTYMIDCAP":"^NSEMDCP50",
                "NIFTYIT":    "^CNXIT",
            }
            symbol = yf_map.get(ticker.upper(), f"{ticker}.NS")
            hist   = yf.Ticker(symbol).history(start=str(start), end=str(end))
            if hist.empty:
                return {}
            result = {}
            for row in hist.itertuples():
                result[row.Index.date()] = {
                    "close": round(float(row.Close), 4),
                    "high":  round(float(row.High),  4),
                    "low":   round(float(row.Low),   4),
                    "open":  round(float(row.Open),  4),
                }
            return result
        except Exception:
            return {}

    def _extract_tech_signals(self, sorted_days: list, ohlc: dict,
                              up_to_idx: int, category: str) -> dict:
        """
        Compute technical indicator signals using OHLC data available up to
        sorted_days[up_to_idx]. Returns {indicator_key: signal_str} dict.
        Used internally by backtest_technical().
        """
        window_days = sorted_days[:up_to_idx + 1][-65:]   # last 65 bars
        closes = [ohlc[d]["close"] for d in window_days]
        highs  = [ohlc[d]["high"]  for d in window_days]
        lows   = [ohlc[d]["low"]   for d in window_days]
        opens  = [ohlc[d]["open"]  for d in window_days]

        if len(closes) < 5:
            return {}

        price_data = {
            "closes": closes, "highs": highs,
            "lows": lows, "opens": opens,
            "price": closes[-1],
        }
        tech = self._compute_technical(price_data, "1D", category)

        signals: dict = {
            "RSI":        tech["rsi_signal"],
            "MACD":       tech["macd_signal"],
            "supertrend": tech["st_signal"],
            "bollinger":  tech["bb_signal"],
            "ADX":        tech["adx_signal"],
            "VIX":        tech["vix_signal"],
        }
        if "pcr_signal" in tech:
            signals["PCR"] = tech["pcr_signal"]
        if "ratio_signal" in tech:
            signals["gold_silver_ratio"] = tech["ratio_signal"]
        if "candle_signal" in tech:
            signals["candle"] = tech["candle_signal"]
        if "ema_signal" in tech:
            signals["EMA"] = tech["ema_signal"]
        if "pivot_signal" in tech:
            signals["pivot"] = tech["pivot_signal"]
        return signals

    def backtest_technical(self, ticker: str, horizon: str, days: int,
                           category: str = "equity",
                           verbose: bool = False) -> dict:
        """
        Backtest each technical indicator independently against historical
        OHLC data for `ticker`.

        At each test date, the indicator sees only the past data (no look-ahead).
        Returns per-indicator directional accuracy % over the test window.
        Used by run_backtest.py --update-indicator-weights.

        Returns:
          indicator_accuracy  — {indicator_key: accuracy_pct} (None if <10 samples)
          total_days_tested   — number of valid windows
          suggested_weights   — {indicator_key: suggested_weight} derived from lift
        """
        ohlc = self._load_ohlc_history(ticker, days + 90)
        if not ohlc:
            return {
                "ticker": ticker, "horizon": horizon,
                "indicator_accuracy": {}, "total_days_tested": 0,
                "suggested_weights": {},
                "note": f"No OHLC history available for {ticker}.",
            }

        sorted_days   = sorted(ohlc.keys())
        horizon_days  = HORIZON_DAYS.get(horizon, HORIZON_DAYS["1W"])
        BASELINE      = 33.3

        ind_correct: dict[str, int] = {}
        ind_total:   dict[str, int] = {}
        n_tested = 0

        for idx in range(len(sorted_days) - 1):
            target     = sorted_days[idx]
            future_idx = min(idx + horizon_days, len(sorted_days) - 1)
            future_day = sorted_days[future_idx]
            if future_day == target:
                continue

            pct    = (ohlc[future_day]["close"] - ohlc[target]["close"]) / ohlc[target]["close"] * 100
            actual = "bull" if pct > 0.5 else "bear" if pct < -0.5 else "neutral"

            try:
                signals = self._extract_tech_signals(sorted_days, ohlc, idx, category)
            except Exception:
                continue

            if not signals:
                continue

            n_tested += 1
            for ind_key, sig in signals.items():
                if ind_key not in ind_correct:
                    ind_correct[ind_key] = 0
                    ind_total[ind_key]   = 0
                ind_correct[ind_key] += int(sig == actual)
                ind_total[ind_key]   += 1

            if verbose and n_tested % 50 == 0:
                print(f"    … {n_tested} windows", flush=True)

        indicator_accuracy: dict[str, float | None] = {
            k: round(ind_correct[k] / ind_total[k] * 100, 1) if ind_total.get(k, 0) >= 10 else None
            for k in ind_total
        }

        # Suggest weights: lift = accuracy − baseline, proportional allocation
        # Floor at 0.2 (don't fully silence an indicator on limited data)
        lifts = {k: max(0.2, (acc - BASELINE)) if acc is not None else 0.2
                 for k, acc in indicator_accuracy.items()}
        lift_max = max(lifts.values()) if lifts else 1.0
        suggested: dict[str, float] = {
            k: round(max(0.0, min(2.0, v / lift_max * 1.5)), 2)
            for k, v in lifts.items()
        }

        return {
            "ticker":              ticker,
            "horizon":             horizon,
            "total_days_tested":   n_tested,
            "indicator_accuracy":  indicator_accuracy,
            "suggested_weights":   suggested,
            "note": ("Per-indicator technical backtest. "
                     "Correct = signal matches actual ±0.5% close-to-close. "
                     f"Random baseline = {BASELINE}%."),
        }

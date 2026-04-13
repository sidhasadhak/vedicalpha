"""
brihat_engine.py
Brihat Samhita (Varahamihira, ~587 CE) — Transit & Mundane Engine
Planet positions sourced from Swiss Ephemeris (Lahiri sidereal) via ephemeris.py.
Vol II, key chapters for market prediction:

  Ch  8  — Brhaspati Charitra (Jupiter's transit through 12 signs)
  Ch 32  — Shani Charitra (Saturn's transit through 12 signs)
  Ch  5  — Rahu/Ketu effects (eclipse effects on commodities)
  Ch 19  — Sasyadi (grains, commodities — price effects)
  Ch 24  — Planetary War effects on markets
  Ch 29  — Pushyabhisheka (auspicious commerce timing)
  Ch 99  — Shantikarma (propitiation, market sentiment reset)

Principles encoded:
  1. Jupiter's transit sign → effects on grains, gold, cattle, trade prosperity
  2. Saturn's transit sign → market depression, scarcity, or abundance
  3. Rahu/Ketu sign position → eclipse-driven commodity disruptions
  4. Planetary war (graha yuddha) → sharp volatility in relevant commodity
  5. Mars in fire signs → metal price surges
  6. Venus in own/exalted sign → luxury goods and cattle boom
"""

# ── Jupiter Transit Effects (Ch 8 — Brhaspati Charitra) ─────────────────────
# Jupiter spends ~1 year per sign. Effects on grain/gold/cattle/trade.
# sign_num: 1=Aries ... 12=Pisces
# score: -1.0 to +1.0 for overall market prosperity
JUPITER_TRANSIT = {
    1:  {  # Aries
        "score": +0.40, "signal": "bull",
        "grain": +0.35, "gold": +0.20, "cattle": +0.45, "trade": +0.40,
        "note": "Jupiter in Aries — strong crops, cattle prosper, good trade conditions",
        "categories": {"agri": +0.35, "gold": +0.20, "commodity": +0.30, "equity": +0.35, "index": +0.35},
    },
    2:  {  # Taurus
        "score": +0.50, "signal": "bull",
        "grain": +0.50, "gold": +0.45, "cattle": +0.55, "trade": +0.40,
        "note": "Jupiter in Taurus (own sign) — maximum abundance; grain, gold, cattle all prosper ★",
        "categories": {"agri": +0.50, "gold": +0.45, "silver": +0.40, "commodity": +0.35, "equity": +0.40, "index": +0.45},
    },
    3:  {  # Gemini
        "score": +0.20, "signal": "bull",
        "grain": +0.15, "gold": +0.25, "cattle": +0.10, "trade": +0.35,
        "note": "Jupiter in Gemini — moderate; trade and commerce improve, mixed for agriculture",
        "categories": {"agri": +0.10, "gold": +0.20, "commodity": +0.20, "equity": +0.30, "index": +0.25},
    },
    4:  {  # Cancer (Jupiter exalted)
        "score": +0.55, "signal": "bull",
        "grain": +0.60, "gold": +0.40, "cattle": +0.50, "trade": +0.50,
        "note": "Jupiter exalted in Cancer — most auspicious; bumper crops, maximum prosperity ★★",
        "categories": {"agri": +0.60, "gold": +0.40, "silver": +0.35, "commodity": +0.40, "equity": +0.50, "index": +0.55},
    },
    5:  {  # Leo
        "score": +0.30, "signal": "bull",
        "grain": +0.20, "gold": +0.45, "cattle": +0.30, "trade": +0.35,
        "note": "Jupiter in Leo — gold and royal metals prosper; government spending rises",
        "categories": {"agri": +0.20, "gold": +0.45, "silver": +0.30, "commodity": +0.30, "equity": +0.35, "index": +0.30},
    },
    6:  {  # Virgo
        "score": +0.15, "signal": "neut",
        "grain": +0.30, "gold": +0.10, "cattle": +0.20, "trade": +0.15,
        "note": "Jupiter in Virgo — good for agriculture and service sectors; moderate overall",
        "categories": {"agri": +0.30, "gold": +0.10, "commodity": +0.15, "equity": +0.20, "index": +0.15},
    },
    7:  {  # Libra
        "score": +0.25, "signal": "bull",
        "grain": +0.20, "gold": +0.30, "cattle": +0.20, "trade": +0.40,
        "note": "Jupiter in Libra — trade, commerce, partnerships prosper; balanced markets",
        "categories": {"agri": +0.20, "gold": +0.30, "commodity": +0.25, "equity": +0.35, "index": +0.30},
    },
    8:  {  # Scorpio
        "score": -0.20, "signal": "bear",
        "grain": -0.25, "gold": +0.10, "cattle": -0.20, "trade": -0.15,
        "note": "Jupiter in Scorpio — hidden troubles; some sectors struggle; gold holds",
        "categories": {"agri": -0.25, "gold": +0.10, "commodity": -0.15, "equity": -0.20, "index": -0.20},
    },
    9:  {  # Sagittarius (Jupiter's own sign)
        "score": +0.45, "signal": "bull",
        "grain": +0.40, "gold": +0.35, "cattle": +0.45, "trade": +0.45,
        "note": "Jupiter in Sagittarius (own sign) — strong prosperity; religious/educational sectors boom ★",
        "categories": {"agri": +0.40, "gold": +0.35, "silver": +0.30, "commodity": +0.35, "equity": +0.45, "index": +0.45},
    },
    10: {  # Capricorn (Jupiter debilitated)
        "score": -0.35, "signal": "bear",
        "grain": -0.40, "gold": -0.20, "cattle": -0.35, "trade": -0.30,
        "note": "Jupiter debilitated in Capricorn — crop failure, reduced prosperity, market depression ★",
        "categories": {"agri": -0.40, "gold": -0.20, "commodity": -0.30, "equity": -0.35, "index": -0.35},
    },
    11: {  # Aquarius
        "score": +0.10, "signal": "neut",
        "grain": +0.05, "gold": +0.15, "cattle": +0.05, "trade": +0.20,
        "note": "Jupiter in Aquarius — modest gains; technology, mass-market sectors benefit",
        "categories": {"agri": +0.05, "gold": +0.10, "commodity": +0.10, "equity": +0.20, "index": +0.15},
    },
    12: {  # Pisces (Jupiter's moolatrikona sign)
        "score": +0.35, "signal": "bull",
        "grain": +0.35, "gold": +0.30, "cattle": +0.40, "trade": +0.30,
        "note": "Jupiter in Pisces — spiritual abundance; ocean trade prospers; water crops good",
        "categories": {"agri": +0.35, "gold": +0.30, "silver": +0.35, "commodity": +0.25, "equity": +0.30, "index": +0.30},
    },
}

# ── Saturn Transit Effects (Ch 32 — Shani Charitra) ──────────────────────────
# Saturn spends ~2.5 years per sign (Sade Sati for 3 signs = 7.5 years)
SATURN_TRANSIT = {
    1:  {  # Aries (Saturn debilitated)
        "score": -0.45, "signal": "bear",
        "note": "Saturn debilitated in Aries — major market stress, crop failures, fuel shortage ★",
        "categories": {"agri": -0.50, "gold": +0.15, "commodity": -0.40, "equity": -0.45, "index": -0.45},
    },
    2:  {  # Taurus
        "score": -0.20, "signal": "bear",
        "note": "Saturn in Taurus — slow economy, banking stress, reduced consumer spending",
        "categories": {"agri": -0.20, "gold": +0.10, "commodity": -0.25, "equity": -0.25, "index": -0.20},
    },
    3:  {  # Gemini
        "score": +0.10, "signal": "neut",
        "note": "Saturn in Gemini — communication and transport sectors stabilize; moderate",
        "categories": {"agri": +0.05, "gold": +0.05, "commodity": +0.10, "equity": +0.15, "index": +0.10},
    },
    4:  {  # Cancer
        "score": -0.30, "signal": "bear",
        "note": "Saturn in Cancer — real estate and food sectors stressed; emotional volatility",
        "categories": {"agri": -0.30, "gold": +0.10, "commodity": -0.20, "equity": -0.30, "index": -0.25},
    },
    5:  {  # Leo
        "score": -0.20, "signal": "bear",
        "note": "Saturn in Leo — government and authority friction; equity market sluggish",
        "categories": {"agri": -0.15, "gold": +0.20, "commodity": -0.15, "equity": -0.25, "index": -0.20},
    },
    6:  {  # Virgo
        "score": +0.15, "signal": "bull",
        "note": "Saturn in Virgo — discipline restores markets; healthcare and manufacturing benefit",
        "categories": {"agri": +0.20, "gold": +0.05, "commodity": +0.15, "equity": +0.20, "index": +0.15},
    },
    7:  {  # Libra (Saturn exalted)
        "score": +0.45, "signal": "bull",
        "note": "Saturn exalted in Libra — best markets under Saturn; justice, law, trade flourish ★★",
        "categories": {"agri": +0.35, "gold": +0.30, "silver": +0.35, "commodity": +0.40, "equity": +0.45, "index": +0.45},
    },
    8:  {  # Scorpio
        "score": -0.35, "signal": "bear",
        "note": "Saturn in Scorpio — hidden economic crises, debt issues, sudden market reversals",
        "categories": {"agri": -0.30, "gold": +0.25, "commodity": -0.35, "equity": -0.40, "index": -0.35},
    },
    9:  {  # Sagittarius
        "score": -0.10, "signal": "neut",
        "note": "Saturn in Sagittarius — mixed; philosophy and law sectors, moderate impact",
        "categories": {"agri": -0.10, "gold": +0.10, "commodity": -0.10, "equity": -0.05, "index": -0.05},
    },
    10: {  # Capricorn (Saturn's own sign)
        "score": +0.25, "signal": "bull",
        "note": "Saturn in Capricorn (own sign) — disciplined growth; infrastructure and industry prosper",
        "categories": {"agri": +0.20, "gold": +0.15, "commodity": +0.25, "equity": +0.25, "index": +0.25},
    },
    11: {  # Aquarius (Saturn's own sign)
        "score": +0.30, "signal": "bull",
        "note": "Saturn in Aquarius — technology and mass markets; steady gains in index and equity",
        "categories": {"agri": +0.15, "gold": +0.10, "commodity": +0.20, "equity": +0.35, "index": +0.30},
    },
    12: {  # Pisces
        "score": -0.15, "signal": "neut",
        "note": "Saturn in Pisces — overseas trade issues, maritime commodities affected; some gold safety buying",
        "categories": {"agri": -0.15, "gold": +0.20, "silver": +0.15, "commodity": -0.10, "equity": -0.15, "index": -0.15},
    },
}

# ── Rahu/Ketu Eclipse Effects (Ch 5) ─────────────────────────────────────────
# Rahu and Ketu transit in pairs (always opposite). Rahu sign governs.
# When eclipses occur in a sign, that sign's ruled commodities are disrupted.
RAHU_TRANSIT = {
    1:  {"score": -0.20, "note": "Rahu in Aries — military goods surge, equity volatile; gold safe haven"},
    2:  {"score": -0.25, "note": "Rahu in Taurus — banking/finance disruption; gold/silver bullish"},
    3:  {"score": -0.10, "note": "Rahu in Gemini — communication sector volatile; mixed for markets"},
    4:  {"score": -0.30, "note": "Rahu in Cancer — food/water supply fears; agri prices volatile"},
    5:  {"score": -0.15, "note": "Rahu in Leo — government instability risk; equity underperforms"},
    6:  {"score": +0.10, "note": "Rahu in Virgo — healthcare and analytical sectors benefit from disruption"},
    7:  {"score": -0.15, "note": "Rahu in Libra — trade agreements uncertain; forex and commodity cross-currents"},
    8:  {"score": -0.35, "note": "Rahu in Scorpio — sudden shocks, debt crises; gold and defensive assets surge ★"},
    9:  {"score": -0.10, "note": "Rahu in Sagittarius — regulatory/religious uncertainty; mixed markets"},
    10: {"score": -0.20, "note": "Rahu in Capricorn — career/industry disruption; infrastructure stocks volatile"},
    11: {"score": +0.15, "note": "Rahu in Aquarius — technology sector innovates; gains for early movers"},
    12: {"score": -0.25, "note": "Rahu in Pisces — oil/gas/water sector disruption; overseas trade hit"},
}

# ── Mars in Fire Signs → Metal/Energy Price Surges (Ch 24 — Graha Yuddha) ───
MARS_SIGN_COMMODITY = {
    1:  {"score": +0.30, "category_boost": {"commodity": +0.35, "gold": +0.20}, "note": "Mars in Aries — energy and metals surge, aggressive buying"},
    5:  {"score": +0.25, "category_boost": {"gold": +0.30, "equity": +0.20},    "note": "Mars in Leo — gold and government stocks active"},
    9:  {"score": +0.20, "category_boost": {"commodity": +0.25, "agri": +0.15}, "note": "Mars in Sagittarius — transport costs rise, agri affected"},
    2:  {"score": -0.10, "category_boost": {"agri": -0.15},                     "note": "Mars in Taurus — agricultural disruption possible"},
    4:  {"score": -0.20, "category_boost": {"agri": -0.25, "silver": +0.15},    "note": "Mars in Cancer — food supply disruption; silver as hedge"},
    8:  {"score": -0.30, "category_boost": {"commodity": -0.30, "gold": +0.30}, "note": "Mars in Scorpio — crisis; gold safe haven surge ★"},
}

# ── Venus Effects (Ch 29) ─────────────────────────────────────────────────────
VENUS_SIGN_COMMODITY = {
    2:  {"score": +0.40, "category_boost": {"gold": +0.45, "silver": +0.40, "agri": +0.35}, "note": "Venus in Taurus (own) — luxury goods, precious metals, crops boom ★"},
    7:  {"score": +0.35, "category_boost": {"gold": +0.35, "silver": +0.35, "equity": +0.25}, "note": "Venus in Libra (own) — balance and prosperity in luxury sectors"},
    12: {"score": +0.30, "category_boost": {"silver": +0.35, "agri": +0.25}, "note": "Venus in Pisces (exalted) — spiritual abundance; silver and water crops boom ★"},
    6:  {"score": -0.20, "category_boost": {"gold": -0.15, "silver": -0.15}, "note": "Venus in Virgo (debilitated) — luxury sector struggles; precious metals dip"},
}


class BrihatEngine:
    """
    Brihat Samhita transit engine.
    Uses slow-moving planetary positions (Jupiter, Saturn, Rahu/Ketu) for
    medium-to-long-term market signals (1W–3M horizon).
    Planet positions are fetched from Swiss Ephemeris (Lahiri sidereal) via ephemeris.py.
    """

    def get_brihat_signals(self, panchanga: dict, category: str = "equity") -> dict:
        """
        Master method. Returns composite Brihat Samhita signal.
        panchanga: dict with optional key 'date' (date object or ISO string).
        Planet positions are fetched from ephemeris for the prediction date.
        """
        from datetime import date as _date
        from ephemeris import get_positions

        # Resolve prediction date from panchanga
        _date_raw = panchanga.get("date")
        if isinstance(_date_raw, _date):
            pred_date = _date_raw
        elif isinstance(_date_raw, str):
            try:
                pred_date = _date.fromisoformat(_date_raw)
            except (ValueError, TypeError):
                pred_date = _date.today()
        else:
            pred_date = _date.today()

        # Fetch real ephemeris positions (cached, Lahiri sidereal)
        positions = get_positions(pred_date)

        jupiter_sign = positions["jupiter"]["sign"]
        jupiter_name = positions["jupiter"]["sign_name"]
        jupiter_deg  = positions["jupiter"]["degree"]

        saturn_sign  = positions["saturn"]["sign"]
        saturn_name  = positions["saturn"]["sign_name"]
        saturn_deg   = positions["saturn"]["degree"]

        rahu_sign    = positions["rahu"]["sign"]
        rahu_name    = positions["rahu"]["sign_name"]

        mars_sign    = positions["mars"]["sign"]
        mars_name    = positions["mars"]["sign_name"]

        venus_sign   = positions["venus"]["sign"]
        venus_name   = positions["venus"]["sign_name"]

        signals = []

        # 1. Jupiter transit signal
        jup_sig = self._jupiter_signal(jupiter_sign, jupiter_name, jupiter_deg, category)
        signals.append(jup_sig)

        # 2. Saturn transit signal
        sat_sig = self._saturn_signal(saturn_sign, saturn_name, saturn_deg, category)
        signals.append(sat_sig)

        # 3. Rahu eclipse signal
        rahu_sig = self._rahu_signal(rahu_sign, rahu_name, category)
        signals.append(rahu_sig)

        # 4. Mars commodity surge signal
        mars_sig = self._mars_signal(mars_sign, mars_name, category)
        if mars_sig:
            signals.append(mars_sig)

        # 5. Venus prosperity signal
        venus_sig = self._venus_signal(venus_sign, venus_name, category)
        if venus_sig:
            signals.append(venus_sig)

        # Weighted composite (Jupiter + Saturn get double weight for slow planets)
        weights = [2.0, 2.0, 1.0, 1.0, 1.0]
        total_w  = sum(weights[:len(signals)])
        avg_score = sum(s["score"] * w for s, w in zip(signals, weights)) / (total_w or 1)
        clipped   = max(-1.0, min(1.0, avg_score))

        if clipped > 0.20:
            signal, label = "bull", "BULLISH"
        elif clipped < -0.20:
            signal, label = "bear", "BEARISH"
        else:
            signal, label = "neutral", "NEUTRAL"

        confidence = int(min(90, 45 + abs(clipped) * 45))

        return {
            "engine":       "brihat_samhita",
            "signal":       signal,
            "signal_label": label,
            "score":        round(clipped, 3),
            "confidence":   confidence,
            "sub_signals":  signals,
            "source":       "Brihat Samhita (Varahamihira) — Jupiter Ch 8, Saturn Ch 32, Eclipse Ch 5",
            "note": (
                "Brihat Samhita uses slow-planet transits (Jupiter, Saturn, Rahu/Ketu) "
                "for medium-to-long-term commodity and market forecasting. "
                "Most reliable for 1W–3M horizon."
            ),
        }

    # ── Planet signal methods ─────────────────────────────────────────────────

    def _jupiter_signal(self, sign: int, sign_name: str, degree: float, category: str) -> dict:
        data = JUPITER_TRANSIT.get(sign, JUPITER_TRANSIT[1])
        cat_score = data["categories"].get(category, data["score"])
        return {
            "name":        f"Jupiter Transit — {sign_name} ({degree:.1f}°)",
            "signal":      "bull" if cat_score > 0.10 else "bear" if cat_score < -0.10 else "neutral",
            "score":       round(cat_score, 3),
            "confidence":  75,
            "description": data["note"],
            "source":      "Brihat Samhita Ch 8 — Brhaspati Charitra",
        }

    def _saturn_signal(self, sign: int, sign_name: str, degree: float, category: str) -> dict:
        data = SATURN_TRANSIT.get(sign, SATURN_TRANSIT[1])
        cat_score = data["categories"].get(category, data["score"])
        return {
            "name":        f"Saturn Transit — {sign_name} ({degree:.1f}°)",
            "signal":      "bull" if cat_score > 0.10 else "bear" if cat_score < -0.10 else "neutral",
            "score":       round(cat_score, 3),
            "confidence":  70,
            "description": data["note"],
            "source":      "Brihat Samhita Ch 32 — Shani Charitra",
        }

    def _rahu_signal(self, sign: int, sign_name: str, category: str) -> dict:
        data = RAHU_TRANSIT.get(sign, RAHU_TRANSIT[1])
        # Gold/silver always get a boost when Rahu causes disruption
        score = data["score"]
        if category in ("gold", "silver") and score < 0:
            score = abs(score) * 0.5  # Safe haven demand
        return {
            "name":        f"Rahu Transit — {sign_name}",
            "signal":      "bull" if score > 0.10 else "bear" if score < -0.10 else "neutral",
            "score":       round(score, 3),
            "confidence":  60,
            "description": data["note"],
            "source":      "Brihat Samhita Ch 5 — Eclipse & Rahu effects",
        }

    def _mars_signal(self, sign: int, sign_name: str, category: str) -> dict | None:
        data = MARS_SIGN_COMMODITY.get(sign)
        if not data:
            return None
        cat_boost = data["category_boost"].get(category, data["score"] * 0.5)
        return {
            "name":        f"Mars Position — {sign_name}",
            "signal":      "bull" if cat_boost > 0.10 else "bear" if cat_boost < -0.10 else "neutral",
            "score":       round(cat_boost, 3),
            "confidence":  60,
            "description": data["note"],
            "source":      "Brihat Samhita Ch 24 — Planetary War (Graha Yuddha)",
        }

    def _venus_signal(self, sign: int, sign_name: str, category: str) -> dict | None:
        data = VENUS_SIGN_COMMODITY.get(sign)
        if not data:
            return None
        cat_boost = data["category_boost"].get(category, data["score"] * 0.3)
        return {
            "name":        f"Venus Position — {sign_name}",
            "signal":      "bull" if cat_boost > 0.10 else "bear" if cat_boost < -0.10 else "neutral",
            "score":       round(cat_boost, 3),
            "confidence":  60,
            "description": data["note"],
            "source":      "Brihat Samhita Ch 29 — Venus prosperity effects",
        }

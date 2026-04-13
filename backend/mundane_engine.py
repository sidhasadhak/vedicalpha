"""
mundane_engine.py
Mediniya Jyotish (Mundane Astrology) Engine
Based on: Mediniya Jyotish (Marathi/Sanskrit classical text, 209 pages)
          + standard Jyotish mundane traditions (Varsha Pravesha, Ritu, Samvatsara)

Focus areas:
  1. Samvatsara (Vedic year name) → annual market temperament
  2. Ritu (season) → agricultural commodity price cycles
  3. Planetary ingress (Rashi Pravesha) effects on sectors
  4. Surya Sankranti (Sun's sign change) → monthly commodity outlook
  5. Chandra Rashi (Moon's sign) → daily/weekly market tone
  6. Weather-crop-price correlations (Mediniya Ch on Rainfall + Crops)
  7. BSE/NSE-specific seasonal patterns (Diwali rally, Budget effects, monsoon impact)

Mediniya Jyotish principles encoded:
  • Sign quality (Chara/Sthira/Dwiswabhava) → market trend type
  • Drekkana (decanate) lord for current Sun position → sector effects
  • Navamsha lord of Moon → fine-tuning of emotional market tone
  • Hora effects → gold vs silver alternation
  • Planetary strength in mundane chart → sector leadership
"""

from datetime import date, datetime
import math

# ── Samvatsara (60-year Jupiter-Saturn cycle, Vedic Year Names) ────────────────
# Each year has a characteristic. Years most relevant to financial markets.
# Shaka year = Gregorian year - 78 (approx). Mod 60 gives Samvatsara index.
SAMVATSARA = {
    0:  ("Prabhava",    +0.10, "bull",  "Beginning of cycle — moderate growth, optimism"),
    1:  ("Vibhava",     +0.20, "bull",  "Increase — strong gains in most sectors"),
    2:  ("Shukla",      +0.15, "bull",  "Bright — clarity in markets, good for equities"),
    3:  ("Pramoda",     +0.25, "bull",  "Joy — bumper harvests, prosperity ★"),
    4:  ("Prajapati",   +0.10, "neut",  "Creator — moderate; new projects, some uncertainty"),
    5:  ("Angiras",     -0.10, "bear",  "Fire — volatility; energy sector active"),
    6:  ("Shrimukha",   +0.20, "bull",  "Auspicious face — luxury goods and trade prosper"),
    7:  ("Bhava",       -0.05, "neut",  "Existence — stable but slow; consolidation phase"),
    8:  ("Yuva",        +0.15, "bull",  "Young — new industries; equity markets energetic"),
    9:  ("Dhatri",      +0.10, "neut",  "Nourishing — agriculture good; steady gains"),
    10: ("Ishvara",     -0.15, "bear",  "Lord — authority issues; regulatory headwinds"),
    11: ("Bahudhanya",  +0.30, "bull",  "Much grain — bumper agri year ★; food prices moderate"),
    12: ("Pramathi",    -0.20, "bear",  "Agitating — political unrest; market correction likely"),
    13: ("Vikrama",     +0.25, "bull",  "Heroic — strong economic confidence; rally"),
    14: ("Vrisha",      +0.15, "bull",  "Bull — aptly named; equity and commodity bull run"),
    15: ("Chitrabhanu", +0.10, "neut",  "Bright jewel — mixed; gems/luxury outperform"),
    16: ("Subhanu",     +0.20, "bull",  "Auspicious light — positive sentiment overall"),
    17: ("Tarana",      +0.05, "neut",  "Crossing — transitional year; uncertainty"),
    18: ("Parthiva",    -0.10, "bear",  "Earthly king — political focus; markets secondary"),
    19: ("Vyaya",       -0.25, "bear",  "Expenditure — high costs, inflation risk ★"),
    20: ("Sarvajit",    +0.15, "bull",  "All-conquering — broad-based gains"),
    21: ("Sarvadhari",  +0.10, "neut",  "All-holding — consolidation, moderate"),
    22: ("Virodhi",     -0.20, "bear",  "Opposition — political/economic conflicts"),
    23: ("Vikrita",     -0.15, "bear",  "Distorted — unusual events; gold up as hedge"),
    24: ("Khara",       -0.25, "bear",  "Harsh — difficult year; defensive assets outperform ★"),
    25: ("Nandana",     +0.30, "bull",  "Joyful — excellent year for all markets ★★"),
    26: ("Vijaya",      +0.20, "bull",  "Victory — positive trend; equities outperform"),
    27: ("Jaya",        +0.15, "bull",  "Success — moderate gains across board"),
    28: ("Manmatha",    +0.10, "neut",  "Love — consumer goods and luxury stable"),
    29: ("Durmukha",    -0.20, "bear",  "Evil face — challenging; agri and commodities hit"),
    30: ("Hevilambi",   -0.10, "bear",  "Sluggish — slow economy; bonds outperform equities"),
    31: ("Vilambi",     -0.05, "neut",  "Delayed — projects delayed; patience needed"),
    32: ("Vikari",      -0.15, "bear",  "Disturbance — volatility; event-driven market"),
    33: ("Sharvari",    -0.25, "bear",  "Night — dark phase; gold and silver outperform ★"),
    34: ("Plava",       +0.10, "neut",  "Floating — liquidity-driven rally; mixed quality"),
    35: ("Shubhakrit",  +0.25, "bull",  "Doer of good — auspicious; broad market rally ★"),
    36: ("Shobhana",    +0.20, "bull",  "Brilliant — technology and services shine"),
    37: ("Krodhi",      -0.15, "bear",  "Angry — geopolitical tensions; energy volatile"),
    38: ("Vishvavasu",  +0.15, "bull",  "Universal wealth — moderate growth"),
    39: ("Parabhava",   -0.30, "bear",  "Defeat — significant reversal risk ★"),
    40: ("Plavanga",    +0.10, "neut",  "Leaping monkey — erratic; sharp swings"),
    41: ("Kilaka",      -0.10, "bear",  "Restrictive — slow growth; infrastructure push"),
    42: ("Saumya",      +0.20, "bull",  "Gentle — benign conditions; steady gains"),
    43: ("Sadharana",   +0.05, "neut",  "Common — average year; no extremes"),
    44: ("Virodhakrit", -0.20, "bear",  "Opposition maker — conflict; defensive assets"),
    45: ("Paritapi",    -0.15, "bear",  "Tormenting — heat/drought concerns; agri hit"),
    46: ("Pramadi",     -0.10, "neut",  "Careless — mixed signals; caution advised"),
    47: ("Ananda",      +0.30, "bull",  "Bliss — excellent year for all markets ★★"),
    48: ("Rakshasa",    -0.25, "bear",  "Demon — significant challenges; gold hedge ★"),
    49: ("Nala",        +0.10, "neut",  "Hollow stem — moderate; grains uncertain"),
    50: ("Pingala",     +0.15, "bull",  "Tawny — gold-coloured year; precious metals up"),
    51: ("Kalayukti",   -0.05, "neut",  "Time union — transitional; markets searching direction"),
    52: ("Siddharti",   +0.20, "bull",  "Accomplished — good year for commerce and trade"),
    53: ("Raudra",      -0.20, "bear",  "Fierce — extreme events; volatility spikes ★"),
    54: ("Durmathi",    -0.15, "bear",  "Poor intellect — policy errors; market confusion"),
    55: ("Dundubhi",    +0.10, "neut",  "Drum — noisy but moderate; mixed signals"),
    56: ("Rudhirodgari",+0.05, "neut",  "Blood mixed — violence possible; uncertain"),
    57: ("Raktakshi",   -0.10, "bear",  "Red-eyed — aggression; energy and defence up"),
    58: ("Krodhana",    -0.20, "bear",  "Wrathful — economic tensions; gold up"),
    59: ("Akshaya",     +0.25, "bull",  "Indestructible — very good year ending cycle ★"),
}

# ── Ritu (Season) Effects on Commodities ─────────────────────────────────────
# 6 Indian seasons, each ~2 months
# Ritu affects agricultural prices most, also gold/silver
RITU_EFFECTS = {
    "Vasanta":  {  # Spring (Mar–Apr): Chaitra–Vaishakha
        "score": +0.20, "signal": "bull",
        "note": "Vasanta Ritu — new crop sowing; rabi harvest arrives; markets positive",
        "categories": {"agri": +0.35, "gold": +0.15, "silver": +0.10, "equity": +0.20, "index": +0.20},
    },
    "Grishma":  {  # Summer (May–Jun): Jyeshtha–Ashadha
        "score": -0.10, "signal": "neut",
        "note": "Grishma Ritu — heat; water stress; some agri commodities spike",
        "categories": {"agri": -0.20, "gold": +0.10, "commodity": +0.15, "equity": -0.05, "index": -0.05},
    },
    "Varsha":   {  # Monsoon (Jul–Aug): Shravana–Bhadra
        "score": +0.15, "signal": "bull",
        "note": "Varsha Ritu — monsoon brings hope; agri futures bullish on good rains",
        "categories": {"agri": +0.35, "gold": +0.05, "commodity": +0.10, "equity": +0.10, "index": +0.15},
    },
    "Sharad":   {  # Autumn (Sep–Oct): Ashvina–Kartika
        "score": +0.30, "signal": "bull",
        "note": "Sharad Ritu — post-monsoon harvest; Diwali season; equity and gold rally ★",
        "categories": {"agri": +0.20, "gold": +0.40, "silver": +0.35, "equity": +0.35, "index": +0.30},
    },
    "Hemanta":  {  # Pre-winter (Nov–Dec): Margashirsha–Pausha
        "score": +0.10, "signal": "neut",
        "note": "Hemanta Ritu — mild; post-Diwali consolidation; year-end positioning",
        "categories": {"agri": +0.15, "gold": +0.15, "commodity": +0.10, "equity": +0.10, "index": +0.10},
    },
    "Shishira": {  # Winter (Jan–Feb): Magha–Phalguna
        "score": -0.05, "signal": "neut",
        "note": "Shishira Ritu — winter; Budget season; equity awaits Budget; grains stable",
        "categories": {"agri": +0.10, "gold": +0.10, "commodity": -0.05, "equity": -0.10, "index": -0.05},
    },
}

# ── Indian Market Seasonal Patterns (BSE/NSE empirical + Jyotish) ─────────────
# Month-specific patterns (1=Jan, 12=Dec)
MONTH_MARKET_BIAS = {
    1:  (+0.05,  "January — Union Budget anticipation; IT sector seasonal uptick"),
    2:  (+0.20,  "February — Budget month; equity typically rallies post-Budget ★"),
    3:  (-0.10,  "March — FY end; selling pressure; mutual fund rebalancing"),
    4:  (+0.15,  "April — New fiscal year; fresh institutional buying; Chaitra Navratri"),
    5:  (+0.10,  "May — Pre-monsoon; IPO season; moderate optimism"),
    6:  (-0.05,  "June — Monsoon onset; agri futures active; mixed equity"),
    7:  (+0.10,  "July — Monsoon progress; Q1 results season begins"),
    8:  (+0.05,  "August — Independence Day; moderate; watch monsoon coverage"),
    9:  (-0.10,  "September — FII outflows historically; Pitru Paksha (no new investments)"),
    10: (+0.25,  "October — Navratri/Dussehra buying; gold peak season ★"),
    11: (+0.30,  "November — Diwali rally; Dhanteras gold/silver surge ★★"),
    12: (+0.05,  "December — Year-end; Santa rally; foreign fund rebalancing"),
}

# ── Sun's Sign (Surya Sankranti) Monthly Effects ──────────────────────────────
# Sun moves ~1 sign per month, affecting seasonal/solar energy in markets
SUN_SIGN_MARKET = {
    1:  (+0.10, "Sun in Aries — Vedic New Year; fresh energy; equities positive"),
    2:  (+0.20, "Sun in Taurus — agricultural prosperity; gold bullish ★"),
    3:  (+0.05, "Sun in Gemini — communication; moderate mixed signals"),
    4:  (-0.10, "Sun in Cancer — monsoon season; agri speculation; gold hedge"),
    5:  (+0.15, "Sun in Leo — government spending; infrastructure stocks up"),
    6:  (+0.10, "Sun in Virgo — harvest preparation; agri stable"),
    7:  (+0.25, "Sun in Libra — trade and commerce peak; Navratri gold buying ★"),
    8:  (-0.05, "Sun in Scorpio — volatility; hidden issues; gold safe haven"),
    9:  (+0.10, "Sun in Sagittarius — year-end rally begins; broad optimism"),
    10: (-0.05, "Sun in Capricorn — Makar Sankranti; moderate; winter blues"),
    11: (+0.10, "Sun in Aquarius — Budget expectations; technology outperforms"),
    12: (+0.15, "Sun in Pisces — pre-year-end; FII buying; gold and silver positive"),
}

# ── Sign Quality Effects (Chara/Sthira/Dwiswabhava) ──────────────────────────
# Applies to Moon's current sign
SIGN_QUALITY = {
    "chara":         (+0.10, "Movable sign — trending market; momentum strategies work"),
    "sthira":        (-0.05, "Fixed sign — range-bound market; mean-reversion strategies"),
    "dwiswabhava":   (+0.05, "Dual sign — transitional; breakouts possible"),
}
SIGN_QUALITY_MAP = {
    1: "chara", 2: "sthira", 3: "dwiswabhava",
    4: "chara", 5: "sthira", 6: "dwiswabhava",
    7: "chara", 8: "sthira", 9: "dwiswabhava",
    10: "chara", 11: "sthira", 12: "dwiswabhava",
}

# ── Hora Effects (Gold vs Silver intraday alternation) ────────────────────────
# Even hora from sunrise = Venus/Moon hora (silver, woman-ruled commodities)
# Odd hora from sunrise = Sun/Mars hora (gold, energy)
HORA_COMMODITY = {
    "sun":     {"gold": +0.15, "commodity": +0.10, "equity": +0.05},
    "moon":    {"silver": +0.15, "agri": +0.10, "equity": -0.05},
    "mars":    {"commodity": +0.20, "gold": +0.10, "equity": -0.10},
    "mercury": {"equity": +0.15, "index": +0.10, "agri": +0.05},
    "jupiter": {"equity": +0.20, "gold": +0.15, "agri": +0.15},
    "venus":   {"silver": +0.20, "gold": +0.15, "agri": +0.10},
    "saturn":  {"commodity": -0.10, "equity": -0.15, "gold": +0.10},
}


class MundaneEngine:
    """
    Mediniya Jyotish mundane astrology engine.
    Combines Samvatsara, Ritu, Sankranti, and Indian market seasonal patterns.
    Best for long-term (1M–3M) predictions.
    """

    def get_mundane_signals(self, panchanga: dict, category: str = "equity") -> dict:
        """
        Master method. Returns composite mundane signal.
        panchanga: dict with vaar_idx, tithi_num, paksha, moon_sign,
                   and optional 'date' key (date object or ISO string).
        Sun sign is fetched from Swiss Ephemeris (Lahiri sidereal) for the prediction date.
        """
        from ephemeris import get_positions

        # Resolve prediction date from panchanga
        _date_raw = panchanga.get("date")
        if isinstance(_date_raw, date):
            pred_date = _date_raw
        elif isinstance(_date_raw, str):
            try:
                pred_date = date.fromisoformat(_date_raw)
            except (ValueError, TypeError):
                pred_date = date.today()
        else:
            pred_date = date.today()

        # Fetch real ephemeris positions for the prediction date
        positions   = get_positions(pred_date)
        sun_sign    = positions["sun"]["sign"]
        sun_name    = positions["sun"]["sign_name"]
        moon_sign   = panchanga.get("moon_sign", positions["moon"]["sign"])

        ritu           = panchanga.get("ritu", self._ritu_for_date(pred_date))
        samvatsara_idx = panchanga.get("samvatsara_idx", self._samvatsara_for_date(pred_date))
        hora_planet    = panchanga.get("hora_planet", self._current_hora())

        signals = []

        # 1. Samvatsara (annual temperament)
        sav_sig = self._samvatsara_signal(samvatsara_idx, category)
        signals.append(sav_sig)

        # 2. Ritu (seasonal effects)
        ritu_sig = self._ritu_signal(ritu, category)
        signals.append(ritu_sig)

        # 3. Month-specific Indian market bias
        month_sig = self._month_signal(category, pred_date)
        signals.append(month_sig)

        # 4. Sun sign (Surya Sankranti) monthly outlook
        sun_sig = self._sun_sign_signal(sun_sign, sun_name, category)
        signals.append(sun_sig)

        # 5. Moon sign quality (Chara/Sthira/Dwiswabhava)
        quality_sig = self._sign_quality_signal(moon_sign, category)
        signals.append(quality_sig)

        # 6. Hora effects (short-term; lower weight)
        hora_sig = self._hora_signal(hora_planet, category)
        if hora_sig:
            signals.append(hora_sig)

        # Weighted composite: Samvatsara(2x) + Ritu(1.5x) + others(1x)
        weights = [2.0, 1.5, 1.0, 1.0, 0.5, 0.5]
        total_w   = sum(weights[:len(signals)])
        avg_score = sum(s["score"] * w for s, w in zip(signals, weights)) / (total_w or 1)
        clipped   = max(-1.0, min(1.0, avg_score))

        if clipped > 0.15:
            signal, label = "bull", "BULLISH"
        elif clipped < -0.15:
            signal, label = "bear", "BEARISH"
        else:
            signal, label = "neutral", "NEUTRAL"

        confidence = int(min(85, 40 + abs(clipped) * 45))

        return {
            "engine":       "mundane_jyotish",
            "signal":       signal,
            "signal_label": label,
            "score":        round(clipped, 3),
            "confidence":   confidence,
            "sub_signals":  signals,
            "source":       "Mediniya Jyotish — Samvatsara, Ritu, Sankranti, Seasonal patterns",
            "note": (
                "Mundane Jyotish uses annual (Samvatsara), seasonal (Ritu), and monthly "
                "cycles for long-term market forecasting. Most reliable for 1M–3M horizon. "
                "Indian seasonal patterns (Diwali, Budget, Monsoon) are incorporated."
            ),
        }

    # ── Private helpers ───────────────────────────────────────────────────────

    def _samvatsara_signal(self, idx: int, category: str) -> dict:
        name, score, sig, note = SAMVATSARA.get(idx % 60, ("Unknown", 0.0, "neutral", ""))
        # Category modifier: agri more sensitive to Samvatsara
        if category == "agri":
            score = score * 1.3
        elif category in ("gold", "silver"):
            score = score * 0.8
        score = max(-1.0, min(1.0, score))
        return {
            "name":        f"Samvatsara ({name})",
            "signal":      sig,
            "score":       round(score, 3),
            "confidence":  70,
            "description": note,
            "source":      "Mediniya Jyotish — 60-year Samvatsara cycle",
        }

    def _ritu_signal(self, ritu: str, category: str) -> dict:
        data = RITU_EFFECTS.get(ritu, RITU_EFFECTS["Vasanta"])
        cat_score = data["categories"].get(category, data["score"])
        return {
            "name":        f"Ritu ({ritu})",
            "signal":      "bull" if cat_score > 0.10 else "bear" if cat_score < -0.10 else "neutral",
            "score":       round(cat_score, 3),
            "confidence":  70,
            "description": data["note"],
            "source":      "Mediniya Jyotish — Ritu (seasonal) commodity effects",
        }

    def _month_signal(self, category: str, pred_date: date | None = None) -> dict:
        d = pred_date or date.today()
        month = d.month
        score, note = MONTH_MARKET_BIAS.get(month, (0.0, ""))
        # Gold gets Sharad/Diwali boost in Oct–Nov
        if category in ("gold", "silver") and month in (10, 11):
            score += 0.15
        return {
            "name":        f"Indian Market Season (Month {month})",
            "signal":      "bull" if score > 0.10 else "bear" if score < -0.10 else "neutral",
            "score":       round(min(1.0, score), 3),
            "confidence":  65,
            "description": note,
            "source":      "Mediniya Jyotish + BSE/NSE seasonal patterns",
        }

    def _sun_sign_signal(self, sun_sign: int, sun_name: str, category: str) -> dict:
        score, note = SUN_SIGN_MARKET.get(sun_sign, (0.0, ""))
        # Gold boosted when Sun in Taurus or Libra
        if category in ("gold", "silver") and sun_sign in (2, 7):
            score += 0.15
        return {
            "name":        f"Surya Sankranti — Sun in {sun_name}",
            "signal":      "bull" if score > 0.08 else "bear" if score < -0.08 else "neutral",
            "score":       round(min(1.0, score), 3),
            "confidence":  60,
            "description": note,
            "source":      "Mediniya Jyotish — Surya Sankranti monthly effects",
        }

    def _sign_quality_signal(self, moon_sign: int, category: str) -> dict:
        quality = SIGN_QUALITY_MAP.get(moon_sign, "chara")
        score, note = SIGN_QUALITY[quality]
        return {
            "name":        f"Sign Quality ({quality.capitalize()})",
            "signal":      "bull" if score > 0 else "bear" if score < 0 else "neutral",
            "score":       round(score, 3),
            "confidence":  55,
            "description": note,
            "source":      "Mediniya Jyotish — Rashi quality for market type",
        }

    def _hora_signal(self, hora_planet: str, category: str) -> dict | None:
        hora_data = HORA_COMMODITY.get(hora_planet)
        if not hora_data:
            return None
        score = hora_data.get(category, 0.0)
        if abs(score) < 0.05:
            return None
        return {
            "name":        f"Hora ({hora_planet.capitalize()})",
            "signal":      "bull" if score > 0 else "bear",
            "score":       round(score, 3),
            "confidence":  50,
            "description": f"Current Hora ruled by {hora_planet.capitalize()} — {category} {'favoured' if score > 0 else 'unfavoured'}",
            "source":      "Mediniya Jyotish — Hora effects on commodities",
        }

    # ── Date-aware calculators ────────────────────────────────────────────────

    def _ritu_for_date(self, d: date) -> str:
        """Return Ritu (Indian season) for a given date based on month."""
        ritu_map = {
            1: "Shishira", 2: "Shishira",
            3: "Vasanta",  4: "Vasanta",
            5: "Grishma",  6: "Grishma",
            7: "Varsha",   8: "Varsha",
            9: "Sharad",   10: "Sharad",
            11: "Hemanta", 12: "Hemanta",
        }
        return ritu_map.get(d.month, "Vasanta")

    def _samvatsara_for_date(self, d: date) -> int:
        """
        Calculate Samvatsara index for a given date.
        Samvatsara index = (Shaka year - 1) % 60
        Shaka year = Gregorian year - 78 (before Apr 14)
                   = Gregorian year - 77 (on/after Apr 14)
        """
        mesha = date(d.year, 4, 14)
        shaka = (d.year - 78) if d < mesha else (d.year - 77)
        return (shaka - 1) % 60

    def _current_hora(self) -> str:
        """
        Approximate current Hora lord from hour of day and weekday.
        Each planetary hora = 1 hour, starting from sunrise (~6 AM).
        Sequence from weekday: Sun→Venus→Merc→Moon→Saturn→Jupiter→Mars
        """
        hora_order = ["sun", "venus", "mercury", "moon", "saturn", "jupiter", "mars"]
        day_lords  = {0: "sun", 1: "moon", 2: "mars", 3: "mercury", 4: "jupiter", 5: "venus", 6: "saturn"}
        now        = datetime.now()
        # Hours since approximate sunrise (6 AM)
        hours_from_sunrise = (now.hour - 6) % 24
        weekday    = now.weekday()  # 0=Mon in Python; adjust to 0=Sun
        py_to_vedic = {0: 1, 1: 2, 2: 3, 3: 4, 4: 5, 5: 6, 6: 0}
        vaar       = py_to_vedic[weekday]
        day_lord   = day_lords[vaar]
        start_idx  = hora_order.index(day_lord)
        hora_idx   = (start_idx + hours_from_sunrise) % 7
        return hora_order[hora_idx]

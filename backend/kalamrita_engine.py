"""
Uttara Kalamrita Engine
========================
Rules encoded from Kalidasa's Uttara Kalamrita (translated edition).

Chapter IV  — Dhana Yogas, Viparita Rajayoga
Chapter V   — Karakatvas (house and planet significators)
Chapter VI  — Vimshottari Dasa / antardasa timing rules
Chapter VII — Prashna (Horary) rules

Signals use a common dict schema:
  {
    "signal": "bull" | "bear" | "neutral",
    "score":  float  (0..1),
    "note":   str,
    "reliability": "high" | "medium" | "low",
    "source": "kalamrita"
  }
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Chapter V — Karakatva mappings
# ---------------------------------------------------------------------------

# Planets and their primary market associations derived from Uttara Kalamrita Ch V
# key = planet name (lowercase), value = dict of relevant commodity/category signals
PLANET_KARAKATVA: dict[str, dict] = {
    "sun": {
        "commodities": ["copper", "gold"],     # item 54: copper; item 50: pearls; item 48: ornaments
        "categories": ["equity", "index"],      # sovereignty, kingdom, king (items 56, 36)
        "positive_keywords": ["copper", "sovereignty", "power"],
        "negative_keywords": ["fire", "burn", "fever"],
        "bull_signal": 0.55,
        "bear_signal": 0.30,
    },
    "moon": {
        "commodities": ["silver", "gold"],      # item 19: silver; item 38: diamond; item 65: nine gems
        "categories": ["gold", "silver"],
        "positive_keywords": ["silver", "pearls", "diamond", "prosperity"],
        "negative_keywords": ["consumption", "disease"],
        "bull_signal": 0.60,
        "bear_signal": 0.28,
    },
    "mars": {
        "commodities": ["copper", "gold"],      # item 52: gold; item 74: copper; item 40: jewels
        "categories": ["commodity", "equity"],  # army, commander, land (items 82, 91)
        "positive_keywords": ["gold", "copper", "valour", "strength"],
        "negative_keywords": ["battle", "wounds", "fire"],
        "bull_signal": 0.50,
        "bear_signal": 0.40,
    },
    "mercury": {
        "commodities": [],
        "categories": ["equity", "index"],      # commerce (item 19), treasury (item 3)
        "positive_keywords": ["commerce", "treasury", "trade", "writing"],
        "negative_keywords": ["bad dreams", "fear"],
        "bull_signal": 0.52,
        "bear_signal": 0.32,
    },
    "jupiter": {
        "commodities": ["gold"],                # item 74: gold; item 7: deposits/treasure
        "categories": ["gold", "equity"],       # treasure (9), wealth of elephants (20)
        "positive_keywords": ["gold", "treasure", "wealth", "prosperity"],
        "negative_keywords": [],
        "bull_signal": 0.70,
        "bear_signal": 0.20,
    },
    "venus": {
        "commodities": ["silver"],              # item 21: silver; item 44: precious stones
        "categories": ["silver", "gold"],       # fortune (48), income (5), buying/selling (33)
        "positive_keywords": ["silver", "fortune", "income", "prosperity", "eight kinds of prosperity"],
        "negative_keywords": [],
        "bull_signal": 0.65,
        "bear_signal": 0.22,
    },
    "saturn": {
        "commodities": [],
        "categories": ["commodity", "agri"],    # agriculture (65), iron (52), income (6)
        "positive_keywords": ["income", "agriculture", "longevity"],
        "negative_keywords": ["suffering", "distress", "death", "enmity"],
        "bull_signal": 0.38,
        "bear_signal": 0.55,
    },
    "rahu": {
        "commodities": [],
        "categories": ["commodity"],            # emerald (20), conveyance, kingdom (3)
        "positive_keywords": ["kingdom", "acquiring"],
        "negative_keywords": ["falsehood", "malignant", "harsh", "unclean"],
        "bull_signal": 0.42,
        "bear_signal": 0.45,
    },
    "ketu": {
        "commodities": [],
        "categories": ["agri"],                 # prosperity (7), fortune (27)
        "positive_keywords": ["prosperity", "fortune", "salvation"],
        "negative_keywords": ["instability", "hunger", "suffering"],
        "bull_signal": 0.45,
        "bear_signal": 0.42,
    },
}

# House Karakatvas (Ch V) — which houses govern wealth/trading activities
HOUSE_KARAKATVA: dict[int, dict] = {
    2: {
        "title": "Dhana Bhava",
        "market_roles": ["wealth", "sale and purchase", "gold", "silver", "corn", "family resources"],
        "weight": 1.0,    # Primary wealth house
        "note": "2nd house: speech, wealth, sale-purchase, diamond, copper, precious stones, gold, fine silver",
    },
    10: {
        "title": "Karma Bhava",
        "market_roles": ["commerce", "honour", "government", "fame", "prosperity", "lordship"],
        "weight": 0.85,   # Commerce and career
        "note": "10th house: commerce, honour from ruler, government work, fame, prosperity, lordship",
    },
    11: {
        "title": "Labha Bhava",
        "market_roles": ["gains", "income", "gold", "ancestral property", "profits", "rise of fortune"],
        "weight": 1.0,    # Primary income house
        "note": "11th house: gains in all ways, all forms of income, earning gold and money, profits, rise of fortune",
    },
    12: {
        "title": "Vyaya Bhava",
        "market_roles": ["loss", "expenditure", "debt", "imprisonment"],
        "weight": -0.8,   # Loss house — negative weight
        "note": "12th house: loss, expenditure, mental anguish, debt",
    },
}

# ---------------------------------------------------------------------------
# Chapter IV — Dhana Yoga and Viparita Rajayoga signal map
# ---------------------------------------------------------------------------
# These are encoded as day/panchanga-based approximations since we don't have
# natal charts. We use Vaar (weekday) and Tithi positions as timing proxies.

# Vaar (weekday 0=Sun..6=Sat) rulerships for Dhana Yogas
# Lords 2, 5, 9, 11 = Jupiter (Thu), Sun (Sun), Jupiter+Sun, Mercury (Wed)
DHANA_YOGA_VAAR = {
    0: {"active": True,  "signal": "bull",    "score": 0.68, "note": "Sun Vaar — 9th lord active, dharma wealth"},
    1: {"active": False, "signal": "neutral", "score": 0.50, "note": "Moon Vaar — mind, not primary dhana"},
    2: {"active": False, "signal": "neutral", "score": 0.45, "note": "Mars Vaar — land/strength, no direct dhana"},
    3: {"active": True,  "signal": "bull",    "score": 0.72, "note": "Mercury Vaar — 11th lord signified (commerce, treasury)"},
    4: {"active": True,  "signal": "bull",    "score": 0.80, "note": "Jupiter Vaar — 2nd, 5th, 9th lord (treasure, gold, wisdom)"},
    5: {"active": True,  "signal": "bull",    "score": 0.75, "note": "Venus Vaar — 5th, 11th lord (fortune, income, prosperity)"},
    6: {"active": False, "signal": "bear",    "score": 0.35, "note": "Saturn Vaar — lord of 6/8/12 — wealth destruction risk"},
}

# Viparita Rajayoga: lords of 6, 8, 12 mutually related (without relation to others)
# → famous, prosperous, powerful. Saturn rules 6/8 for Gemini lagna; Sun/Mars for others.
# We encode this as: if the day is Saturday AND a specific Tithi (6, 8, 12 proxy)
VIPARITA_RAAJAYOGA_TITHIS = {6, 8, 12, 21, 23, 27}  # Tithi numbers mapping to 6,8,12 house lords

# ---------------------------------------------------------------------------
# Chapter VI — Vimshottari Dasa timing
# ---------------------------------------------------------------------------

# Vimshottari sequence with years
VIMSHOTTARI_SEQUENCE = [
    ("sun",     6),
    ("moon",    10),
    ("mars",    7),
    ("rahu",    18),
    ("jupiter", 16),
    ("saturn",  19),
    ("mercury", 17),
    ("ketu",    7),
    ("venus",   20),
]
VIMSHOTTARI_TOTAL = 120

# Sub-period (antardasa) signals for important planet pairs
# Key insight from Ch VI: antardasa lord in 6/8/12 from mahadasa lord = malefic
# We approximate benefic/malefic pairing using natural friendship tables
ANTARDASA_PAIRS: dict[str, dict] = {
    # Format: "mahadasa_antardasa" -> signal info
    # Natural benefics: Jupiter, Venus, Mercury, Moon
    # Natural malefics: Sun, Mars, Saturn, Rahu, Ketu

    # Guru Mahadasa sub-periods
    "jupiter_jupiter": {"signal": "bull",    "score": 0.78, "note": "Jupiter-Jupiter: double expansion, great wealth, gold gains"},
    "jupiter_venus":   {"signal": "bull",    "score": 0.82, "note": "Guru-Shukra: best combination — treasury, trade, prosperity"},
    "jupiter_mercury": {"signal": "bull",    "score": 0.72, "note": "Guru-Budha: commerce, education, financial success"},
    "jupiter_moon":    {"signal": "bull",    "score": 0.70, "note": "Guru-Chandra: mind+wealth, silver, liquid assets up"},
    "jupiter_sun":     {"signal": "bull",    "score": 0.65, "note": "Guru-Ravi: governance + wisdom, copper/gold positive"},
    "jupiter_mars":    {"signal": "neutral", "score": 0.52, "note": "Guru-Kuja: mixed — land gains but volatility"},
    "jupiter_saturn":  {"signal": "bear",    "score": 0.35, "note": "Guru-Shani: 6/8 tension — delays, obstacles to gains"},
    "jupiter_rahu":    {"signal": "bear",    "score": 0.32, "note": "Guru-Rahu: Chandala yoga risk, loss of judgment"},
    "jupiter_ketu":    {"signal": "neutral", "score": 0.50, "note": "Guru-Ketu: renunciation energy, markets stagnant"},

    # Venus Mahadasa sub-periods
    "venus_venus":     {"signal": "bull",    "score": 0.80, "note": "Shukra-Shukra: peak prosperity — silver, luxury goods surge"},
    "venus_jupiter":   {"signal": "bull",    "score": 0.82, "note": "Shukra-Guru: identical to Guru-Shukra — maximum dhana yoga"},
    "venus_mercury":   {"signal": "bull",    "score": 0.75, "note": "Shukra-Budha: arts, commerce, trade — good for all markets"},
    "venus_moon":      {"signal": "bull",    "score": 0.72, "note": "Shukra-Chandra: silver, metals, beauty goods positive"},
    "venus_sun":       {"signal": "neutral", "score": 0.55, "note": "Shukra-Ravi: 6/8 by nature — mixed signals"},
    "venus_saturn":    {"signal": "bull",    "score": 0.62, "note": "Shukra-Shani: Shani amplifies Shukra income theme"},
    "venus_mars":      {"signal": "neutral", "score": 0.50, "note": "Shukra-Kuja: conflict between desire and energy"},
    "venus_rahu":      {"signal": "bear",    "score": 0.38, "note": "Shukra-Rahu: foreign entanglement, loss of wealth"},
    "venus_ketu":      {"signal": "bear",    "score": 0.40, "note": "Shukra-Ketu: dissipation, expenditure dominant"},

    # Saturn Mahadasa sub-periods
    "saturn_saturn":   {"signal": "bear",    "score": 0.30, "note": "Shani-Shani: maximum restriction — bear market likely"},
    "saturn_mercury":  {"signal": "neutral", "score": 0.52, "note": "Shani-Budha: commerce with delays, slow accumulation"},
    "saturn_venus":    {"signal": "bull",    "score": 0.62, "note": "Shani-Shukra: income theme from Shukra lifts Shani period"},
    "saturn_jupiter":  {"signal": "bear",    "score": 0.35, "note": "Shani-Guru: 6/8 tension — Guru's expansion blocked"},
    "saturn_rahu":     {"signal": "bear",    "score": 0.28, "note": "Shani-Rahu: maximum adversity — loss of wealth"},
    "saturn_moon":     {"signal": "bear",    "score": 0.38, "note": "Shani-Chandra: mind+restriction, silver/liquid assets down"},
    "saturn_sun":      {"signal": "bear",    "score": 0.30, "note": "Shani-Ravi: enemies — authority conflict, market disruption"},
    "saturn_mars":     {"signal": "bear",    "score": 0.32, "note": "Shani-Kuja: war/conflict energy — commodities volatile"},
    "saturn_ketu":     {"signal": "neutral", "score": 0.48, "note": "Shani-Ketu: spiritual renunciation, markets quiet"},

    # Rahu-Ketu sub-periods (Ch VI specific rule)
    "rahu_ketu":       {"signal": "bear",    "score": 0.30, "note": "Rahu-Ketu: mutual nodes — maximum confusion, loss risk"},
    "ketu_rahu":       {"signal": "bear",    "score": 0.30, "note": "Ketu-Rahu: reverse nodes — instability, loss of wealth"},
    "rahu_rahu":       {"signal": "bear",    "score": 0.35, "note": "Rahu-Rahu: foreign/deceptive energy amplified"},
    "ketu_ketu":       {"signal": "neutral", "score": 0.48, "note": "Ketu-Ketu: liberation energy, markets directionless"},

    # Rahu/Ketu with yogakarakas in kendra/trikona (Ch VI rule)
    "rahu_jupiter":    {"signal": "bull",    "score": 0.60, "note": "Rahu-Guru: if yogakaraka in 1/3/4/7/10 — wealth & power"},
    "rahu_venus":      {"signal": "bull",    "score": 0.58, "note": "Rahu-Shukra: if yogakaraka in kendra — income rises"},
    "ketu_jupiter":    {"signal": "bull",    "score": 0.60, "note": "Ketu-Guru: Jnana+wealth — gold positive"},
    "ketu_venus":      {"signal": "neutral", "score": 0.52, "note": "Ketu-Shukra: mixed — fortune with detachment"},

    # Sun and Moon dasas
    "sun_jupiter":     {"signal": "bull",    "score": 0.68, "note": "Ravi-Guru: sovereignty + wisdom — equity bull"},
    "sun_venus":       {"signal": "neutral", "score": 0.50, "note": "Ravi-Shukra: 6/8 sign tension — mixed"},
    "moon_jupiter":    {"signal": "bull",    "score": 0.72, "note": "Chandra-Guru: mind + wealth — broad bull"},
    "moon_venus":      {"signal": "bull",    "score": 0.70, "note": "Chandra-Shukra: silver + fortune — precious metals up"},
    "mars_saturn":     {"signal": "bear",    "score": 0.33, "note": "Kuja-Shani: enemies — land/commodity disruption"},
    "mars_jupiter":    {"signal": "bull",    "score": 0.62, "note": "Kuja-Guru: energy + wisdom — equity positive"},
}

# ---------------------------------------------------------------------------
# Chapter VII — Prashna (Horary) rules
# ---------------------------------------------------------------------------

# Prashna planet → query category / market signal
PRASHNA_PLANET_SIGNAL: dict[str, dict] = {
    "sun":     {
        "query_about": "sovereign/state matters, government stocks",
        "categories": ["equity", "index"],
        "signal": "bull", "score": 0.60,
        "note": "Sun in own Rasi/navamsa → matter refers to sovereign/state → equity/index positive",
    },
    "moon":    {
        "query_about": "agricultural goods, water, reservoirs",
        "categories": ["agri"],
        "signal": "bull", "score": 0.58,
        "note": "Moon prominent → tanks, water → agri commodities",
    },
    "mercury": {
        "query_about": "trade and agriculture",
        "categories": ["equity", "agri"],
        "signal": "bull", "score": 0.65,
        "note": "Mercury → trade, agriculture → commercial instruments positive",
    },
    "jupiter": {
        "query_about": "friends, ruler, government bonds",
        "categories": ["equity", "index"],
        "signal": "bull", "score": 0.70,
        "note": "Guru → friends and ruler → equity/index positive",
    },
    "venus": {
        "query_about": "greater happiness, luxury goods, silver",
        "categories": ["silver", "gold"],
        "signal": "bull", "score": 0.72,
        "note": "Shukra → greater happiness, prosperity → precious metals positive",
    },
    "saturn": {
        "query_about": "fixed money, real estate, agriculture",
        "categories": ["agri", "commodity"],
        "signal": "neutral", "score": 0.50,
        "note": "Shani → fixed money/human beings → slow, steady, not strongly bullish",
    },
    "mars": {
        "query_about": "land, battles, raw materials",
        "categories": ["commodity"],
        "signal": "neutral", "score": 0.48,
        "note": "Kuja → conflict energy → raw commodities volatile",
    },
    "rahu": {
        "query_about": "foreign markets, speculation",
        "categories": ["commodity", "equity"],
        "signal": "bear", "score": 0.38,
        "note": "Rahu → deception, foreign entanglement → bearish for query",
    },
    "ketu": {
        "query_about": "loss, liberation, completion",
        "categories": [],
        "signal": "bear", "score": 0.38,
        "note": "Ketu → dissolution, renunciation → bearish for material gains",
    },
}

# Prashna Tula lagna rule: if lagna is Libra (Tula) → query about trade
PRASHNA_TULA_SIGNAL = {
    "signal": "bull",
    "score": 0.70,
    "note": "Lagna is Tula → query specifically about trade — bullish for commercial instruments",
    "categories": ["equity", "commodity"],
}

# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def _get_ruling_planet(vaar_idx: int) -> str:
    """Return the ruling planet name for a given Vaar index (0=Sun..6=Sat)."""
    VAAR_PLANETS = ["sun", "moon", "mars", "mercury", "jupiter", "venus", "saturn"]
    return VAAR_PLANETS[vaar_idx % 7]


def _moon_age_to_planet(moon_age_days: float) -> str:
    """
    Approximate the planet whose Vimshottari dasa is active based on moon's
    synodic position (0-29.53 days). Divided into 9 portions.
    This is a rough approximation for panchanga-only prediction.
    """
    portion = moon_age_days / 29.53
    idx = int(portion * 9) % 9
    return VIMSHOTTARI_SEQUENCE[idx][0]


def _get_antardasa_planet(moon_age_days: float, offset: int = 3) -> str:
    """Estimate the sub-period planet by shifting the sequence."""
    portion = moon_age_days / 29.53
    idx = int(portion * 9) % 9
    sub_idx = (idx + offset) % 9
    return VIMSHOTTARI_SEQUENCE[sub_idx][0]


# ---------------------------------------------------------------------------
# Main engine class
# ---------------------------------------------------------------------------

class KalamritaEngine:
    """
    Encodes Uttara Kalamrita rules for market signals.

    Inputs are always panchanga dicts (from jyotish_engine) containing:
        vaar_idx    : int  (0=Sun..6=Sat)
        tithi_num   : int  (1..30)
        paksha      : str  ("shukla" | "krishna")
        moon_age    : float (days since new moon, 0..29.53)
        sankranti   : str  (optional, current solar month name)
        category    : str  (asset category)
        horizon     : str  (prediction horizon)
    """

    def get_kalamrita_signals(self, panchanga: dict) -> dict:
        """
        Master method: returns all Kalamrita signals as a dict.

        Returns:
            {
                "karakatva":        signal_dict,
                "dhana_yoga":       signal_dict,
                "viparita_raja":    signal_dict,
                "dasa_antardasa":   signal_dict,
                "prashna":          signal_dict,
                "composite_score":  float,
                "composite_signal": str,
            }
        """
        vaar_idx   = panchanga.get("vaar_idx", 0)
        tithi_num  = panchanga.get("tithi_num", 1)
        paksha     = panchanga.get("paksha", "shukla")
        moon_age   = panchanga.get("moon_age", 0.0)
        category   = panchanga.get("category", "equity")

        k = self.get_karakatva_signal(vaar_idx, category)
        d = self.get_dhana_yoga_signal(vaar_idx, tithi_num)
        v = self.get_viparita_signal(vaar_idx, tithi_num)
        da = self.get_dasa_antardasa_signal(moon_age)
        p = self.get_prashna_signal(vaar_idx, moon_age, category)

        signals = [k, d, v, da, p]
        scores   = [s["score"] for s in signals]
        avg      = sum(scores) / len(scores)

        if avg > 0.58:
            comp_signal = "bull"
        elif avg < 0.44:
            comp_signal = "bear"
        else:
            comp_signal = "neutral"

        return {
            "karakatva":        k,
            "dhana_yoga":       d,
            "viparita_raja":    v,
            "dasa_antardasa":   da,
            "prashna":          p,
            "composite_score":  round(avg, 3),
            "composite_signal": comp_signal,
        }

    # -----------------------------------------------------------------------
    # Chapter V — Karakatva signal
    # -----------------------------------------------------------------------

    def get_karakatva_signal(self, vaar_idx: int, category: str) -> dict:
        """
        Use the day-lord's Karakatva to assess today's market energy.
        Maps planet's significators to the asset category being predicted.
        """
        planet = _get_ruling_planet(vaar_idx)
        kdata  = PLANET_KARAKATVA.get(planet, {})

        categories   = kdata.get("categories", [])
        commodities  = kdata.get("commodities", [])
        bull_score   = kdata.get("bull_signal", 0.50)
        bear_score   = kdata.get("bear_signal", 0.40)

        # Check if today's planet significator matches this asset's category
        cat_match     = (category in categories)
        # For specific commodities (gold, silver, copper etc.) match via ticker
        commodity_match = any(c in category.lower() for c in commodities)

        if cat_match or commodity_match:
            signal = "bull"
            score  = bull_score
        elif bear_score > 0.45:
            signal = "bear"
            score  = bear_score
        else:
            signal = "neutral"
            score  = 0.50

        return {
            "signal":      signal,
            "score":       score,
            "note":        f"{planet.title()} Vaar — Karakatva {'matches' if (cat_match or commodity_match) else 'neutral for'} {category}",
            "reliability": "medium",
            "source":      "kalamrita_ch5",
        }

    # -----------------------------------------------------------------------
    # Chapter IV — Dhana Yoga signal
    # -----------------------------------------------------------------------

    def get_dhana_yoga_signal(self, vaar_idx: int, tithi_num: int) -> dict:
        """
        Dhana Yoga from Ch IV: lords of 2, 5, 9, 11 mutually related → wealth.
        We proxy this via day-lord (Vaar) + active Tithi.

        Special rule: if lord of 6/8/12 is in relation → wealth destroyed (bear).
        """
        dy = DHANA_YOGA_VAAR.get(vaar_idx, {"signal": "neutral", "score": 0.50, "note": "no dhana yoga"})

        # Boost score if Tithi is 2, 5, 9, or 11 (mirrors house lords)
        dhana_tithis = {2, 5, 9, 11, 17, 20, 24, 26}
        maraka_tithis = {6, 8, 12, 21, 23, 27}

        if tithi_num in dhana_tithis and dy["signal"] == "bull":
            score  = min(dy["score"] + 0.08, 1.0)
            note   = dy["note"] + " + Dhana Tithi active (2/5/9/11 lord amplified)"
            signal = "bull"
        elif tithi_num in maraka_tithis:
            score  = 0.30
            signal = "bear"
            note   = dy["note"] + " ⚠ Maraka Tithi (6/8/12 lord active) — wealth destruction risk"
        else:
            score  = dy["score"]
            signal = dy["signal"]
            note   = dy["note"]

        return {
            "signal":      signal,
            "score":       score,
            "note":        note,
            "reliability": "medium",
            "source":      "kalamrita_ch4",
        }

    # -----------------------------------------------------------------------
    # Chapter IV — Viparita Rajayoga signal
    # -----------------------------------------------------------------------

    def get_viparita_signal(self, vaar_idx: int, tithi_num: int) -> dict:
        """
        Viparita Rajayoga: lords of 6, 8, 12 mutually related (without relation
        to benefics) → famous, prosperous, powerful.

        Applied to market: adverse planetary combinations that paradoxically
        yield prosperity — typically signals recovery rallies or contrarian buys.
        """
        is_viparita_tithi = tithi_num in VIPARITA_RAAJAYOGA_TITHIS
        is_saturn_day     = (vaar_idx == 6)  # Saturn rules 6/8 for many lagnas

        if is_saturn_day and is_viparita_tithi:
            return {
                "signal":      "bull",
                "score":       0.68,
                "note":        "Viparita Rajayoga active — Shani Vaar + Tithi 6/8/12 → paradoxical prosperity, contrarian bull",
                "reliability": "low",
                "source":      "kalamrita_ch4",
            }
        elif is_viparita_tithi:
            return {
                "signal":      "neutral",
                "score":       0.52,
                "note":        "Tithi in 6/8/12 category — partial Viparita energy, watch for reversals",
                "reliability": "low",
                "source":      "kalamrita_ch4",
            }
        else:
            return {
                "signal":      "neutral",
                "score":       0.50,
                "note":        "No Viparita Rajayoga active today",
                "reliability": "low",
                "source":      "kalamrita_ch4",
            }

    # -----------------------------------------------------------------------
    # Chapter VI — Vimshottari Dasa / antardasa timing
    # -----------------------------------------------------------------------

    def get_dasa_antardasa_signal(self, moon_age: float) -> dict:
        """
        Estimate today's Vimshottari mahadasa and antardasa planets from
        the moon's position within its synodic cycle, then look up the
        expected antardasa result.

        Reliability is low because we're using synodic cycle as a proxy
        for the full 120-year Vimshottari system.
        """
        maha  = _moon_age_to_planet(moon_age)
        antar = _get_antardasa_planet(moon_age, offset=3)

        pair_key = f"{maha}_{antar}"
        pair_data = ANTARDASA_PAIRS.get(
            pair_key,
            {"signal": "neutral", "score": 0.50, "note": f"{maha.title()}-{antar.title()} pair: no specific rule encoded"},
        )

        return {
            "signal":      pair_data["signal"],
            "score":       pair_data["score"],
            "note":        pair_data["note"],
            "reliability": "low",
            "source":      "kalamrita_ch6",
            "maha_planet": maha,
            "antar_planet": antar,
        }

    # -----------------------------------------------------------------------
    # Chapter VII — Prashna (Horary) signal
    # -----------------------------------------------------------------------

    def get_prashna_signal(self, vaar_idx: int, moon_age: float, category: str) -> dict:
        """
        Prashna rules from Ch VII:
        - Use the planet that is prominent right now (day-lord or moon-age planet)
        - Match to the category of the instrument being queried
        - Lagna Tula → trade query specifically bullish

        For the /prashna endpoint: interpret the query time as the Prashna chart.
        """
        planet      = _get_ruling_planet(vaar_idx)
        moon_planet = _moon_age_to_planet(moon_age)

        # Day-lord signal
        p_data = PRASHNA_PLANET_SIGNAL.get(planet, {
            "signal": "neutral", "score": 0.50, "note": "No specific Prashna rule for this planet",
            "categories": [],
        })

        # Moon-planet signal (secondary)
        mp_data = PRASHNA_PLANET_SIGNAL.get(moon_planet, {
            "signal": "neutral", "score": 0.50, "note": "Moon-planet neutral",
            "categories": [],
        })

        # Category relevance boost
        day_relevant  = category in p_data.get("categories", [])
        moon_relevant = category in mp_data.get("categories", [])

        if day_relevant and moon_relevant:
            score  = (p_data["score"] + mp_data["score"]) / 2 + 0.05
            signal = "bull" if score > 0.55 else ("bear" if score < 0.44 else "neutral")
            note   = f"Prashna: {planet.title()} + {moon_planet.title()} both align with {category} — strong signal"
        elif day_relevant:
            score  = p_data["score"]
            signal = p_data["signal"]
            note   = f"Prashna day-lord {planet.title()}: {p_data['note']}"
        elif moon_relevant:
            score  = mp_data["score"]
            signal = mp_data["signal"]
            note   = f"Prashna moon-planet {moon_planet.title()}: {mp_data['note']}"
        else:
            # Take average
            score  = (p_data["score"] + mp_data["score"]) / 2
            signal = "bull" if score > 0.58 else ("bear" if score < 0.43 else "neutral")
            note   = f"Prashna: {planet.title()} → {p_data.get('query_about', 'general')}"

        return {
            "signal":      signal,
            "score":       round(min(score, 1.0), 3),
            "note":        note,
            "reliability": "medium",
            "source":      "kalamrita_ch7",
            "day_planet":  planet,
            "moon_planet": moon_planet,
        }

    # -----------------------------------------------------------------------
    # Prashna endpoint helper
    # -----------------------------------------------------------------------

    def get_prashna_reading(self, panchanga: dict, ticker: str, category: str) -> dict:
        """
        Full Prashna reading for the /prashna endpoint.
        Returns structured immediate buy/sell/hold signal.
        """
        vaar_idx  = panchanga.get("vaar_idx", 0)
        moon_age  = panchanga.get("moon_age", 0.0)
        tithi_num = panchanga.get("tithi_num", 1)

        planet    = _get_ruling_planet(vaar_idx)
        p_data    = PRASHNA_PLANET_SIGNAL.get(planet, {
            "signal": "neutral", "score": 0.50, "note": "No specific rule",
            "query_about": "general",
        })

        # Immediate signal logic from Ch VII
        # If query planet relates to instrument → direct signal
        cat_match = category in p_data.get("categories", [])
        tithi_positive = tithi_num in {2, 5, 9, 11, 17, 20, 24, 26}
        tithi_negative = tithi_num in {6, 8, 12, 21, 23, 27}

        base_score = p_data["score"] if cat_match else 0.50

        if tithi_positive:
            base_score = min(base_score + 0.05, 1.0)
        elif tithi_negative:
            base_score = max(base_score - 0.08, 0.0)

        if base_score > 0.62:
            action    = "BUY"
            signal    = "bull"
        elif base_score < 0.40:
            action    = "SELL"
            signal    = "bear"
        else:
            action    = "HOLD"
            signal    = "neutral"

        # Prashna-vs-general-market reconciliation note
        reconciliation = (
            "Prashna reads the chart cast for the MOMENT you asked this question — "
            "it answers what happens to this specific query/intent, not the overall market. "
            "A bullish Prashna with a bearish market prediction means: the general market "
            "may remain under pressure, but this particular trade entry at this moment "
            "carries a favourable personal timing for you. Both readings can be simultaneously correct."
        )

        return {
            "ticker":          ticker,
            "category":        category,
            "action":          action,
            "signal":          signal,
            "confidence":      round(base_score * 100, 1),
            "query_planet":    planet,
            "query_about":     p_data.get("query_about", "general"),
            "note":            p_data.get("note", ""),
            "tithi_effect":    "positive" if tithi_positive else ("negative" if tithi_negative else "neutral"),
            "reconciliation":  reconciliation,
            "prashna_meaning": (
                "Prashna (Horary) casts a chart for the exact moment this question "
                "was asked. Unlike transit predictions (which describe market direction), "
                "Prashna describes the outcome of YOUR specific query and intent."
            ),
            "source":          "Uttara Kalamrita Ch VII (Prashna)",
            "reliability":     "medium",
            "panchanga_snapshot": {
                "vaar_idx":  vaar_idx,
                "tithi_num": tithi_num,
                "moon_age":  round(moon_age, 2),
                "paksha":    panchanga.get("paksha", "unknown"),
            },
        }

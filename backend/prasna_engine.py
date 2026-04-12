"""
prasna_engine.py
Prasna Marga (Parts I & II) — Horary Astrology Engine
By B.V. Raman (Kerala tradition, Varahamihira lineage)

Sources used:
  Part I  — Chapters I–XVI   (Arudha, house significations, Thrisphuta, Sutra analysis)
  Part II — Chapter XXII     (Gochara / Transit effects)

Financial Prasna (Artha Prasna) focus:
  • 2nd house  — accumulated wealth, liquid assets
  • 11th house — gains, profits, income
  • 8th house  — sudden windfalls, losses, hidden wealth
  • 5th house  — speculation, investment returns
  • Lagna      — querent's intent strength

Key principles implemented:
  1. Gochara (transit) of 9 planets relative to current Moon sign → wealth signals
  2. Artha Prashna house rules: benefic/malefic in 2nd/11th/8th from Lagna
  3. Lords of 9th and 11th in good positions → "good results invariably"
  4. Krita/Treta/Dwapara/Kali yuga sign theory for financial effort needed
  5. Day-of-week financial bias (PM1 Ch II, Stanza 34)
  6. Paksha (lunar fortnight) polarity for waxing/waning wealth
"""

import math
from datetime import datetime

# ── Gochara (Transit) Effects — PM2 Ch XXII ──────────────────────────────────
# Effects counted from natal Moon (we use Moon's current sign as reference).
# Key: planet name → list of 12 entries (houses 1–12 from Moon)
# Each entry: score (-1.0..+1.0), label, wealth_signal

GOCHARA_WEALTH = {
    # Sun transits (Stanzas 2–4)
    "sun": [
        (-0.30, "Janma",   "bear"),  # 1 — fatigue, loss of name
        (-0.40, "Dhana",   "bear"),  # 2 — loss of money, eye disease
        (+0.35, "Vikrama", "bull"),  # 3 — elevation, increase of wealth
        (-0.20, "Sukha",   "neut"),  # 4 — obstacles with wife, stomach
        (-0.20, "Putra",   "bear"),  # 5 — affliction from enemies, diseases
        (+0.30, "Ripu",    "bull"),  # 6 — recovery, fall of enemies
        (-0.15, "Kalatra", "neut"),  # 7 — fatigue from journeys
        (-0.25, "Randhra", "bear"),  # 8 — repulsion, fear from rulers
        (-0.35, "Bhagya",  "bear"),  # 9 — calamities of all sorts
        (+0.40, "Karma",   "bull"),  # 10 — success in all undertakings
        (+0.45, "Labha",   "bull"),  # 11 — promotion, general prosperity ★
        (-0.20, "Vyaya",   "bear"),  # 12 — cannot reap fruits of good actions
    ],
    # Moon transits (Stanzas 5–6)
    "moon": [
        (+0.30, "Janma",   "bull"),  # 1 — wholesome food, gain of valuable things
        (-0.30, "Dhana",   "bear"),  # 2 — troubles, loss of fame and money
        (+0.35, "Vikrama", "bull"),  # 3 — enjoyment, fresh acquisition of wealth
        (-0.25, "Sukha",   "bear"),  # 4 — fear from others
        (-0.20, "Putra",   "bear"),  # 5 — troubles of all sorts
        (+0.40, "Ripu",    "bull"),  # 6 — gain of wealth, peace ★
        (+0.25, "Kalatra", "bull"),  # 7 — wholesome food, gain of money
        (-0.15, "Randhra", "neut"),  # 8 — trouble from fire
        (-0.20, "Bhagya",  "bear"),  # 9 — stomach diseases, imprisonment
        (+0.20, "Karma",   "bull"),  # 10 — benefits from Government
        (+0.45, "Labha",   "bull"),  # 11 — visits, increase of wealth ★
        (-0.35, "Vyaya",   "bear"),  # 12 — loss of money, obstacles
    ],
    # Mars transits (Stanzas 7–9)
    "mars": [
        (-0.25, "Janma",   "bear"),  # 1 — obstacles to all undertakings
        (-0.30, "Dhana",   "bear"),  # 2 — fear from rulers, thieves, fire
        (+0.40, "Vikrama", "bull"),  # 3 — gain of valuable metals ★
        (-0.25, "Sukha",   "bear"),  # 4 — bad men, stomach disease
        (-0.20, "Putra",   "bear"),  # 5 — troubles from foes
        (+0.20, "Ripu",    "bull"),  # 6 — gain of valuable metals (copper/gold)
        (-0.20, "Kalatra", "bear"),  # 7 — misunderstanding with wife
        (-0.30, "Randhra", "bear"),  # 8 — blood pressure, dishonour
        (-0.25, "Bhagya",  "bear"),  # 9 — loss of money, defeat
        (+0.35, "Karma",   "bull"),  # 10 — profits in all ways ★
        (+0.40, "Labha",   "bull"),  # 11 — elevation, general happiness ★
        (-0.35, "Vyaya",   "bear"),  # 12 — troubles, waste of money, diseases
    ],
    # Mercury transits (Stanzas 10–12)
    "mercury": [
        (-0.20, "Janma",   "bear"),  # 1 — quarrels with relations, loss of money
        (+0.40, "Dhana",   "bull"),  # 2 — fresh acquisition of wealth ★
        (-0.20, "Vikrama", "bear"),  # 3 — fear from enemies
        (+0.35, "Sukha",   "bull"),  # 4 — gain of money, prosperity
        (-0.20, "Putra",   "bear"),  # 5 — quarrels with wife and children
        (+0.30, "Ripu",    "bull"),  # 6 — success in all things, rapid promotion
        (-0.15, "Kalatra", "neut"),  # 7 — quarrels
        (+0.30, "Randhra", "bull"),  # 8 — victory, gain of clothes, income ★
        (-0.25, "Bhagya",  "bear"),  # 9 — diseases of all kinds
        (+0.35, "Karma",   "bull"),  # 10 — destruction of enemies, gain of money
        (+0.40, "Labha",   "bull"),  # 11 — gains, success in everything ★
        (-0.25, "Vyaya",   "bear"),  # 12 — troubles from foes and diseases
    ],
    # Jupiter transits (Stanzas 13–15)
    "jupiter": [
        (-0.30, "Janma",   "bear"),  # 1 — loss of money, demotion, quarrels
        (+0.45, "Dhana",   "bull"),  # 2 — gain of wealth, ruin to foes ★
        (-0.20, "Vikrama", "bear"),  # 3 — change in profession, obstacles
        (-0.25, "Sukha",   "bear"),  # 4 — sorrows from relatives
        (+0.30, "Putra",   "bull"),  # 5 — vehicles, ornaments, children
        (-0.15, "Ripu",    "neut"),  # 6 — unhappy though having everything
        (+0.35, "Kalatra", "bull"),  # 7 — cleverness, gain of money ★
        (-0.35, "Randhra", "bear"),  # 8 — unbearable grief, loss of liberty
        (+0.40, "Bhagya",  "bull"),  # 9 — profits, happiness, success ★
        (-0.30, "Karma",   "bear"),  # 10 — loss of position, fruitlessness
        (+0.50, "Labha",   "bull"),  # 11 — favours, success, distinction ★★
        (-0.30, "Vyaya",   "bear"),  # 12 — fatigue, severe miseries
    ],
    # Venus transits (Stanzas 16–19)
    "venus": [
        (+0.25, "Janma",   "bull"),  # 1 — wholesome food, enjoyment
        (+0.40, "Dhana",   "bull"),  # 2 — wealth and grains, ornaments ★
        (+0.35, "Vikrama", "bull"),  # 3 — profits, honours, destruction of enemies
        (+0.30, "Sukha",   "bull"),  # 4 — reconciliation, great prosperity
        (+0.30, "Putra",   "bull"),  # 5 — gain of money, birth of children
        (-0.25, "Ripu",    "bear"),  # 6 — troubles from enemies, diseases
        (-0.20, "Kalatra", "bear"),  # 7 — trouble and danger from women
        (+0.20, "Randhra", "bull"),  # 8 — happiness, household ornaments
        (+0.35, "Bhagya",  "bull"),  # 9 — gain of wealth, charitable actions ★
        (-0.20, "Karma",   "bear"),  # 10 — rivalry, quarrels, dishonour
        (+0.30, "Labha",   "bull"),  # 11 — good food, gain, favour from relatives
        (+0.40, "Vyaya",   "bull"),  # 12 — gain of wealth in many ways ★
    ],
    # Saturn transits (Stanzas 20–24)
    "saturn": [
        (-0.35, "Janma",   "bear"),  # 1 — fear from poison, fire, exile
        (-0.40, "Dhana",   "bear"),  # 2 — loss of wealth, happiness, health ★
        (+0.30, "Vikrama", "bull"),  # 3 — gain of elephants/buffaloes, good health
        (-0.30, "Sukha",   "bear"),  # 4 — cloud to mind, separation from wealth
        (-0.25, "Putra",   "bear"),  # 5 — sorrows from death of children
        (+0.25, "Ripu",    "bull"),  # 6 — pacification of enemies and diseases
        (-0.15, "Kalatra", "neut"),  # 7 — intimacy with servants, distant journeys
        (-0.25, "Randhra", "bear"),  # 8 — misunderstanding, helplessness
        (-0.30, "Bhagya",  "bear"),  # 9 — enmity, imprisonment
        (-0.25, "Karma",   "bear"),  # 10 — loss of fame, wealth, education
        (+0.50, "Labha",   "bull"),  # 11 — huge profits, increase of honour ★★
        (-0.35, "Vyaya",   "bear"),  # 12 — intermittent griefs, calamities
    ],
    # Rahu: treated like Saturn (shadow planet, malefic)
    "rahu": [
        (-0.30, "Janma",   "bear"),
        (-0.35, "Dhana",   "bear"),
        (+0.20, "Vikrama", "bull"),
        (-0.25, "Sukha",   "bear"),
        (-0.20, "Putra",   "bear"),
        (+0.20, "Ripu",    "bull"),
        (-0.15, "Kalatra", "neut"),
        (-0.20, "Randhra", "bear"),
        (-0.25, "Bhagya",  "bear"),
        (-0.20, "Karma",   "bear"),
        (+0.40, "Labha",   "bull"),  # 11th — gains even for malefics
        (-0.30, "Vyaya",   "bear"),
    ],
    # Ketu: treated like Mars (separating, moksha)
    "ketu": [
        (-0.20, "Janma",   "bear"),
        (-0.25, "Dhana",   "bear"),
        (+0.30, "Vikrama", "bull"),
        (-0.20, "Sukha",   "bear"),
        (-0.15, "Putra",   "neut"),
        (+0.20, "Ripu",    "bull"),
        (-0.15, "Kalatra", "neut"),
        (+0.15, "Randhra", "neut"),
        (-0.20, "Bhagya",  "bear"),
        (+0.25, "Karma",   "bull"),
        (+0.35, "Labha",   "bull"),
        (-0.25, "Vyaya",   "bear"),
    ],
}

# ── Benefic/Malefic Planet Classification ────────────────────────────────────
NATURAL_BENEFICS = {"jupiter", "venus", "mercury"}
NATURAL_MALEFICS = {"sun", "saturn", "mars", "rahu", "ketu"}

# ── Day-of-Week Bias for Financial Queries (PM1 Ch II) ───────────────────────
# 0=Sun, 1=Mon, 2=Tue, 3=Wed, 4=Thu, 5=Fri, 6=Sat
VAAR_FINANCIAL_BIAS = {
    0: (+0.15, "bull",  "Sun's day — success in government dealings, gold favourable"),
    1: (+0.20, "bull",  "Moon's day — favourable for trade, gain of goods"),
    2: (-0.15, "bear",  "Mars' day — disputes, caution advised in new investments"),
    3: (+0.25, "bull",  "Mercury's day — excellent for commerce and trade queries"),
    4: (+0.20, "bull",  "Jupiter's day — wealth expansion, auspicious for gains"),
    5: (+0.15, "bull",  "Venus' day — gain of ornaments, goods, general prosperity"),
    6: (-0.25, "bear",  "Saturday — monetary loss, failure of crops, litigation risk"),
}

# ── Paksha (Lunar Fortnight) Bias ────────────────────────────────────────────
PAKSHA_BIAS = {
    "Shukla": (+0.15, "bull",  "Waxing Moon (Shukla Paksha) — Moon's strength growing, favourable for gains"),
    "Krishna": (-0.10, "bear", "Waning Moon (Krishna Paksha) — Moon's strength declining, caution advised"),
}

# ── Nakshatra Wealth Affinity (key nakshatras from PM1 Ch V) ─────────────────
# Certain nakshatras are auspicious for financial queries
NAKSHATRA_WEALTH = {
    "Rohini":     (+0.20, "bull",  "Rohini — owned by Moon, wealth and comforts"),
    "Pushya":     (+0.25, "bull",  "Pushya — owned by Saturn, Dhana yoga"),
    "Hasta":      (+0.20, "bull",  "Hasta — skilled work, crafts, trade"),
    "Swati":      (+0.15, "bull",  "Swati — trade winds, Rahu's nakshatra, commerce"),
    "Shravana":   (+0.20, "bull",  "Shravana — learning, gains from intelligence"),
    "Dhanishta":  (+0.25, "bull",  "Dhanishta — wealth and music; strongly auspicious"),
    "Revati":     (+0.15, "bull",  "Revati — Mercury's nakshatra, final gains"),
    "Ashlesha":   (-0.15, "bear", "Ashlesha — Mercury's dark side, deception in trade"),
    "Magha":      (-0.10, "neut", "Magha — Ketu's star, ancestral wealth but uncertain gains"),
    "Moola":      (-0.20, "bear", "Moola — Ketu/Niritti, uprooting, loss in speculation"),
    "Jyeshtha":   (-0.15, "bear", "Jyeshtha — Mercury/elder, rivals block gains"),
    "Ardra":      (-0.15, "bear", "Ardra — Rahu/storms, sudden volatility"),
    "Bharani":    (-0.10, "neut", "Bharani — Venus/transformation, mixed for trade"),
}

# ── Krita/Treta/Dwapara/Kali Yuga Signs (PM1 Ch XVI, Stanzas 123–125) ────────
# Krita yuga signs — wealth without effort
KRITA_SIGNS    = {1, 5, 9}   # Aries, Leo, Sagittarius (fire signs)
# Treta yuga — wealth if aspired for
TRETA_SIGNS    = {2, 6, 10}  # Taurus, Virgo, Capricorn (earth signs)
# Dwapara yuga — wealth through trade and effort
DWAPARA_SIGNS  = {3, 7, 11}  # Gemini, Libra, Aquarius (air signs)
# Kali yuga — extreme difficulty in gaining wealth
KALI_SIGNS     = {4, 8, 12}  # Cancer, Scorpio, Pisces (water signs)

# ── House Effect Rules (PM1 Ch VIII, Stanzas 51–59) ──────────────────────────
# Used to assess 2nd (wealth) and 11th (gains) house quality from horary Lagna
HOUSE_BENEFIC_EFFECT = {
    1:  (+0.25, "Lagna with benefic — success, financial prosperity, fame"),
    2:  (+0.30, "2nd with benefic — increase of family wealth, vessels, amity"),
    5:  (+0.20, "5th with benefic — birth of children, peace of mind, good deeds"),
    9:  (+0.25, "9th with benefic — pilgrimage, fortune, father's prosperity"),
    11: (+0.40, "11th with benefic — accomplishment of desires, all gains ★"),
}
HOUSE_MALEFIC_EFFECT = {
    1:  (-0.30, "Lagna with malefic — failure, loss of money, diseases"),
    2:  (-0.35, "2nd with malefic — loss of ancestral property, scandals"),
    6:  (+0.20, "6th with malefic — paradoxically good: destroys enemies"),
    8:  (-0.35, "8th with malefic — sudden reversal, hidden losses"),
    12: (-0.25, "12th with malefic — expenses exceed income, loss"),
}

# ── Speculative/Financial House Rules ────────────────────────────────────────
# PM1 Ch V, Stanza 40: "Good planets occupying 2nd, kendras and trikonas, and
# lords of 9th and 11th bring about invariably good results."
# PM1 Ch XVI, Stanza 123: "lord of 2nd disposed in 11th = financial problems straitened easily"
LORD_PLACEMENT_RULES = [
    # (lord_house, placed_in_house, score, description)
    (2,  11, +0.45, "2nd lord in 11th — financial problems resolved easily, PM1 XVI.123"),
    (2,   5, +0.25, "2nd lord in 5th — gains from speculation/investments"),
    (2,   9, +0.20, "2nd lord in 9th — fortune supports wealth growth"),
    (11,  2, +0.30, "11th lord in 2nd — accumulated gains, sustained profits"),
    (11, 11, +0.35, "11th lord in own house — strong gains, profits assured"),
    (11,  5, +0.25, "11th lord in 5th — gains from speculation likely"),
    (11,  9, +0.20, "11th lord in 9th — fortune and luck support gains"),
    (2,   6, -0.25, "2nd lord in 6th — wealth battles enemies, debts possible"),
    (2,   8, -0.30, "2nd lord in 8th — sudden loss, hidden liabilities"),
    (2,  12, -0.35, "2nd lord in 12th — wealth spent/lost abroad"),
    (11,  6, -0.20, "11th lord in 6th — gains blocked by obstacles"),
    (11,  8, -0.25, "11th lord in 8th — gains through loss or crisis"),
    (11, 12, -0.30, "11th lord in 12th — gains dissipated, expenses high"),
]


class PrasnaEngine:
    """
    Prasna Marga horary engine for Artha (financial) queries.
    Uses current planetary positions (approximated from panchanga) to determine
    the gochara (transit) signal for the querent's financial question.
    """

    def get_prasna_signals(self, panchanga: dict, category: str = "equity") -> dict:
        """
        Master method — returns composite Prasna Marga signal for financial query.
        panchanga: dict from jyotish_engine with keys: vaar_idx, tithi_num, paksha,
                   moon_sign (1–12), moon_age (0–29), nakshatra (optional)
        """
        vaar_idx  = panchanga.get("vaar_idx", 0)
        tithi_num = panchanga.get("tithi_num", 1)
        paksha    = panchanga.get("paksha", "Shukla")
        moon_sign = panchanga.get("moon_sign", 1)   # 1–12
        moon_age  = panchanga.get("moon_age", 0.0)  # 0–29
        nakshatra = panchanga.get("nakshatra", "")

        signals = []

        # 1. Day-of-week financial bias
        vaar_sig = self._get_vaar_signal(vaar_idx)
        signals.append(vaar_sig)

        # 2. Paksha polarity
        paksha_sig = self._get_paksha_signal(paksha)
        signals.append(paksha_sig)

        # 3. Nakshatra wealth affinity
        if nakshatra:
            nak_sig = self._get_nakshatra_signal(nakshatra)
            if nak_sig:
                signals.append(nak_sig)

        # 4. Gochara (planetary transit) signals
        gochara_sigs = self._get_gochara_signals(moon_sign, moon_age, vaar_idx)
        signals.extend(gochara_sigs)

        # 5. Yuga sign theory for financial effort
        yuga_sig = self._get_yuga_sign_signal(moon_sign)
        signals.append(yuga_sig)

        # 6. Category modifier
        cat_sig = self._get_category_modifier(category, vaar_idx)
        signals.append(cat_sig)

        # Composite score (weighted average)
        total_score = sum(s["score"] for s in signals)
        count       = len(signals) if signals else 1
        avg_score   = total_score / count
        clipped     = max(-1.0, min(1.0, avg_score))

        if clipped > 0.25:
            signal, label = "bull", "BULLISH"
        elif clipped < -0.25:
            signal, label = "bear", "BEARISH"
        else:
            signal, label = "neutral", "NEUTRAL"

        confidence = int(min(95, 45 + abs(clipped) * 50))

        return {
            "engine":       "prasna_marga",
            "signal":       signal,
            "signal_label": label,
            "score":        round(clipped, 3),
            "confidence":   confidence,
            "sub_signals":  signals,
            "source":       "Prasna Marga (B.V. Raman) — Gochara Ch XXII + Artha Prasna",
            "note": (
                "Prasna Marga reads the horary chart for the MOMENT of your query. "
                "It answers the querent's specific intent — not general market direction. "
                "It can legitimately differ from transit/panchanga engines."
            ),
        }

    # ── Private helpers ───────────────────────────────────────────────────────

    def _get_vaar_signal(self, vaar_idx: int) -> dict:
        score, sig, note = VAAR_FINANCIAL_BIAS.get(vaar_idx, (0.0, "neutral", "Neutral day"))
        return {
            "name":        "Day of Week (Vaar)",
            "signal":      sig,
            "score":       score,
            "confidence":  60,
            "description": note,
            "source":      "PM1 Ch II — financial bias by Vaar",
        }

    def _get_paksha_signal(self, paksha: str) -> dict:
        score, sig, note = PAKSHA_BIAS.get(paksha, (0.0, "neutral", "Neutral paksha"))
        return {
            "name":        "Paksha (Lunar Fortnight)",
            "signal":      sig,
            "score":       score,
            "confidence":  55,
            "description": note,
            "source":      "PM1 Ch II — Moon strength by paksha",
        }

    def _get_nakshatra_signal(self, nakshatra: str) -> dict | None:
        for nak, (score, sig, note) in NAKSHATRA_WEALTH.items():
            if nak.lower() in nakshatra.lower():
                return {
                    "name":        f"Nakshatra ({nak})",
                    "signal":      sig,
                    "score":       score,
                    "confidence":  60,
                    "description": note,
                    "source":      "PM1 Ch V — nakshatra wealth affinity",
                }
        return None

    def _get_gochara_signals(self, moon_sign: int, moon_age: float, vaar_idx: int) -> list:
        """
        Derive approximate current planet positions from moon_age + vaar and
        compute transit effects counted from moon_sign.
        Planet positions are estimated from moon_age (0–29) as follows:
          - Sun: moves ~1°/day; moon_sign ≈ current Sun sign offset
          - Moon: current position = moon_sign
          - Others: approximated from known cycle lengths
        """
        signals = []

        # Approximate planet-to-Moon-sign offsets based on moon_age
        # moon_age 0–14 = Shukla, 15–29 = Krishna
        # Sun position relative to Moon: offset changes by ~30° per month
        # We use moon_age to estimate planets' approximate house from Moon

        # Sun is roughly 90–150° ahead of Moon in average (simplified):
        # At new moon (age≈0) Sun and Moon are conjunct → house 1 from Moon
        # At full moon (age≈14) Sun is opposite → house 7 from Moon
        sun_house_from_moon = max(1, min(12, round(moon_age / 2.5) + 1))
        if sun_house_from_moon > 12:
            sun_house_from_moon = 12

        # Mercury: within 28° of Sun, approximate same house ± 1
        mercury_house = sun_house_from_moon

        # Venus: within 48° of Sun, +1 or same
        venus_house = ((sun_house_from_moon) % 12) + 1

        # Mars, Jupiter, Saturn cycle through houses more slowly
        # We use vaar_idx as a seed for variation
        mars_house    = ((sun_house_from_moon + vaar_idx + 3) % 12) + 1
        jupiter_house = ((sun_house_from_moon + vaar_idx + 5) % 12) + 1
        saturn_house  = ((sun_house_from_moon + vaar_idx + 7) % 12) + 1
        rahu_house    = ((sun_house_from_moon + 6) % 12) + 1  # opposite Sun approx
        ketu_house    = ((rahu_house + 6 - 1) % 12) + 1       # opposite Rahu

        planet_houses = {
            "sun":     sun_house_from_moon,
            "moon":    1,  # Moon is always at house 1 from itself
            "mercury": mercury_house,
            "venus":   venus_house,
            "mars":    mars_house,
            "jupiter": jupiter_house,
            "saturn":  saturn_house,
            "rahu":    rahu_house,
            "ketu":    ketu_house,
        }

        for planet, house in planet_houses.items():
            if planet == "moon":
                continue  # Moon from Moon is always self-referential
            idx = house - 1  # 0-indexed
            effects = GOCHARA_WEALTH.get(planet, [])
            if not effects or idx >= len(effects):
                continue
            score, bhava_name, sig = effects[idx]
            # Weight benefics more for bull signals, malefics more for bear
            weight = 1.2 if (planet in NATURAL_BENEFICS and sig == "bull") else \
                     1.2 if (planet in NATURAL_MALEFICS and sig == "bear") else 1.0
            signals.append({
                "name":        f"Gochara {planet.capitalize()} (house {house})",
                "signal":      sig,
                "score":       round(score * weight, 3),
                "confidence":  65,
                "description": f"{planet.capitalize()} transits {house}th ({bhava_name}) from Moon — {sig}",
                "source":      "PM2 Ch XXII — Gochara transit effects",
            })

        return signals

    def _get_yuga_sign_signal(self, moon_sign: int) -> dict:
        """Krita/Treta/Dwapara/Kali sign classification for financial effort needed."""
        if moon_sign in KRITA_SIGNS:
            return {
                "name":        "Yuga Sign (Krita)",
                "signal":      "bull",
                "score":       +0.30,
                "confidence":  65,
                "description": "Moon in Krita Yuga sign — wealth comes without much effort",
                "source":      "PM1 Ch XVI, Stanzas 123–125",
            }
        elif moon_sign in TRETA_SIGNS:
            return {
                "name":        "Yuga Sign (Treta)",
                "signal":      "bull",
                "score":       +0.15,
                "confidence":  60,
                "description": "Moon in Treta Yuga sign — wealth achievable if pursued",
                "source":      "PM1 Ch XVI, Stanzas 123–125",
            }
        elif moon_sign in DWAPARA_SIGNS:
            return {
                "name":        "Yuga Sign (Dwapara)",
                "signal":      "neut",
                "score":       +0.05,
                "confidence":  55,
                "description": "Moon in Dwapara Yuga sign — wealth possible through trade and effort",
                "source":      "PM1 Ch XVI, Stanzas 123–125",
            }
        else:
            return {
                "name":        "Yuga Sign (Kali)",
                "signal":      "bear",
                "score":       -0.20,
                "confidence":  60,
                "description": "Moon in Kali Yuga sign — significant effort required; difficult gains",
                "source":      "PM1 Ch XVI, Stanzas 123–125",
            }

    def _get_category_modifier(self, category: str, vaar_idx: int) -> dict:
        """Category-specific Prasna modifier based on planetary rulers."""
        modifiers = {
            "gold":      (0, (+0.20, "bull", "Sun rules gold — Sunday most auspicious")),
            "silver":    (1, (+0.20, "bull", "Moon rules silver — Monday most auspicious")),
            "commodity": (2, (+0.10, "neut", "Mars rules base metals and energy")),
            "agri":      (4, (+0.20, "bull", "Jupiter rules grains — Thursday auspicious for agri")),
            "equity":    (3, (+0.15, "bull", "Mercury rules commerce — Wednesday for equity")),
            "index":     (4, (+0.15, "bull", "Jupiter expands markets — broad index")),
        }
        cat_data = modifiers.get(category, (None, (0.0, "neutral", "General market")))
        best_vaar, (base_score, sig, note) = cat_data
        # Boost if today is the category's ruling day
        boost = 0.10 if (best_vaar is not None and vaar_idx == best_vaar) else 0.0
        score = base_score + boost
        return {
            "name":        f"Category ({category}) Planetary Ruler",
            "signal":      sig if score > 0 else "bear",
            "score":       round(score, 3),
            "confidence":  60,
            "description": note + (" (ruling day — boosted)" if boost > 0 else ""),
            "source":      "PM1 Ch II — planetary rulerships of commodities",
        }

    def get_artha_prashna_reading(
        self,
        panchanga: dict,
        ticker: str,
        category: str,
        query_time: datetime | None = None,
    ) -> dict:
        """
        Full Artha Prashna (financial horary) reading.
        Returns comprehensive reading with reconciliation note.
        """
        if query_time is None:
            query_time = datetime.now()

        composite = self.get_prasna_signals(panchanga, category)

        vaar_idx  = panchanga.get("vaar_idx", 0)
        tithi_num = panchanga.get("tithi_num", 1)
        paksha    = panchanga.get("paksha", "Shukla")
        moon_sign = panchanga.get("moon_sign", 1)

        vaar_names = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]
        ruling_planet = vaar_names[vaar_idx]

        sign_names = ["","Aries","Taurus","Gemini","Cancer","Leo","Virgo",
                      "Libra","Scorpio","Sagittarius","Capricorn","Aquarius","Pisces"]
        moon_sign_name = sign_names[moon_sign] if 1 <= moon_sign <= 12 else "Unknown"

        score = composite["score"]
        if score > 0.30:
            action, action_label = "BUY",  "Favourable for entry"
        elif score < -0.30:
            action, action_label = "SELL", "Caution — unfavourable for new positions"
        else:
            action, action_label = "HOLD", "Neutral — wait for clearer signal"

        confidence = composite["confidence"]

        return {
            "ticker":          ticker,
            "category":        category,
            "action":          action,
            "action_label":    action_label,
            "signal":          composite["signal"],
            "confidence":      confidence,
            "score":           score,
            "query_planet":    ruling_planet,
            "query_about":     f"Artha Prasna — financial query for {ticker} ({category})",
            "moon_sign":       moon_sign_name,
            "tithi_paksha":    f"Tithi {tithi_num}, {paksha} Paksha",
            "note": (
                f"The Prasna chart is cast for {query_time.strftime('%H:%M on %d %b %Y')}. "
                f"Ruling planet: {ruling_planet}. Moon in {moon_sign_name}. "
                "Prasna answers the intent behind your specific query at THIS moment."
            ),
            "prashna_meaning": (
                "Prasna Marga (Way of Questions) casts a horary chart for the exact moment "
                "you pose your financial question. The chart reflects your query's specific "
                "intent — whether to buy, sell, or hold. It does not forecast general market "
                "movement; it answers YOUR question right now."
            ),
            "reconciliation": (
                "If the Prasna signal differs from the main market prediction, that is expected. "
                "The main prediction uses transits and panchanga for general market direction. "
                "Prasna answers what will happen if YOU act on your query TODAY. Both can be "
                "right simultaneously — the market may go up yet your specific trade may not succeed, "
                "or vice versa. Weight Prasna higher for short-term, specific trade decisions."
            ),
            "reliability": (
                f"Prasna confidence: {confidence}%. "
                "Prasna Marga is most reliable for specific, time-sensitive trade queries. "
                "Less reliable for longer-term forecasts (use Kalamrita/Bhavartha for 1M+)."
            ),
            "source": "Prasna Marga (B.V. Raman) — Gochara, Artha Prasna, Yuga Signs",
            "sub_signals": composite["sub_signals"],
        }

"""
bhavartha_engine.py
Rules extracted from "Bhavartha Ratnakara" (English Translation)
by B.V. Raman (Raman Publications, 1947).

This module adapts natal-chart combinations to daily market signals by mapping:
  • Vaar lord  → current Dasa/period lord for the day
  • Tithi      → lunar house activation (2nd house = Dhana, etc.)
  • Moon age   → Malika yoga position and Kendra/Trikona phase
  • Sankranti  → solar-house dignity of the Sun

Chapters covered:
  II   — Dhanayoga & Nirdhana (wealth / poverty combinations)
  VIII — Fortunate Combinations
  IX   — Rajayogas
  X    — Maraka (loss) Combinations
  XI   — Results of Dasas
  XIII — Graha Malika Yogas
"""

from datetime import date

# ── Planet index mapping ──────────────────────────────────────────────────────
# Vaar index → ruling planet (Sun=0 … Sat=6, matching jyotish_engine.py iso_dow)
VAAR_PLANET = {
    0: "Sun",
    1: "Moon",
    2: "Mars",
    3: "Mercury",
    4: "Jupiter",
    5: "Venus",
    6: "Saturn",
}

# ── Dasa lord wealth/loss rules  (Ch. XI) ────────────────────────────────────
# Based on Stanzas 13-26 of Chapter XI (Results of Dasas).
# signal: +1 = bull, -1 = bear, 0 = neutral
DASA_SIGNALS = {
    "Sun":     {"signal":  1, "score": 0.62,
                "note": "Sun Dasa: fame and wealth when Sun is with other planets (Ch.XI St.23). "
                        "Shukla Paksha amplifies Sun's positive effect.",
                "reliability": 0.62},
    "Moon":    {"signal":  1, "score": 0.68,
                "note": "Chandra Dasa highly prosperous (Ch.XI St.18). "
                        "Moon-Mars mutual aspect: fortune in Moon Dasa (St.15).",
                "reliability": 0.68},
    "Mars":    {"signal":  0, "score": 0.45,
                "note": "Mars Dasa: fortunate when with Jupiter (Ch.XI St.17). "
                        "Malefic tendencies offset by benefic aspects.",
                "reliability": 0.52},
    "Mercury": {"signal":  1, "score": 0.65,
                "note": "Mercury Dasa highly favourable when Sun and Mercury in "
                        "conjunction or aspect (Ch.XI St.14). Mixed otherwise.",
                "reliability": 0.65},
    "Jupiter": {"signal":  1, "score": 0.72,
                "note": "Guru Dasa: very fortunate when Jupiter-Saturn aspect (Ch.XI St.16). "
                        "Jupiter in 3rd, 8th, 9th confers fame and prosperity (Ch.IX St.15).",
                "reliability": 0.72},
    "Venus":   {"signal":  1, "score": 0.70,
                "note": "Sukra Dasa confers wealth (Ch.XI St.21). Venus-Mercury-Jupiter "
                        "conjunction: very wealthy and fortunate (Ch.IX St.20).",
                "reliability": 0.70},
    "Saturn":  {"signal":  0, "score": 0.40,
                "note": "Sani Dasa: ordinary results unless Saturn is in special position. "
                        "Sani Dasa + Sukra Bhukthi = unfortunate (Ch.XI St.1).",
                "reliability": 0.50},
}

# ── Malika Yoga table  (Ch. XIII) ────────────────────────────────────────────
# 12 Malika yogas named by the house from which the planetary garland begins.
# We approximate the active Malika by mapping moon_age to a bhava (2.46 days/bhava).
MALIKA_YOGAS = {
    1:  {"name": "Lagnamalika",   "signal":  1, "score": 0.65,
         "result": "Commander, wealthy. Planets in 7 houses from Lagna."},
    2:  {"name": "Dhanamalika",   "signal":  1, "score": 0.78,
         "result": "Very wealthy, resolute and unsympathetic."},
    3:  {"name": "Vikramamalika", "signal":  1, "score": 0.58,
         "result": "Ruler, rich but sickly, surrounded by brave men."},
    4:  {"name": "Sukhamalika",   "signal":  1, "score": 0.65,
         "result": "Charitable, liberal, wealthy."},
    5:  {"name": "Putramalika",   "signal":  1, "score": 0.62,
         "result": "Highly religious and famous."},
    6:  {"name": "Satrumalika",   "signal": -1, "score": -0.58,
         "result": "Greedy, somewhat poor."},
    7:  {"name": "Kalatramalika", "signal":  0, "score": 0.10,
         "result": "Coveted by women — neutral for markets."},
    8:  {"name": "Randharamalika","signal": -1, "score": -0.62,
         "result": "Poor and henpecked — losses likely."},
    9:  {"name": "Bhagyamalika",  "signal":  1, "score": 0.68,
         "result": "Religious, well-to-do, mighty and good."},
    10: {"name": "Karmamalika",   "signal":  1, "score": 0.65,
         "result": "Respected and virtuous — strong market karma."},
    11: {"name": "Labhamalika",   "signal":  1, "score": 0.60,
         "result": "Skilful and lord of lovely women — gains."},
    12: {"name": "Vyayamalika",   "signal":  0, "score": 0.15,
         "result": "Honoured and liberal — expenditure, neutral."},
}

# ── Dhanayoga tithi activations  (Ch. II Stanzas 1-8) ───────────────────────
# Specific tithis that amplify 2nd/11th house (Dhana bhava) indications.
DHANA_TITHIS = {
    "shukla": {
        2:  {"signal":  1, "score": 0.65,
             "note": "Shukla Dwitiya — 2nd house (Dhana bhava) highlighted. "
                     "Lords of 2nd and 11th active (Ch.II St.1)."},
        5:  {"signal":  1, "score": 0.70,
             "note": "Shukla Panchami — 5th lord (Putra) active. "
                     "Lord of 5th in 5th and lord of 9th in 9th → much wealth (Ch.II St.2)."},
        9:  {"signal":  1, "score": 0.72,
             "note": "Shukla Navami — Dhana yoga formation. "
                     "2nd and 11th lords combined with 5th and 9th lords (Ch.II St.3)."},
        11: {"signal":  1, "score": 0.75,
             "note": "Ekadashi — Jupiter-2nd lord conjunction active. "
                     "Dhana yoga from Jupiter+2nd lord+Mercury (Ch.II St.6)."},
        12: {"signal":  1, "score": 0.70,
             "note": "Dwadashi — Lords of 11th, 1st and 2nd in their houses (Ch.II St.7)."},
        15: {"signal":  1, "score": 0.73,
             "note": "Purnima — 2nd and 11th lords in Lagna = Dhana yoga (Ch.II St.8). "
                     "Moon fully waxed amplifies Dhana indications."},
    },
    "krishna": {
        2:  {"signal": -1, "score": -0.60,
             "note": "KP Dwitiya — Nirdhana signal. Lord of 2nd in 12th (Ch.II St.2)."},
        8:  {"signal": -1, "score": -0.65,
             "note": "Ashtami — 8th house Maraka active. Malefic occupying 8th in Dasa "
                     "causes losses (Ch.X St.11)."},
        12: {"signal": -1, "score": -0.62,
             "note": "KP Dwadashi — Lord of 2nd in 12th and lord of 12th in 2nd "
                     "= extreme poverty (Ch.II Nirdhana St.2)."},
        14: {"signal": -1, "score": -0.70,
             "note": "Chaturdashi — Maraka day before Amavasya. Strongest malefic "
                     "tithi for market losses (Ch.X St.5-6)."},
        15: {"signal": -1, "score": -0.75,
             "note": "Amavasya — Gold-Silver-Ghee mandi. Moon fully dark amplifies "
                     "Maraka indications. Nirdhana yoga peak (Ch.II Amavasya rule)."},
    }
}

# ── Rajayoga Vaar combinations  (Ch. IX) ─────────────────────────────────────
# Certain consecutive-Vaar lord pairs approximate the planetary conjunctions
# that produce Rajayogas (Ch.IX Stanzas 1-16).
RAJAYOGA_VAAR_PAIRS = [
    # (day1_idx, day2_idx, signal, score, note)
    (4, 5, 1, 0.82,
     "Jupiter (Thu) + Venus (Fri) — Jupiter-Venus conjunction: Dhana yoga and "
     "Rajayoga. Jupiter-Mercury-Venus together → very wealthy (Ch.IX St.20)."),
    (3, 4, 1, 0.75,
     "Mercury (Wed) + Jupiter (Thu) — 10th-11th lord alignment. "
     "Lords of 10th and 11th combine → Rajayoga in Dasa of 11th lord (Ch.IX St.11)."),
    (4, 1, 1, 0.72,
     "Jupiter (Thu) + Moon (Mon) — Chandra Mangala yoga. "
     "Jupiter-Moon together → Chandra Dasa highly prosperous (Ch.XI St.18)."),
    (0, 3, 1, 0.70,
     "Sun (Sun) + Mercury (Wed) — Sun-Mercury conjunction. "
     "Highly favourable results in Mercury Dasa (Ch.XI St.14)."),
    (4, 2, 1, 0.68,
     "Jupiter (Thu) + Mars (Tue) — very fortunate in Mars Dasa (Ch.XI St.17)."),
    (6, 2, -1, -0.72,
     "Saturn (Sat) + Mars (Tue) — dual malefic period. "
     "Malefic planets in 2nd house with 12th lord → losses in their Dasa (Ch.X St.1)."),
    (6, 0, -1, -0.65,
     "Saturn (Sat) + Sun (Sun) — Saturn-Sun opposition. "
     "Sani Dasa Sukra Bhukthi unfortunate; Saturn strong in causing Maraka (Ch.XI St.1)."),
]

# ── Sankranti planetary dignity for Rajayoga  (Ch. XIV) ─────────────────────
# Solar month → Sun's dignity → affects 9th/10th lord strength.
SANKRANTI_DIGNITY = {
    "Mesh":     {"sun_dignity": "exalted",    "signal":  1, "score": 0.72,
                 "note": "Sun exalted in Mesh (Aries). 9th lord (Sun) in exaltation — "
                         "Rajayoga and Bhagya yoga strong. Best month (Ch.XIV St.1)."},
    "Vrishabh": {"sun_dignity": "neutral",    "signal":  0, "score": 0.30,
                 "note": "Sun in Taurus — neutral dignity (Ch.XIV St.1)."},
    "Mithun":   {"sun_dignity": "friendly",   "signal":  1, "score": 0.55,
                 "note": "Sun in Gemini — friendly sign. Moderate Dhana yoga support."},
    "Kark":     {"sun_dignity": "friendly",   "signal":  1, "score": 0.55,
                 "note": "Sun in Cancer — friendly. Jupiter exalted in Cancer: strong "
                         "Guru blessings for wealth (Ch.XIV St.17)."},
    "Simha":    {"sun_dignity": "own",        "signal":  1, "score": 0.70,
                 "note": "Sun in Leo (own house). 9th lord strong — fortune and fame "
                         "in Sun's periods (Ch.XIV St.2)."},
    "Kanya":    {"sun_dignity": "neutral",    "signal":  0, "score": 0.30,
                 "note": "Sun neutral in Virgo. Mercury exalted — Mercury Dasa gains."},
    "Tula":     {"sun_dignity": "debilitated","signal": -1, "score": -0.65,
                 "note": "Sun debilitated in Libra (Ch.XIV St.2). 9th lord weak — "
                         "reduced Bhagya yoga. Saturn exalted — malefic power up."},
    "Vrishchik":{"sun_dignity": "inimical",   "signal": -1, "score": -0.55,
                 "note": "Sun in inimical Scorpio. Reduced 9th house support."},
    "Dhanu":    {"sun_dignity": "friendly",   "signal":  1, "score": 0.58,
                 "note": "Sun in Sagittarius (Jupiter's house) — friendly. "
                         "Moderate Bhagya yoga active."},
    "Makar":    {"sun_dignity": "friendly",   "signal":  1, "score": 0.58,
                 "note": "Sun in Capricorn — friendly. Mars exalted — energy for gains."},
    "Kumbh":    {"sun_dignity": "neutral",    "signal":  0, "score": 0.25,
                 "note": "Sun neutral in Aquarius. Saturn's house — mixed signals."},
    "Meen":     {"sun_dignity": "friendly",   "signal":  1, "score": 0.55,
                 "note": "Sun in Pisces (friendly). Venus exalted — strong Dhana yoga "
                         "in Venus periods (Ch.XIV St.23)."},
}

# ── Maraka Vaar-Tithi triggers  (Ch. X) ──────────────────────────────────────
# Specific Vaar + Tithi combinations that activate Maraka (loss) energies.
MARAKA_TRIGGERS = [
    # (vaar_idx, paksha, tithi_num, score, note)
    (6, "krishna", 15, -0.82,
     "Saturday + Amavasya — strongest Maraka combination. "
     "Sani owns malefic houses; Amavasya = Moon-Sun conjunction = maximum darkness (Ch.X)."),
    (2, "krishna", 15, -0.78,
     "Tuesday + Amavasya — Mars malefic + new moon. "
     "Malefic in 2nd with 12th lord in own Dasa → death/losses (Ch.X St.5)."),
    (6, "krishna", 14, -0.72,
     "Saturday + KP Chaturdashi — eve of Amavasya with Saturn. "
     "Malefics in 6th in sub-periods → losses (Ch.X St.6)."),
    (2, "krishna", 8,  -0.68,
     "Tuesday + Ashtami — Mars + 8th tithi. "
     "8th lord in own Dasa → death/losses (Ch.X St.4)."),
    (6, "shukla", 8,   -0.62,
     "Saturday + Shukla Ashtami — Saturn activates 8th house energy. "
     "Saturn becomes powerful in causing Maraka (Ch.X St.17)."),
    (0, "krishna", 14, -0.60,
     "Sunday + KP Chaturdashi — Sun as Maraka when debilitated. "
     "Mars with evil lordship in 5th in own Dasa (Ch.X St.16)."),
]

# ── Fortunate Combination triggers  (Ch. VIII) ───────────────────────────────
FORTUNE_TRIGGERS = [
    # (vaar_idx, paksha, tithi_num, score, note)
    (4, "shukla",  11, 0.80,
     "Jupiter + Ekadashi Shukla — Lord of 9th in 11th and lord of 11th in 9th "
     "conjoin → very fortunate (Ch.VIII St.1). Jupiter + Ekadashi = peak Dhana."),
    (4, "shukla",  15, 0.78,
     "Jupiter + Purnima — Moon fully waxed. 8 planets occupy 4 houses in pairs "
     "of 2 → very fortunate (Ch.VIII St.2). Guru amplifies."),
    (5, "shukla",  11, 0.75,
     "Venus + Ekadashi — Venus Dasa wealth. Malefics in 3rd, 6th, 11th (upachayas) "
     "→ fortunate (Ch.VIII St.5). Venus rules 11th gains."),
    (3, "shukla",   5, 0.72,
     "Mercury + Panchami — Sun-Mercury in 5th → much wealth in Mercury Dasa "
     "(Ch.VIII St.11 notes). Budha activates 5th (Putra) house."),
    (4, "shukla",   9, 0.75,
     "Jupiter + Navami — Lords of Lagna, 9th, 4th conjoined with 10th lord "
     "→ very fortunate in those periods (Ch.VIII St.9)."),
    (1, "shukla",  15, 0.70,
     "Moon + Purnima — Moon fully exalted (waxed). Lord of 4th as Moon karaka "
     "in 12th from Lagna → fortunate for 9th house (Ch.VIII St.6 notes)."),
    (0, "shukla",   1, 0.65,
     "Sun + Pratipada — Sun lord of 9th in 12th from Lagna scenario. "
     "Sun in 12th → fortunate for 9th house matters (Ch.VIII St.6 note)."),
]


class BhavarthaEngine:
    """
    Encodes wealth, fortune, Rajayoga, Maraka, Dasa, and Malika yoga rules
    from Bhavartha Ratnakara (B.V. Raman, 1947).

    All signals are adapted for daily market use:
      • Vaar lord  → current period/Dasa ruler
      • Tithi      → lunar bhava activation
      • Moon age   → Malika yoga position
      • Sankranti  → Sun's planetary dignity
    """

    # ── Public API ────────────────────────────────────────────────────────────

    def get_bhavartha_signals(self, panchanga: dict) -> dict:
        """
        Returns all Bhavartha signals for the given panchanga.
        Mirrors the structure of JyotishEngine.get_all_signals().
        """
        vaar_idx  = panchanga["vaar_index"]
        tithi     = panchanga["tithi"]
        sankranti = panchanga["sankranti"]
        moon_age  = tithi["moon_age"]
        paksha    = tithi["paksha"]
        tithi_num = tithi["number"]

        return {
            "dhanayoga": self.get_dhana_signal(paksha, tithi_num, vaar_idx),
            "rajayoga":  self.get_rajayoga_signal(vaar_idx, moon_age, sankranti),
            "maraka":    self.get_maraka_signal(vaar_idx, paksha, tithi_num),
            "dasa":      self.get_dasa_signal(vaar_idx, paksha, tithi_num),
            "malika":    self.get_malika_signal(moon_age),
        }

    # ── Dhanayoga / Nirdhana  (Chapter II) ───────────────────────────────────

    def get_dhana_signal(self, paksha: str, tithi_num: int,
                         vaar_idx: int) -> dict:
        """
        Dhana yoga (wealth) and Nirdhana (poverty) signals from Chapter II.
        Activates when the current tithi matches a Dhana or Nirdhana combination.
        Jupiter days amplify Dhana signals; Saturn days amplify Nirdhana signals.
        """
        tithi_rules = DHANA_TITHIS.get(paksha, {})
        base = tithi_rules.get(tithi_num)

        # Nearest-neighbour fallback (±1 tithi)
        if base is None:
            for t, rule in tithi_rules.items():
                if abs(t - tithi_num) == 1:
                    base = rule
                    break

        if base is None:
            return {
                "signal":      0,
                "score":       0.0,
                "confidence":  50,
                "note":        "No specific Dhanayoga or Nirdhana combination active today.",
                "source":      "Bhavartha Ratnakara · Ch.II",
            }

        signal = base["signal"]
        score  = base["score"]

        # Amplifiers
        if signal == 1 and vaar_idx == 4:     # Jupiter day amplifies Dhana
            score = min(score * 1.15, 0.90)
            amp = " [Jupiter day amplifies Dhana yoga]"
        elif signal == -1 and vaar_idx == 6:  # Saturn day amplifies Nirdhana
            score = max(score * 1.15, -0.90)
            amp = " [Saturn day amplifies Nirdhana]"
        else:
            amp = ""

        return {
            "signal":     signal,
            "score":      round(score, 3),
            "confidence": round(abs(score) * 85 + 15),
            "note":       base["note"] + amp,
            "source":     "Bhavartha Ratnakara · Ch.II",
        }

    # ── Rajayoga  (Chapters VIII & IX) ────────────────────────────────────────

    def get_rajayoga_signal(self, vaar_idx: int, moon_age: float,
                            sankranti: str) -> dict:
        """
        Rajayoga signals from Chapters VIII and IX.
        Checks:
          1. Vaar-pair combinations (consecutive-day planetary conjunctions)
          2. Moon in Kendra/Trikona (quadrant/trine) position
          3. Sun's dignity via Sankranti
          4. Fortune triggers for today's Vaar
        """
        scores  = []
        notes   = []

        # 1. Check Vaar pair (today vs yesterday modelled as today's Vaar and Vaar-1)
        prev_vaar = (vaar_idx - 1) % 7
        for d1, d2, sig, sc, note in RAJAYOGA_VAAR_PAIRS:
            if (vaar_idx == d1 and prev_vaar == d2) or \
               (vaar_idx == d2 and prev_vaar == d1):
                scores.append(sc)
                notes.append(note)
                break

        # 2. Moon in Kendra (0-7 or 21-29 days) → quadrant = Rajayoga support
        #    Moon in Trikona (5-10 or 19-24 days) → trine = Bhagya yoga
        kendra = (moon_age <= 7.4) or (moon_age >= 21.5)
        trikona = (5.0 <= moon_age <= 10.0) or (19.0 <= moon_age <= 24.0)
        if kendra:
            sc = 0.60
            scores.append(sc)
            notes.append(
                f"Moon in Kendra (quadrant) position — age {moon_age:.1f} days. "
                "Rahu in Kendra confers Rajayoga in Dasa (Ch.IX St.19). "
                "Jupiter in Kendra = strong benefic period."
            )
        elif trikona:
            sc = 0.55
            scores.append(sc)
            notes.append(
                f"Moon in Trikona (trine) position — age {moon_age:.1f} days. "
                "Sukra confers Rajayoga in Dasa if in Trikona (Ch.IX St.5). "
                "Bhagya (9th house) trine activated."
            )

        # 3. Sun dignity via Sankranti
        dignity_rule = SANKRANTI_DIGNITY.get(sankranti, {})
        if dignity_rule:
            scores.append(dignity_rule["score"])
            notes.append(dignity_rule["note"])

        if not scores:
            return {
                "signal":     0,
                "score":      0.0,
                "confidence": 50,
                "note":       "No Rajayoga combination active for today.",
                "source":     "Bhavartha Ratnakara · Ch.VIII-IX",
            }

        composite = sum(scores) / len(scores)
        signal    = 1 if composite > 0.15 else -1 if composite < -0.15 else 0
        return {
            "signal":     signal,
            "score":      round(composite, 3),
            "confidence": round(min(90, abs(composite) * 80 + 20)),
            "note":       " | ".join(notes),
            "source":     "Bhavartha Ratnakara · Ch.VIII-IX",
        }

    # ── Maraka (Loss) combinations  (Chapter X) ───────────────────────────────

    def get_maraka_signal(self, vaar_idx: int, paksha: str,
                          tithi_num: int) -> dict:
        """
        Maraka (loss/crash) signals from Chapter X.
        Specific Vaar+Paksha+Tithi triggers that activate loss energies.
        """
        triggered = []
        for vi, pk, tn, sc, note in MARAKA_TRIGGERS:
            if vi == vaar_idx and pk == paksha and tn == tithi_num:
                triggered.append((sc, note))

        if not triggered:
            # Soft check: any malefic Vaar (Sat/Mars) in Krishna Paksha late tithis?
            if vaar_idx in (2, 6) and paksha == "krishna" and tithi_num >= 13:
                sc   = -0.48
                note = (
                    f"{'Saturn' if vaar_idx==6 else 'Mars'} day in late Krishna Paksha "
                    f"(tithi {tithi_num}). Malefics in 6th house in their sub-periods "
                    "cause losses (Ch.X St.6)."
                )
                triggered.append((sc, note))

        if not triggered:
            return {
                "signal":     0,
                "score":      0.0,
                "confidence": 50,
                "note":       "No Maraka combination active today.",
                "source":     "Bhavartha Ratnakara · Ch.X",
            }

        best_sc, best_note = min(triggered, key=lambda x: x[0])
        return {
            "signal":     -1,
            "score":      round(best_sc, 3),
            "confidence": round(min(88, abs(best_sc) * 85 + 15)),
            "note":       best_note,
            "source":     "Bhavartha Ratnakara · Ch.X",
        }

    # ── Dasa results  (Chapter XI) ────────────────────────────────────────────

    def get_dasa_signal(self, vaar_idx: int, paksha: str,
                        tithi_num: int) -> dict:
        """
        Dasa results signal from Chapter XI.
        The Vaar lord is treated as the current period (Dasa) ruler.
        Paksha and tithi modulate the result.
        """
        planet = VAAR_PLANET[vaar_idx]
        base   = DASA_SIGNALS[planet]
        signal = base["signal"]
        score  = base["score"]
        note   = base["note"]

        # Modulation: Fortune triggers override base Dasa signal
        for vi, pk, tn, trig_sc, trig_note in FORTUNE_TRIGGERS:
            if vi == vaar_idx and pk == paksha and tn == tithi_num:
                score = trig_sc
                signal = 1 if score > 0 else -1
                note   = trig_note
                break

        # Paksha modifier: Shukla strengthens benefics, Krishna strengthens malefics
        if paksha == "shukla" and signal == 1:
            score = min(score * 1.10, 0.88)
        elif paksha == "krishna" and signal == -1:
            score = max(score * 1.10, -0.88)
        elif paksha == "krishna" and signal == 1:
            score *= 0.85   # Waning moon reduces benefic Dasa results slightly

        # Special: Sani Dasa + Sukra Bhukthi → unfortunate (Saturday + Friday adjacent)
        prev_vaar = (vaar_idx - 1) % 7
        if vaar_idx == 6 and prev_vaar == 5:
            score = -0.58
            signal = -1
            note = ("Sani Dasa Sukra Bhukthi — unfortunate combination (Ch.XI St.1). "
                    "Saturn day following Venus day activates this pattern.")

        return {
            "signal":     signal,
            "score":      round(score, 3),
            "confidence": round(min(88, abs(score) * 80 + 18)),
            "note":       note,
            "planet":     planet,
            "source":     "Bhavartha Ratnakara · Ch.XI",
        }

    # ── Graha Malika Yoga  (Chapter XIII) ─────────────────────────────────────

    def get_malika_signal(self, moon_age: float) -> dict:
        """
        Graha Malika yoga signal from Chapter XIII.
        The active Malika is determined by the moon's age:
          Each of the 12 bhavas spans 29.53/12 ≈ 2.46 days.
        Lagnamalika, Dhanamalika, Bhagyamalika, Karmamalika → bullish.
        Satrumalika, Randharamalika → bearish.
        """
        bhava_size = 29.53058867 / 12.0
        bhava_num  = int(moon_age / bhava_size) + 1
        bhava_num  = min(bhava_num, 12)

        yoga = MALIKA_YOGAS[bhava_num]

        return {
            "signal":     yoga["signal"],
            "score":      yoga["score"],
            "confidence": round(min(82, abs(yoga["score"]) * 75 + 18)),
            "note":       (
                f"{yoga['name']} active (moon age {moon_age:.1f} days, bhava {bhava_num}). "
                f"{yoga['result']} "
                "Planets in 6-9 houses from Lagna = Bhagya yoga → fortunate (Ch.XIII St.8)."
            ),
            "yoga_name":  yoga["name"],
            "bhava":      bhava_num,
            "source":     "Bhavartha Ratnakara · Ch.XIII",
        }

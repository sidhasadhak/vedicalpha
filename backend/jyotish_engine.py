"""
jyotish_engine.py
Encodes all rules from "Vyapar Ratna" by Pt. Hardev Sharma Trivedi & Pt. Gopeshkumar Ojha.

Key systems:
  1. Vaar (day of week) — intraday/weekly price direction rules
  2. Tithi (lunar date) — Shukla/Krishna Paksha commodity rules
  3. Paksha (fortnightly) — phase effects on gold, silver, grains
  4. Sankranti (solar ingress) — seasonal commodity trends
  5. Nakshatra-approximate — via moon age
"""

import math
from datetime import date, timedelta

# ── Constants ────────────────────────────────────────────────────────────────

SYNODIC_MONTH  = 29.53058867          # Days per lunar cycle
KNOWN_NEW_MOON = date(2024, 1, 11)    # Reference new moon date

WEEKDAYS = ["Ravivaar", "Somvaar", "Mangalvaar", "Budhvaar",
            "Guruvaar", "Shukravaar", "Shanivaar"]

SANKRANTIS = ["Makar", "Kumbh", "Meen", "Mesh", "Vrishabh", "Mithun",
              "Kark", "Simha", "Kanya", "Tula", "Vrishchik", "Dhanu"]

TITHI_NAMES = [
    "Pratipada", "Dwitiya", "Tritiya", "Chaturthi", "Panchami",
    "Shashthi", "Saptami", "Ashtami", "Navami", "Dashami",
    "Ekadashi", "Dwadashi", "Trayodashi", "Chaturdashi", "Purnima/Amavasya"
]

# ── Vaar rules (from book pages 65–67) ──────────────────────────────────────
# signal: +1 = tezi (bull), -1 = mandi (bear), 0 = neutral
# duration_note: how long this trend is expected to last

VAAR_RULES = {
    # Ravivaar — markets closed in India; carry-over effect
    0: {
        "name": "Ravivaar (Sun)",
        "effects": {"equity": 0, "commodity": 0, "agri": 0, "gold": 0, "silver": 0},
        "note": "Markets closed. Monday open will likely carry Saturday's closing trend.",
        "duration": "Carry-over to Monday open",
        "reliability": 0.55,
    },
    # Somvaar (Mon) — bull continues to Wed noon
    1: {
        "name": "Somvaar (Mon)",
        "effects": {"equity": 1, "commodity": 0, "agri": 0, "gold": 0, "silver": 1},
        "note": (
            "Somvaar tezi: If up Monday, trend continues to Wednesday noon. "
            "If down Monday, reverses Tuesday. Sudden Monday rally lasts till Tuesday noon."
        ),
        "duration": "Till Wednesday 12pm",
        "reliability": 0.62,
        "special_rules": [
            "If bull Monday AND bull Tuesday → Thursday reaction expected",
            "If bear Monday AND bear Tuesday → bull from Wednesday noon to Thursday",
            "Monday high/low re-tested on Wednesday"
        ]
    },
    # Mangalvaar (Tue) — agricultural & red goods tezi
    2: {
        "name": "Mangalvaar (Tue)",
        "effects": {"equity": 0, "commodity": 0, "agri": 1, "gold": 0, "silver": 0},
        "note": (
            "Monday mandi reverses to tezi Tuesday. "
            "Agricultural commodities favoured. If Monday bull → Tuesday reaction mandi."
        ),
        "duration": "Trend ends Wednesday 12pm",
        "reliability": 0.58,
    },
    # Budhvaar (Wed) — continuation till noon then watch
    3: {
        "name": "Budhvaar (Wed)",
        "effects": {"equity": 0, "commodity": 0, "agri": 0, "gold": 0, "silver": 0},
        "note": (
            "Continuation of Mon-Tue trend till noon. "
            "Post-noon: reversal sets in. Tuesday trend ends by Wednesday noon."
        ),
        "duration": "Morning: continuation. Afternoon: reversal watch",
        "reliability": 0.55,
    },
    # Guruvaar (Thu) — Gold, Silver, Equity tezi
    4: {
        "name": "Guruvaar (Thu)",
        "effects": {"equity": 1, "commodity": 1, "agri": 0, "gold": 1, "silver": 1},
        "note": (
            "Strong Guruvaar support for Gold, Silver, Equity. "
            "Mangalvaar trend ends by Thursday 1pm. If 5 Thursdays in month → Western market instability."
        ),
        "duration": "Full Thursday; bull till Friday noon sometimes",
        "reliability": 0.68,
        "special_rules": [
            "Tuesday trend ends by 1pm Thursday",
            "5-Thursday month: commodity fluctuation + rasa/chemicals tezi"
        ]
    },
    # Shukravaar (Fri) — SHORT-LIVED; reverses on Saturday
    5: {
        "name": "Shukravaar (Fri)",
        "effects": {"equity": 0, "commodity": 0, "agri": 0, "gold": 1, "silver": 1},
        "note": (
            "Friday trends are unstable and short-lived. "
            "Friday bull → Saturday mandi. Friday mandi → Saturday tezi. Exit positions by Friday noon."
        ),
        "duration": "Very short — reverses on Saturday",
        "reliability": 0.50,
        "special_rules": [
            "Friday tezi → Saturday mandi",
            "Friday mandi → Saturday tezi",
            "Thursday bull that extends to Friday ends by Saturday"
        ]
    },
    # Shanivaar (Sat) — STRONG; lasts full week
    6: {
        "name": "Shanivaar (Sat)",
        "effects": {"equity": 0, "commodity": 1, "agri": 1, "gold": 0, "silver": 0},
        "note": (
            "Saturday trend is the most durable — lasts a full week. "
            "Saturday high/low WILL be tested on Monday. Saturday tezi → Monday tezi above Saturday high."
        ),
        "duration": "Full week",
        "reliability": 0.72,
        "special_rules": [
            "Saturday high/low retested on Monday",
            "Saturday bull trend ends by following Tuesday",
            "Saturday mandi: collect agri (wheat, chana, mung) for future profit"
        ]
    },
}

# ── Tithi rules (pages 69–73) ────────────────────────────────────────────────

TITHI_RULES = {
    "shukla": {
        1:  {"gold": 0,  "silver": -1, "grains": 0,  "oils": 0,  "note": "Pratipada Mon/Tue: Rui-Chandi mandi. Pratipada Sun: Rui tezi 4-5%."},
        2:  {"gold": 0,  "silver": -1, "grains": 0,  "oils": 0,  "note": "Dwitiya: similar to Pratipada effects."},
        6:  {"gold": 0,  "silver": 1,  "grains": 1,  "oils": 0,  "note": "Shashthi vriddhi (growing): Rui and grains tezi."},
        7:  {"gold": 0,  "silver": 1,  "grains": 1,  "oils": 0,  "note": "Saptami: continuation of Shashthi tezi."},
        11: {"gold": 1,  "silver": 1,  "grains": 0,  "oils": 1,  "note": "Ekadashi: Gold-Silver-oils tezi. Auspicious tithi."},
        12: {"gold": 1,  "silver": 1,  "grains": 0,  "oils": 0,  "note": "Dwadashi: Metal tezi continues."},
        15: {"gold": 1,  "silver": 1,  "grains": 1,  "oils": 1,  "note": "Purnima: Broadly bullish. Silver especially tezi on Purnima."},
    },
    "krishna": {
        1:  {"gold": 0,  "silver": -1, "grains": 0,  "oils": 0,  "note": "KP Pratipada Wed: Rui-Chandi mandi. KP Pratipada Sun: Rui tezi."},
        6:  {"gold": 0,  "silver": 1,  "grains": 1,  "oils": 1,  "note": "KP Shashthi: Rui tezi if growing. Kshay (diminished) Shashthi: also tezi."},
        7:  {"gold": 0,  "silver": 1,  "grains": 1,  "oils": 0,  "note": "KP Saptami-Ekadashi: Rui (oilseeds/cotton) tezi."},
        10: {"gold": 0,  "silver": 0,  "grains": 1,  "oils": 1,  "note": "KP Dashami kshay: Ghee-Rui tezi. KP Dashami vriddhi: Rui-Ghee mandi."},
        14: {"gold": 0,  "silver": 0,  "grains": 1,  "oils": 0,  "note": "KP Chaturdashi Sun: Gehu-Chana-Jau tezi."},
        15: {"gold": -1, "silver": -1, "grains": 0,  "oils": -1, "note": "Amavasya: Gold-Silver-Ghee MANDI. Mon Amavasya with Kark Chandra: severe mandi."},
    }
}

# ── Sankranti rules (pages 115–117) ─────────────────────────────────────────

SANKRANTI_RULES = {
    "Makar": {
        "equity": 1, "gold": 1, "silver": 1, "grains": -1, "agri": 0,
        "note": "Makar Sankranti (Jan): Til, gur, cotton tezi. Equity positive. New financial optimism.",
        "commodities_tezi": ["gold", "silver", "cotton", "gur", "til"],
        "commodities_mandi": ["grains"]
    },
    "Kumbh": {
        "equity": 0, "gold": 0, "silver": 0, "grains": 0, "agri": 0,
        "note": "Kumbh Sankranti (Feb): Neutral to moderate. Pre-harvest calm.",
        "commodities_tezi": [], "commodities_mandi": []
    },
    "Meen": {
        "equity": 0, "gold": 1, "silver": 0, "grains": 1, "agri": 1,
        "note": "Meen Sankranti (Mar): Pre-harvest agri active. Gold tezi. Rabi crop prices watched.",
        "commodities_tezi": ["gold", "wheat", "barley"], "commodities_mandi": []
    },
    "Mesh": {
        "equity": 1, "gold": 1, "silver": 1, "grains": 1, "agri": 1,
        "note": "Mesh Sankranti (Apr): New financial year energy. Broadly bullish. Best month for equity.",
        "commodities_tezi": ["gold", "silver", "wheat", "cotton"],
        "commodities_mandi": []
    },
    "Vrishabh": {
        "equity": 0, "gold": 0, "silver": 0, "grains": 1, "agri": 1,
        "note": "Vrishabh Sankranti (May): Gehu-Chana-Jau-Kapas-Rai-Khad-Shakkar-Kirana tezi on Ravi/Mangal/Shani entry.",
        "commodities_tezi": ["wheat", "cotton", "sugar", "mustard"],
        "commodities_mandi": []
    },
    "Mithun": {
        "equity": 0, "gold": 0, "silver": 0, "grains": 0, "agri": 0,
        "note": "Mithun Sankranti (Jun): Monsoon watch. Agri variable. Moti (pearl), ratna tezi if Budhvar entry.",
        "commodities_tezi": ["pearls"], "commodities_mandi": []
    },
    "Kark": {
        "equity": -1, "gold": -1, "silver": -1, "grains": 1, "agri": 1,
        "note": "Kark Sankranti (Jul): Gold-Silver-Tamba MANDI. Shani entry: durbhiksha. Mon/Wed/Thu/Fri: agri tezi, metals mandi.",
        "commodities_tezi": ["grains", "agri"],
        "commodities_mandi": ["gold", "silver", "copper"]
    },
    "Simha": {
        "equity": 0, "gold": 1, "silver": 0, "grains": 1, "agri": 0,
        "note": "Simha Sankranti (Aug): Ravi/Mangal/Shani entry: Gehu-Jau-Chaval-Chana-Urad-Moong tezi then mandi. Gold first tezi.",
        "commodities_tezi": ["wheat", "rice", "gold"],
        "commodities_mandi": []
    },
    "Kanya": {
        "equity": 1, "gold": 1, "silver": 1, "grains": 1, "agri": 1,
        "note": "Kanya Sankranti (Sep): BEST OVERALL. Ravi entry: Gold-Silver-Gehu-Chana-Chaval-Haldi-Jeera-Til-Tel-Sarson tezi.",
        "commodities_tezi": ["gold", "silver", "wheat", "rice", "turmeric", "jeera", "mustard"],
        "commodities_mandi": ["urad", "moong", "masoor", "arhar", "bajra"]
    },
    "Tula": {
        "equity": 0, "gold": 1, "silver": 1, "grains": 0, "agri": 0,
        "note": "Tula Sankranti (Oct): Gold-Silver-Chana tezi on Ravi entry. Oilseeds mixed.",
        "commodities_tezi": ["gold", "silver", "chana"],
        "commodities_mandi": ["urad", "moong", "arhar", "bajra"]
    },
    "Vrishchik": {
        "equity": 0, "gold": 0, "silver": 0, "grains": 0, "agri": 1,
        "note": "Vrishchik Sankranti (Nov): Cotton-oilseeds up. Watch wheat. Kirana tezi.",
        "commodities_tezi": ["cotton", "oilseeds"],
        "commodities_mandi": []
    },
    "Dhanu": {
        "equity": 0, "gold": 1, "silver": 0, "grains": 0, "agri": 0,
        "note": "Dhanu Sankranti (Dec): Moderate — holiday season. Gold active. Silver neutral.",
        "commodities_tezi": ["gold"],
        "commodities_mandi": []
    },
}


class JyotishEngine:
    """
    Computes Panchanga and encodes all Vyapar Ratna prediction rules.
    """

    def get_moon_age(self, target: date) -> float:
        delta = (target - KNOWN_NEW_MOON).days
        age   = delta % SYNODIC_MONTH
        return age if age >= 0 else age + SYNODIC_MONTH

    def get_tithi(self, moon_age: float) -> dict:
        raw_tithi = int(moon_age / (SYNODIC_MONTH / 30)) + 1
        raw_tithi = min(raw_tithi, 30)
        paksha    = "shukla" if raw_tithi <= 15 else "krishna"
        tithi_num = raw_tithi if raw_tithi <= 15 else raw_tithi - 15
        return {
            "number":   tithi_num,
            "paksha":   paksha,
            "name":     TITHI_NAMES[tithi_num - 1],
            "raw":      raw_tithi,
            "moon_age": round(moon_age, 2),
        }

    def get_panchanga(self, target: date) -> dict:
        dow       = target.weekday()       # Mon=0, Sun=6
        iso_dow   = (dow + 1) % 7          # Convert to Sun=0 .. Sat=6
        moon_age  = self.get_moon_age(target)
        tithi     = self.get_tithi(moon_age)
        sankranti = SANKRANTIS[target.month - 1]
        vaar      = VAAR_RULES[iso_dow]

        # Count occurrences of each weekday this month (for special 5-weekday rules)
        first_day    = date(target.year, target.month, 1)
        weekday_count = {i: 0 for i in range(7)}
        d = first_day
        while d.month == target.month:
            weekday_count[(d.weekday() + 1) % 7] += 1
            d += timedelta(days=1)

        return {
            "date":           str(target),
            "vaar":           vaar["name"],
            "vaar_index":     iso_dow,
            "tithi":          tithi,
            "sankranti":      sankranti,
            "sankranti_rule": SANKRANTI_RULES[sankranti],
            "vaar_rule":      vaar,
            "weekday_counts": weekday_count,
            "five_thursday":  weekday_count[4] == 5,
            "five_monday":    weekday_count[1] == 5,
            "five_saturday":  weekday_count[6] == 5,
        }

    def get_tithi_signal(self, tithi: dict, category: str) -> dict:
        """
        Return signal (+1 / -1 / 0) from Tithi rules for given category.
        Category maps: equity → treat as neutral (Jyotish rules focus on commodities)
        """
        paksha = tithi["paksha"]
        num    = tithi["number"]
        rules  = TITHI_RULES.get(paksha, {})

        # Find closest matching tithi rule
        signal = 0
        note   = ""
        matched_tithi = None
        for t_num, rule in rules.items():
            if t_num == num:
                matched_tithi = rule
                break
            elif abs(t_num - num) <= 1 and matched_tithi is None:
                matched_tithi = rule   # nearest neighbour fallback

        if matched_tithi:
            note = matched_tithi.get("note", "")
            if category in ("gold",):
                signal = matched_tithi.get("gold", 0)
            elif category in ("silver",):
                signal = matched_tithi.get("silver", 0)
            elif category in ("agri", "commodity"):
                signal = matched_tithi.get("grains", 0)
            elif category == "equity":
                signal = 0   # Jyotish tithi rules mainly apply to commodities

        return {"signal": signal, "note": note, "tithi_num": num, "paksha": paksha}

    def get_vaar_signal(self, vaar_index: int, category: str) -> dict:
        rule = VAAR_RULES[vaar_index]
        cat_map = {
            "equity": "equity", "index": "equity",
            "commodity": "commodity", "agri": "agri",
            "gold": "gold", "silver": "silver",
        }
        key    = cat_map.get(category, "equity")
        signal = rule["effects"].get(key, 0)
        return {
            "signal":      signal,
            "vaar":        rule["name"],
            "note":        rule["note"],
            "duration":    rule["duration"],
            "reliability": rule["reliability"],
            "special":     rule.get("special_rules", []),
        }

    def get_sankranti_signal(self, sankranti: str, category: str) -> dict:
        rule = SANKRANTI_RULES.get(sankranti, {})
        cat_map = {
            "equity": "equity", "index": "equity",
            "commodity": "gold", "agri": "agri",
            "gold": "gold", "silver": "silver",
        }
        key    = cat_map.get(category, "equity")
        signal = rule.get(key, 0)
        return {
            "signal":   signal,
            "note":     rule.get("note", ""),
            "tezi":     rule.get("commodities_tezi", []),
            "mandi":    rule.get("commodities_mandi", []),
        }

    def get_all_signals(self, panchanga: dict, category: str) -> dict:
        vaar_sig      = self.get_vaar_signal(panchanga["vaar_index"], category)
        tithi_sig     = self.get_tithi_signal(panchanga["tithi"], category)
        sankranti_sig = self.get_sankranti_signal(panchanga["sankranti"], category)
        return {
            "vaar":      vaar_sig,
            "tithi":     tithi_sig,
            "sankranti": sankranti_sig,
        }

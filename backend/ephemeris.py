"""
ephemeris.py — Daily planetary positions via Swiss Ephemeris (Lahiri sidereal).

Used by brihat_engine.py and mundane_engine.py to replace the hardcoded
_default_*() approximations with date-accurate planet sign positions.

Key facts:
  • Ayanamsha: Lahiri (Chitrapaksha) — the standard used in Indian Jyotish software
  • Zodiac:    Sidereal (not tropical) — differs from Western astrology by ~23.5°
  • Ephemeris: Moshier (built into pyswisseph, no data files needed, covers 3000 BC–3000 AD)
  • Cache:     LRU 3650 entries (~10 years of daily calls) — backtest performance critical

Sign numbering: 1=Aries, 2=Taurus … 12=Pisces  (1-indexed, matching all existing engine tables)
"""

from __future__ import annotations
from datetime import date
from functools import lru_cache

try:
    import swisseph as swe
    _SWE_AVAILABLE = True
    swe.set_sid_mode(swe.SIDM_LAHIRI)
    _FLAGS = swe.FLG_SIDEREAL | swe.FLG_SPEED
except ImportError:
    _SWE_AVAILABLE = False

# Sign names — index 0=Aries … 11=Pisces (internal); returned dict uses 1-12
SIGN_NAMES = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]

# Planet IDs (only defined when swisseph is importable, safe to reference inside try/except)
_PLANETS = None  # lazily set below


def _planet_ids() -> dict:
    global _PLANETS
    if _PLANETS is None and _SWE_AVAILABLE:
        _PLANETS = {
            "sun":     swe.SUN,
            "moon":    swe.MOON,
            "mercury": swe.MERCURY,
            "venus":   swe.VENUS,
            "mars":    swe.MARS,
            "jupiter": swe.JUPITER,
            "saturn":  swe.SATURN,
            "rahu":    swe.MEAN_NODE,   # North Node (Rahu) — mean node is standard in Jyotish
        }
    return _PLANETS or {}


@lru_cache(maxsize=3650)
def _positions_cached(year: int, month: int, day: int) -> dict:
    """
    Internal cached call — args must be hashable primitives (no date objects).
    Returns {planet: {"sign": 1-12, "sign_name": str, "degree": float, "retrograde": bool}}
    """
    jd = swe.julday(year, month, day, 12.0)   # noon UTC — avoids DST ambiguity

    result = {}
    for name, pid in _planet_ids().items():
        pos, _ = swe.calc_ut(jd, pid, _FLAGS)
        longitude  = pos[0] % 360.0
        speed      = pos[3]                    # deg/day; negative = retrograde
        sign_0idx  = int(longitude / 30)       # 0=Aries … 11=Pisces
        degree     = longitude % 30.0

        result[name] = {
            "sign":      sign_0idx + 1,        # 1-indexed to match engine tables
            "sign_name": SIGN_NAMES[sign_0idx],
            "degree":    round(degree, 2),
            "retrograde": speed < 0,
            "longitude": round(longitude, 2),
        }

    # Ketu (South Node) = Rahu + 180°
    if "rahu" in result:
        rahu_long  = result["rahu"]["longitude"]
        ketu_long  = (rahu_long + 180.0) % 360.0
        ketu_0idx  = int(ketu_long / 30)
        result["ketu"] = {
            "sign":      ketu_0idx + 1,
            "sign_name": SIGN_NAMES[ketu_0idx],
            "degree":    round(ketu_long % 30.0, 2),
            "retrograde": True,                # Rahu/Ketu are always retrograde
            "longitude": round(ketu_long, 2),
        }

    return result


# ── Fallback planet positions (when pyswisseph is unavailable) ────────────────
# Approximate for April 2026; used only if import fails.
_FALLBACK: dict = {
    "sun":     {"sign": 1,  "sign_name": "Aries",       "degree": 0.0,  "retrograde": False},
    "moon":    {"sign": 1,  "sign_name": "Aries",       "degree": 0.0,  "retrograde": False},
    "mercury": {"sign": 12, "sign_name": "Pisces",      "degree": 15.0, "retrograde": False},
    "venus":   {"sign": 4,  "sign_name": "Cancer",      "degree": 5.0,  "retrograde": False},
    "mars":    {"sign": 4,  "sign_name": "Cancer",      "degree": 10.0, "retrograde": False},
    "jupiter": {"sign": 3,  "sign_name": "Gemini",      "degree": 22.0, "retrograde": False},
    "saturn":  {"sign": 12, "sign_name": "Pisces",      "degree": 13.0, "retrograde": False},
    "rahu":    {"sign": 11, "sign_name": "Aquarius",    "degree": 20.0, "retrograde": True},
    "ketu":    {"sign": 5,  "sign_name": "Leo",         "degree": 20.0, "retrograde": True},
}


def get_positions(d: date) -> dict:
    """
    Public API. Returns daily sidereal (Lahiri) planet positions for date `d`.

    Return structure:
      {
        "sun":     {"sign": 1-12, "sign_name": str, "degree": float, "retrograde": bool, "longitude": float},
        "moon":    {...},
        "mars":    {...},
        "mercury": {...},
        "jupiter": {...},
        "venus":   {...},
        "saturn":  {...},
        "rahu":    {...},
        "ketu":    {...},
      }

    Falls back to approximate April 2026 positions if pyswisseph is not installed.
    """
    if not _SWE_AVAILABLE:
        return _FALLBACK
    try:
        return _positions_cached(d.year, d.month, d.day)
    except Exception:
        return _FALLBACK


def sign_name(sign_1idx: int) -> str:
    """Convert 1-indexed sign number to name."""
    return SIGN_NAMES[(sign_1idx - 1) % 12]


def is_available() -> bool:
    """Returns True if pyswisseph is installed and working."""
    return _SWE_AVAILABLE

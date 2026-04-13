# VedicAlpha — Complete Developer Guide

> Read this file first in every session. It contains everything you need to
> be fully oriented — architecture, conventions, weights, endpoints, state.

---

## What Is This Project?

**VedicAlpha** is an Indian stock and commodity prediction app that combines
**six ancient Vedic astrology source books** with **ten Indian-market technical
indicators** to produce BUY / SELL / HOLD signals with confidence scores.

Target users: Indian traders who use both fundamental/technical analysis and
astrological timing (a mainstream practice in India, especially for commodities
and gold). The app surfaces signals from six classical texts in a modern iOS UI
with plain-English explanations.

---

## Repository Layout

```
vyapar_ratna/
│
├── CLAUDE.md                          ← this file (start here every session)
│
├── backend/                           ← Python FastAPI server
│   ├── main.py                        ← all API endpoints, startup, CORS
│   ├── prediction_engine.py           ← 6-engine orchestrator + technical
│   │
│   ├── jyotish_engine.py              ← Engine 1: Vyapar Ratna
│   ├── prasna_engine.py               ← Engine 2: Prasna Marga
│   ├── bhavartha_engine.py            ← Engine 3: Bhavartha Ratnakara
│   ├── kalamrita_engine.py            ← Engine 4: Uttara Kalamrita
│   ├── brihat_engine.py               ← Engine 5: Brihat Samhita
│   ├── mundane_engine.py              ← Engine 6: Mediniya Jyotish
│   │
│   ├── market_data.py                 ← price cascade: nsepython→yfinance→mock
│   ├── history_store.py               ← SQLite for prediction + alert history
│   ├── rule_weights.json              ← 6-engine horizon weights (edit to retune)
│   ├── requirements.txt               ← pip deps (fastapi, uvicorn, yfinance…)
│   ├── SETUP.md                       ← step-by-step new-developer setup
│   ├── vyapar_ratna.db                ← SQLite file (gitignored)
│   └── books/                         ← source PDFs (gitignored — too large)
│       ├── Vyapar-Ratna.pdf
│       ├── Prasna Marga 1.pdf
│       ├── Prasna Marga 2.pdf
│       ├── Bhavartha-Ratnakara.pdf
│       ├── Kalidasa_-_Uttara_Kalamrita.pdf
│       ├── 2015.102832.Varahamihiras-Brihat-Samhitavoli-ii.pdf
│       └── 2015.310309.Mediniya-Jyotish.pdf
│
├── ios_app/
│   └── Vyapar Ratna/
│       └── Vyapar Ratna/
│           ├── VyaparRatnaApp.swift   ← ALL SwiftUI views (single file)
│           └── NetworkManager.swift   ← Codable models + async API calls
│
└── .env.example                       ← credential template (safe to commit)
```

---

## Running the Backend

```bash
cd backend
source venv/bin/activate          # create venv first: python3 -m venv venv
uvicorn main:app --reload --port 8000
```

- Use `python3` NOT `python` (macOS default python is 2.x)
- Server: http://localhost:8000
- API docs: http://localhost:8000/docs (auto-generated Swagger)

**Quick smoke test:**
```bash
curl http://localhost:8000/panchanga
curl -X POST http://localhost:8000/predict \
  -H 'Content-Type: application/json' \
  -d '{"ticker":"GOLD","exchange":"MCX","category":"gold","horizon":"1D","mode":"both"}'
```

---

## All API Endpoints

| Method | Path | Purpose | Payload / Params |
|--------|------|---------|-----------------|
| GET | `/` | Health check | — |
| GET | `/panchanga` | Today's lunar data | `?target_date=YYYY-MM-DD` |
| POST | `/predict` | Full 6-engine prediction | `PredictionRequest` |
| POST | `/prashna` | Horary-only reading | `PrashnaRequest` |
| GET | `/quote/{ticker}` | Live/mock price | `?exchange=NSE\|MCX` |
| GET | `/search` | Instrument search | `?q=RELI` |
| GET | `/dashboard` | Multi-ticker 1D sweep | — |
| GET | `/history` | Prediction log | `?ticker=GOLD&limit=20` |
| POST | `/backtest` | Accuracy test vs history | `?ticker=GOLD&horizon=1W&days=90` |
| POST | `/alert` | Register signal alert | `AlertRequest` |
| GET | `/check_alerts` | Evaluate pending alerts | — |

**PredictionRequest:**
```json
{
  "ticker":   "GOLD",
  "exchange": "MCX",
  "category": "gold",
  "horizon":  "1D",
  "mode":     "both",
  "target_date": null
}
```
horizon: `1D | 1W | 2W | 1M | 3M`
mode: `both | jyotish | technical`

---

## The Six Vedic Engines

### Engine 1 — Vyapar Ratna (`jyotish_engine.py`)
**Source book:** Vyapar Ratna (Marathi commodity almanac, Pt. Hardev Sharma Trivedi)
**Rules encoded:**
- `VAAR_RULES` — 7 weekday signals with duration notes (e.g. Mon bull lasts till Wed noon)
- `TITHI_COMMODITY_SIGNALS` — 15 tithis × multiple commodity categories
- `SANKRANTI_SIGNALS` — 12 solar ingress months → tezi/mandi commodity lists
- Special: five-Thursday month (Western market stress), five-Saturday month (all tezi)
**Best horizons:** 1D, 1W
**Key method:** `get_all_signals(panchanga, category) → dict`

### Engine 2 — Prasna Marga (`prasna_engine.py`)
**Source book:** Prasna Marga Parts I & II (B.V. Raman, Kerala tradition)
**Rules encoded:**
- `GOCHARA_WEALTH` — 9 planets × 12 houses from Moon with wealth scores (81 combinations)
- `NAKSHATRA_WEALTH` — 13 nakshatras with wealth affinity scores
- `KRITA/TRETA/DWAPARA/KALI_SIGNS` — yuga sign theory for financial effort
- `VAAR_FINANCIAL_BIAS` — day-of-week Artha Prashna bias
- `PAKSHA_BIAS` — waxing/waning moon polarity
**KEY PRINCIPLE:** Prasna answers the querent's specific intent at the moment of query,
NOT general market direction. Can legitimately differ from other engines.
**Best horizons:** 1D, 1W — weight is 0% for 1M and 3M
**Key method:** `get_artha_prashna_reading(panchanga, ticker, category) → dict`

### Engine 3 — Bhavartha Ratnakara (`bhavartha_engine.py`)
**Source book:** Bhavartha Ratnakara (Sanskrit yoga-combination text)
**Rules encoded:**
- Dhanayoga — wealth-producing planet combinations
- Nirdhana yoga — poverty/loss combinations
- Rajayoga — prosperity periods
- Maraka combinations — loss indicators (weighted 1.10× — extra caution)
- Dasa timing — Vimshottari period effects
- Graha Malika Yoga — planetary chain formations
**Best horizons:** 1W, 2W, 1M
**Key method:** `get_bhavartha_signals(panchanga) → dict`

### Engine 4 — Uttara Kalamrita (`kalamrita_engine.py`)
**Source book:** Uttara Kalamrita by Kalidasa (classical Sanskrit)
**Rules encoded:**
- `PLANET_KARAKATVA` — 9 planets' significations from Ch V (commodity alignments)
- `HOUSE_KARAKATVA` — 2nd (wealth), 10th (commerce), 11th (gains), 12th (loss)
- `DHANA_YOGA_VAAR` — Ch IV Dhana Yoga by weekday
- `VIPARITA_RAAJAYOGA_TITHIS` — contrarian recovery signal from Ch IV
- `ANTARDASA_PAIRS` — 81 Mahadasa×Antardasa combinations from Ch VI
- `PRASHNA_PLANET_SIGNAL` — 9-planet horary signal from Ch VII
**Best horizons:** 1W–3M
**Note:** The Kalamrita Prashna (Ch VII) is flagged `is_prashna: True` and is NOT
included in total_score — display-only.
**Key method:** `get_kalamrita_signals(kpanch) → dict`

### Engine 5 — Brihat Samhita (`brihat_engine.py`)
**Source book:** Brihat Samhita Vol II (Varahamihira, ~587 CE)
**Rules encoded:**
- `JUPITER_TRANSIT` — 12 signs with per-category scores (Ch 8, Brhaspati Charitra)
  - Exalted Cancer: +0.55 overall; Debilitated Capricorn: −0.35 overall
- `SATURN_TRANSIT` — 12 signs (Ch 32, Shani Charitra)
  - Exalted Libra: +0.45; Debilitated Aries: −0.45
- `RAHU_TRANSIT` — 12 signs, eclipse-driven disruptions (Ch 5)
  - Gold/silver get safe-haven boost when Rahu causes market disruption
- `MARS_SIGN_COMMODITY` — fire sign surges for metals/energy
- `VENUS_SIGN_COMMODITY` — own/exalted sign luxury boom
**Default planet positions:** Hardcoded for ~Apr 2026 in `_default_*()` methods.
Update these or pass `jupiter_sign`, `saturn_sign`, `rahu_sign` in kpanch.
**Best horizons:** 1M, 3M (slow transits)
**Key method:** `get_brihat_signals(panchanga, category) → dict`

### Engine 6 — Mediniya Jyotish (`mundane_engine.py`)
**Source book:** Mediniya Jyotish (Marathi/Sanskrit, 209 pages, scanned)
**Rules encoded:**
- `SAMVATSARA` — all 60 Vedic year names with annual market temperament scores
  - e.g. Nandana (+0.30 bull), Khara (−0.25 bear), Vyaya (−0.25 bear/inflation)
  - Current year (2025–26): Sarvajit (+0.15 bull)
- `RITU_EFFECTS` — 6 Indian seasons with per-category effects
  - Sharad (Sep–Oct): gold +0.40, silver +0.35, equity +0.35 ← Diwali season
- `MONTH_MARKET_BIAS` — 12 Gregorian months with NSE/BSE seasonal patterns
  - Nov: +0.30 (Diwali rally); Feb: +0.20 (Budget); Mar: −0.10 (FY-end selling)
- `SUN_SIGN_MARKET` — Surya Sankranti effects on sector rotation
- `SIGN_QUALITY_MAP` — Chara/Sthira/Dwiswabhava → trend vs range-bound market type
- `HORA_COMMODITY` — intraday gold vs silver alternation (planetary hora lord)
**Best horizons:** 1M, 3M
**Key method:** `get_mundane_signals(panchanga, category) → dict`

---

## Weight System

Weights live in `rule_weights.json` — **edit there, never in code**.

```
Total weight per prediction = Σ(6 Vedic engines) + Technical = 1.0

Technical weight (fixed by category):
  gold:      20%   agri:      23%
  silver:    25%   equity:    43%
  commodity: 50%   index:     50%

Vedic total = (1.0 − tech_weight), split by horizon:

Horizon  VR    PM    BR    UK    BS    MJ
──────────────────────────────────────────
  1D     35%   30%   15%   10%    5%    5%
  1W     25%   15%   25%   20%   10%    5%
  2W     22%   10%   26%   22%   12%    8%
  1M     12%    0%   20%   25%   28%   15%
  3M     10%    0%   20%   25%   30%   15%

VR=Vyapar Ratna, PM=Prasna Marga, BR=Bhavartha Ratnakara,
UK=Uttara Kalamrita, BS=Brihat Samhita, MJ=Mediniya Jyotish

Prasna Marga (PM) is 0% for 1M and 3M — horary is not relevant at long horizons.
Slow-planet engines (BS, MJ) dominate at 1M and 3M.
```

**Signal alignment cap:** If fewer than 3 Vedic engines agree on the same direction,
confidence is capped at 55% and `mixed_signals: true` is set in the response.

---

## Technical Indicators (10+)

All indicators use 60 bars of OHLC data (live from yfinance, or 61-bar mock).

| # | Indicator | Method |
|---|-----------|--------|
| 1 | RSI-14 | `_calc_rsi(closes, 14)` |
| 2 | MACD price-normalised | `_calc_macd(closes)` + `tanh(val / price*0.01)` |
| 3 | Supertrend (7×3 ATR) | `_calc_supertrend(c, h, l)` |
| 4 | Bollinger Bands (%B + width) | `_calc_bollinger(closes)` |
| 5 | ADX-14 | `_calc_adx(h, l, c)` |
| 6 | India VIX proxy | simulated ~15–25 |
| 7 | Put-Call Ratio | equity/index only; simulated 0.6–1.2 |
| 8 | Gold:Silver Ratio | gold/silver category only |
| 9 | Candlestick Patterns | `_detect_candle_pattern(o, h, l, c)` — 9 types |
| 10 | EMA Positioning (9/20/50/200) | `_calc_ema_positioning(closes)` |
| 11 | Pivot Points (P, R1, R2, S1, S2) | `_calc_pivot_points(h, l, c, price)` |

**MACD normalisation (critical for gold):** Gold at ₹72,000 produces large MACD
values that saturate `tanh`. Normalise: `score = tanh(macd / (price * 0.01))`.

---

## Market Data Sources

Priority cascade per call:
1. **nsepython** — live NSE quotes (works without API key; for NSE/BSE only)
2. **yfinance** — 60-day OHLC history (MCX commodities mapped to futures tickers)
3. **Mock data** — 61-bar simulated OHLC from `MOCK_PRICES` dict

yfinance commodity ticker map:
```python
{"GOLD":"GC=F", "SILVER":"SI=F", "CRUDEOIL":"CL=F",
 "COPPER":"HG=F", "NATURALGAS":"NG=F", "ALUMINIUM":"ALI=F",
 "NIFTY50":"^NSEI", "BANKNIFTY":"^NSEBANK", "SENSEX":"^BSESN"}
```

---

## Supported Instruments (48 total)

**20 NSE Equities:** RELIANCE, TCS, INFY, HDFCBANK, ICICIBANK, SBIN, WIPRO,
BAJFINANCE, TATASTEEL, ADANIENT, BHARTIARTL, LT, AXISBANK, MARUTI, SUNPHARMA,
HCLTECH, KOTAKBANK, TITAN, ITC, NESTLEIND

**5 Indices:** SENSEX, NIFTY50, BANKNIFTY, NIFTYMIDCAP, NIFTYIT

**11 MCX Commodities:** GOLD, GOLDM, SILVER, SILVERM, CRUDEOIL, NATURALGAS,
COPPER, ZINC, ALUMINIUM, NICKEL, LEAD

**12 NCDEX Agri:** WHEAT, COTTON, SOYBEAN, SUGAR, MUSTARD, TURMERIC, JEERA,
CHANA, CASTOR, GUARSEED, DHANIYA, BARLEY

---

## iOS App Architecture

**All views in `VyaparRatnaApp.swift`** (single-file design — intentional).
**Models + networking in `NetworkManager.swift`**.

### 3-Tab Structure
```
TabView
├── Dashboard (tab 0)      ← home; shows all default tickers
│   ├── DashboardView
│   │   ├── toolbar: "Predict" button → sheet: PredictView
│   │   └── List of DashboardRowView (ticker + BUY/SELL/HOLD chip)
│   └── TickerDetailView (push on row tap)
│       ├── VerdictCard               ← ALWAYS FIRST: BUY/SELL/HOLD ring + summary
│       ├── DetailPriceCard           ← live price + OHLC
│       ├── PrashnaBannerButton       ← horary CTA → PrashnaDetailSheet
│       └── DisclosureGroup "Detailed Analysis" (collapsed by default)
│           ├── DetailSignalCard      ← horizon picker + EngineWeightsBar
│           ├── DetailPanchaCard      ← today's panchanga
│           ├── DetailChartCard       ← confidence history chart
│           └── DetailFactorsCard     ← all 22+ factors
├── History (tab 1)        ← past predictions list
└── Settings (tab 2)       ← base URL, theme
```

### Key Views
- **VerdictCard:** Circular confidence arc + BUY/STRONG BUY/SELL/STRONG SELL/HOLD
  + 1–2 sentence auto-generated plain English summary
- **EngineWeightsBar:** 7-segment (up to) stacked color bar
  VR=gold, PM=purple, BR=green, UK=dark-purple, BS=orange, MJ=teal, TA=blue
  Prasna segment hidden when weight=0 (1M, 3M horizons)
- **PrashnaDetailSheet:** "What is Prashna?" explainer + reconciliation note

### iOS Models (`NetworkManager.swift`)
```swift
struct PredictionRequest   // ticker, exchange, category, horizon, mode
struct PredictionResponse  // ticker, exchange, horizon, date, panchanga, price, prediction
struct PredictionResult    // signal, signalLabel, confidence, score, factors, engineWeights
struct EngineWeights       // vyaparRatna, prasna, bhavartha, kalamrita, brihat, mundane, technical
struct Factor              // name, signal, score, confidence, description, source
struct PrashnaResponse     // ticker, exchange, category, queryTime, panchanga, prashna
struct PrashnaReading      // action, signal, confidence, queryPlanet, reconciliation, …
struct DashboardResponse   // date, panchanga, tickers: [DashboardTickerItem]
```

---

## Key Architectural Decisions

1. **Prashna is display-only** — flagged `is_prashna: True` in factors, never added
   to `total_score`. It answers the querent's specific intent, not market direction.
   Has its own endpoint `POST /prashna`.

2. **Vaar normalisation** — panchanga returns "Ravivaar (Sun)"; all engines need
   index 0–6. Use prefix-match dict:
   ```python
   _vaar_map = {"sun":0,"ravi":0,"rav":0,"mon":1,"som":1,...}
   vaar_idx = next((v for k,v in _vaar_map.items() if vaar_str.startswith(k)), 0)
   ```

3. **kpanch dict** — normalised panchanga dict built ONCE at top of `predict()`,
   shared by all 6 Vedic engines. Keys: `vaar_idx, tithi_num, paksha, moon_age,
   sankranti, category, horizon`.

4. **Signal alignment cap** — if fewer than 3 engines agree on direction, confidence
   is capped at 55% and `mixed_signals: true` is set.

5. **MACD price-normalisation** — `tanh(macd_val / (price * 0.01))` prevents
   saturation on Gold (₹70k+) and other high-priced instruments.

6. **Brihat defaults** — `brihat_engine._default_jupiter()` returns 4 (Cancer,
   exalted) for May 2025–Jun 2026. `_default_saturn()` returns 1 (Aries, debilitated)
   from Mar 2025. These are date-computed, not truly hardcoded.

7. **Mundane Samvatsara** — Shaka year = Gregorian − 78 (before Apr 14) or −77
   (after). `(shaka - 1) % 60` gives the 0–59 index. "Sarvajit" in 2025–26.

---

## Common Issues & Fixes

| Issue | Fix |
|-------|-----|
| `python` not found | Use `python3` on macOS |
| MACD saturates for gold | `score = tanh(macd / price * 0.01)` |
| Vaar index mismatch | Use prefix-match dict (not list index) |
| yfinance returns empty for MCX | Auto-fallback to mock — no action needed |
| nsepython timeout | Auto-fallback to yfinance → mock |
| 101% rounding in engine_weights | Display artefact only; actual weights sum to 1.0 |
| Brihat wrong planet sign | Update `_default_*()` methods or pass sign in kpanch |
| iOS UIKit warning | Pre-existing SourceKit issue; not caused by code changes |

---

## Environment Variables

No secrets are currently required — nsepython and yfinance work without API keys.
When adding paid data sources, store credentials in `.env` (gitignored) and load
with `python-dotenv`. See `.env.example` for template.

```python
# In market_data.py, at top:
from dotenv import load_dotenv; load_dotenv()
import os
KITE_API_KEY = os.getenv("KITE_API_KEY", "")
```

---

## Git Conventions

```
main     ← stable, deployable
dev      ← active development (default working branch)
feature/ ← short-lived feature branches off dev
```

Commit message format:
```
<type>(<scope>): <short description>

type: feat | fix | refactor | docs | test | chore
scope: backend | ios | engine | weights | infra
```

---

## Coding Conventions

### Python (backend)
- Python 3.10+ required (uses `X | Y` union syntax)
- Engine classes: stateless, no instance variables beyond `__init__`
- Score range: always `−1.0 … +1.0` before weighting
- All scores clipped: `max(-1.0, min(1.0, score))`
- Signal strings: always one of `"bull" | "bear" | "neutral"`
- Factor dicts always have: `name, signal, score, confidence, description, source`
- No f-strings longer than 120 chars; break across lines

### Swift (iOS)
- iOS 17+ target, SwiftUI only (no UIKit)
- All networking via `async/await` in `NetworkManager`
- `@MainActor` on all `ObservableObject` ViewModels
- All JSON snake_case keys handled via `CodingKeys`
- Error states shown inline (no alert dialogs for network errors)
- Single-file view design: add new views to `VyaparRatnaApp.swift`

---

## Current State (as of Apr 2026)

### Built and Working
- [x] All 6 Vedic engines with rules from source books
- [x] 6-engine weight system loaded from `rule_weights.json`
- [x] Signal alignment confidence cap (< 3 engines agree → max 55%)
- [x] 10+ technical indicators (RSI, MACD, Supertrend, BB, ADX, VIX, PCR, ratio, candle, EMA, pivot)
- [x] Market data: nsepython → yfinance → mock cascade
- [x] FastAPI backend with all 11 endpoints
- [x] iOS app: Dashboard, History, Settings tabs
- [x] VerdictCard with plain-English auto-summary
- [x] EngineWeightsBar (7-segment, Prasna hidden at 1M+)
- [x] PrashnaDetailSheet with reconciliation note
- [x] SQLite prediction history
- [x] `rule_weights.json` for no-code weight tuning

### Planned / Not Yet Built
- [ ] Real ephemeris (ephem library) for precise planet positions in Brihat engine
- [ ] Live PCR data from NSE (currently simulated)
- [ ] Live India VIX from NSE (currently simulated)
- [ ] Zerodha Kite Connect integration for real-time tick data
- [ ] Push notifications for alert triggers
- [ ] Backtesting script (`run_backtest.py`) with accuracy report
- [ ] Widget extension for iOS home screen
- [ ] Railway/Render cloud deployment config
- [ ] Apple App Store submission

---

## iPhone → Claude Code Bridge

The iOS Settings tab allows the user to change the backend URL at runtime
(stored in `UserDefaults` under key `vyapar_base_url`). This enables:

- **Simulator:** `http://localhost:8000` (default)
- **LAN:** `http://192.168.x.x:8000` (iPhone + Mac on same Wi-Fi)
- **Cloud:** `https://your-app.railway.app` (deployed backend)

The URL is editable in the Settings tab (`SettingsView`). No code change needed
to switch between environments.

---

## Model Routing (claude_bridge + model_router)

VedicAlpha uses **intelligent model routing** to minimise Claude API cost.
Every Dev Chat message is classified and sent to the right model automatically.

### Which model handles what

| Task | Model | Why |
|------|-------|-----|
| Jyotish rule interpretation | Claude Sonnet/Opus | Needs domain judgment |
| Prediction logic debugging | Claude Sonnet | Complex reasoning |
| Backtesting analysis | Claude Sonnet | Insight + pattern matching |
| Architecture decisions | Claude Opus | Deep reasoning |
| Writing new `.py` / `.swift` files | Qwen3-Coder (Ollama) | Free, fast, capable |
| Adding endpoints / boilerplate | Qwen3-Coder (Ollama) | Pure code generation |
| Refactoring / renaming | Qwen3-Coder (Ollama) | Mechanical transformation |
| Simple bug fixes | Qwen3-Coder (Ollama) | Syntax / type errors |

### Routing keywords

**Coding signals** (→ Qwen3): `write a`, `create a file`, `add a function`,
`update the file`, `add endpoint`, `implement`, `refactor`, `add import`,
`fix the syntax`, file path mentions (`.py`, `.swift`), code blocks (` ``` `).

**Reasoning signals** (→ Claude): `why`, `explain`, `analyse`, `interpret`,
`jyotish`, `astrolog`, `backtest result`, `should i`, `debug`,
`something is wrong`, `what's the best approach`.

**Opus escalation**: `deep analysis`, `compare all six books`,
`interpret all rules from`, `architectural decision`, `fundamental problem`.

### Forcing a model

In the iOS Dev Chat, use the `[Auto] [Claude] [Local]` segmented control.

Via API: add `"force_model": "claude"` or `"force_model": "ollama"` to the POST body.

### Adding new routing rules

Edit `CODING_SIGNALS` / `REASONING_SIGNALS` / `OPUS_SIGNALS` lists in
`backend/model_router.py`. No restart needed — changes take effect on next call.

### Model stats

`GET /model_stats` returns today's call counts, token usage, and estimated cost.
The iOS Dev Chat shows call counts in the top status bar.

### Local model

`qwen3-coder:30b` (18 GB) running via Ollama at `http://localhost:11434`.
If Ollama goes down: `ollama serve &` then `ollama pull qwen3-coder:30b`.

### Claude API key

Set `ANTHROPIC_API_KEY` in `backend/.env`. Without it, Claude calls return
a friendly error message and suggest setting the key — the app does not crash.

---

## Constraints / Non-Negotiables

1. No API keys committed to git — use `.env` (gitignored)
2. PDF books stay in `backend/books/` but are gitignored (file size)
3. `rule_weights.json` intentionally committed — it's configuration not secret
4. SQLite DB (`*.db`) is gitignored
5. `venv/` is gitignored — recreate with `pip install -r requirements.txt`
6. Prashna signal MUST NOT be added to `total_score` — display-only
7. All engine scores must stay in −1.0…+1.0 range before weighting
8. iOS app must compile for iOS 17+ with no third-party Swift packages

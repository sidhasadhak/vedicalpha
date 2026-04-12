# Vyapar Ratna AI — Setup Guide
## Step-by-step: Python backend → iPhone app

---

## STEP 1 — Set up the Python backend

```bash
# 1. Create a virtual environment
cd vyapar_ratna/backend
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the server
python main.py
# → Server starts at http://0.0.0.0:8000
# → Open http://localhost:8000 in browser — you should see the API info JSON
```

**Test it works:**
```bash
curl http://localhost:8000/panchanga
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"ticker":"RELIANCE","exchange":"NSE","category":"equity","horizon":"1D","mode":"both"}'
```

---

## STEP 2 — Connect iPhone to the backend (same Wi-Fi)

1. On your Mac, find your local IP:
   ```bash
   ipconfig getifaddr en0
   # e.g. 192.168.1.105
   ```

2. Open `NetworkManager.swift` and change line 13:
   ```swift
   let BASE_URL = "http://192.168.1.105:8000"   // ← your Mac's IP
   ```

3. Your iPhone and Mac must be on **the same Wi-Fi network**.

---

## STEP 3 — Build the iOS app in Xcode

1. Open **Xcode** → File → New → Project → iOS → App
2. Name it `VyaparRatna`, Interface: SwiftUI, Language: Swift
3. Delete the default `ContentView.swift`
4. Drag these 2 files into the Xcode project:
   - `ios_app/VyaparRatnaApp.swift`
   - `ios_app/NetworkManager.swift`
5. In `VyaparRatnaApp.swift` → right-click `@main` → "Make as app entry" if needed
6. Open `Info.plist` → add this key (allows HTTP to your local server):
   ```xml
   <key>NSAppTransportSecurity</key>
   <dict>
     <key>NSAllowsLocalNetworking</key>
     <true/>
     <key>NSAllowsArbitraryLoads</key>
     <true/>
   </dict>
   ```
7. Select your iPhone as the build target (connect via USB or use wireless)
8. Press ▶ Run

---

## STEP 4 (Optional) — Deploy to cloud so app works anywhere

### Option A: Railway (free tier, easiest)
```bash
# Install Railway CLI
npm install -g @railway/cli
railway login
cd vyapar_ratna/backend
railway init
railway up

# Add a Procfile:
echo "web: uvicorn main:app --host 0.0.0.0 --port \$PORT" > Procfile
railway up
# → Get your URL: https://your-app.up.railway.app
```

### Option B: Render (free tier)
1. Push your `backend/` folder to GitHub
2. Go to render.com → New Web Service
3. Connect your repo, set:
   - Build: `pip install -r requirements.txt`
   - Start: `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. Copy the URL → paste into `NetworkManager.swift`

---

## STEP 5 — Enable live market data (optional but recommended)

### NSE data (equities):
```bash
pip install nsepython
```
Works out of the box — no API key needed for basic quotes.

### Zerodha Kite Connect (professional real-time data):
1. Sign up at https://kite.trade (₹2000/month)
2. Get your API key + secret
3. Uncomment in `requirements.txt`: `kiteconnect==4.2.0`
4. In `market_data.py`, add your credentials:
   ```python
   KITE_API_KEY    = "your_api_key"
   KITE_API_SECRET = "your_api_secret"
   ```

### Angel One SmartAPI (free for Angel One customers):
```bash
pip install smartapi-python
```

---

## Project structure

```
vyapar_ratna/
├── backend/
│   ├── main.py              ← FastAPI app (all routes)
│   ├── jyotish_engine.py    ← All Vyapar Ratna rules encoded
│   ├── prediction_engine.py ← Combines Jyotish + Technical signals
│   ├── market_data.py       ← NSE / MCX / yfinance data fetcher
│   ├── history_store.py     ← SQLite prediction history
│   └── requirements.txt
│
└── ios_app/
    ├── VyaparRatnaApp.swift  ← All SwiftUI screens
    └── NetworkManager.swift  ← API client (Swift async/await)
```

---

## API endpoints reference

| Method | Endpoint           | Description                       |
|--------|--------------------|-----------------------------------|
| GET    | /                  | Health check + version            |
| POST   | /predict           | Full prediction with factors      |
| GET    | /panchanga         | Today's Tithi, Vaar, Sankranti    |
| GET    | /quote/{ticker}    | Live price quote                  |
| GET    | /search?q=...      | Search instruments                |
| GET    | /history           | Past predictions                  |
| POST   | /backtest          | Back-test Jyotish rules           |
| POST   | /alert             | Set a price/signal alert          |
| GET    | /check_alerts      | Evaluate pending alerts           |

---

## Disclaimer

This app is for educational and research purposes only.
It is NOT SEBI-registered financial advice.
Always consult a qualified financial advisor before trading.

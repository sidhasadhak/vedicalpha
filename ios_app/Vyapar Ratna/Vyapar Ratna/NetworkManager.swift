// NetworkManager.swift
// VedicAlpha — iOS App
// Handles all API calls to the FastAPI backend

import Foundation
import Combine

// ── Backend URL — editable at runtime from the Settings screen ───────────────
// Default: http://localhost:8000  (simulator / same-machine testing)
// LAN:     http://192.168.x.x:8000  (iPhone on same Wi-Fi as Mac)
// Cloud:   https://your-app.railway.app

private let kBaseURLKey  = "vedicalpha_base_url"
let kBaseURLDefault      = "http://localhost:8000"

var BASE_URL: String {
    get { UserDefaults.standard.string(forKey: kBaseURLKey) ?? kBaseURLDefault }
    set { UserDefaults.standard.set(newValue, forKey: kBaseURLKey) }
}

// ── Data Models ───────────────────────────────────────────────────────────────

struct PredictionRequest: Codable {
    let ticker: String
    let exchange: String
    let category: String
    let horizon: String
    let mode: String
}

struct FactorSummary: Codable {
    let bull: Int
    let bear: Int
    let neutral: Int
}

struct PriceQuote: Codable {
    let ticker: String
    let price: Double
    let change: Double
    let changePct: Double
    let open: Double
    let high: Double
    let low: Double
    let close: Double
    let source: String
    let timestamp: String
    enum CodingKeys: String, CodingKey {
        case ticker, price, change, open, high, low, close, source, timestamp
        case changePct = "change_pct"
    }
}

struct Factor: Codable, Identifiable {
    let id = UUID()
    let name: String
    let signal: String
    let score: Double
    let confidence: Int
    let description: String
    let source: String
    enum CodingKeys: String, CodingKey {
        case name, signal, score, confidence, description, source
    }
}

struct ChartPoint: Codable, Identifiable {
    let id = UUID()
    let label: String
    let value: Double
    enum CodingKeys: String, CodingKey { case label, value }
}

struct EngineWeights: Codable {
    let vyaparRatna: Int
    let prasna: Int
    let bhavartha: Int
    let kalamrita: Int
    let brihat: Int
    let mundane: Int
    let technical: Int
    let category: String
    let horizon: String
    enum CodingKeys: String, CodingKey {
        case prasna, bhavartha, kalamrita, brihat, mundane, technical, category, horizon
        case vyaparRatna = "vyapar_ratna"
    }
}

struct PredictionResult: Codable {
    let signal: String
    let signalLabel: String
    let confidence: Int
    let score: Double
    let expectedMove: String
    let factors: [Factor]
    let chartData: [ChartPoint]
    let factorSummary: FactorSummary?
    let engineWeights: EngineWeights?
    let disclaimer: String
    enum CodingKeys: String, CodingKey {
        case signal, confidence, score, disclaimer, factors
        case signalLabel   = "signal_label"
        case expectedMove  = "expected_move"
        case chartData     = "chart_data"
        case factorSummary = "factor_summary"
        case engineWeights = "engine_weights"
    }
}

// ── Prashna (Horary) models ───────────────────────────────────────────────────

struct PrashnaRequest: Codable {
    let ticker: String
    let exchange: String
    let category: String
}

struct PanchaSnapshot: Codable {
    let vaarIdx: Int
    let tithiNum: Int
    let moonAge: Double
    let paksha: String
    enum CodingKeys: String, CodingKey {
        case paksha
        case vaarIdx  = "vaar_idx"
        case tithiNum = "tithi_num"
        case moonAge  = "moon_age"
    }
}

struct PrashnaReading: Codable {
    let ticker: String
    let category: String
    let action: String       // "BUY" | "SELL" | "HOLD"
    let signal: String
    let confidence: Double
    let queryPlanet: String
    let queryAbout: String
    let note: String
    let tithiEffect: String
    let reconciliation: String
    let prashnaMeaning: String
    let source: String
    let reliability: String
    let panchaSnapshot: PanchaSnapshot
    enum CodingKeys: String, CodingKey {
        case ticker, category, action, signal, confidence, note, source, reliability
        case queryPlanet    = "query_planet"
        case queryAbout     = "query_about"
        case tithiEffect    = "tithi_effect"
        case reconciliation = "reconciliation"
        case prashnaMeaning = "prashna_meaning"
        case panchaSnapshot = "panchanga_snapshot"
    }
}

struct PrashnaResponse: Codable {
    let ticker: String
    let exchange: String
    let category: String
    let queryTime: String
    let panchanga: Panchanga
    let prashna: PrashnaReading
    enum CodingKeys: String, CodingKey {
        case ticker, exchange, category, panchanga, prashna
        case queryTime = "query_time"
    }
}

struct Tithi: Codable {
    let number: Int
    let paksha: String
    let name: String
}

struct Panchanga: Codable {
    let date: String
    let vaar: String
    let tithi: Tithi
    let sankranti: String
}

struct PredictionResponse: Codable {
    let ticker: String
    let exchange: String
    let horizon: String
    let date: String
    let panchanga: Panchanga
    let price: PriceQuote?
    let prediction: PredictionResult
}

struct DashboardTickerItem: Codable, Identifiable {
    let id = UUID()
    let ticker: String
    let exchange: String
    let category: String
    let price: PriceQuote
    let prediction: PredictionResult
    enum CodingKeys: String, CodingKey {
        case ticker, exchange, category, price, prediction
    }
}

struct DashboardResponse: Codable {
    let date: String
    let panchanga: Panchanga
    let tickers: [DashboardTickerItem]
}

struct QuoteResponse: Codable {
    let ticker: String
    let price: Double
    let change: Double
    let changePct: Double
    let high: Double
    let low: Double
    let source: String
    enum CodingKeys: String, CodingKey {
        case ticker, price, change, high, low, source
        case changePct = "change_pct"
    }
}

struct SearchResult: Codable, Identifiable {
    let id = UUID()
    let ticker: String
    let name: String
    let exchange: String
    let category: String
    enum CodingKeys: String, CodingKey {
        case ticker, name, exchange, category
    }
}

struct HistoryItem: Codable, Identifiable {
    let id = UUID()
    let ticker: String
    let horizon: String
    let signal: String
    let confidence: Int
    let date: String
    enum CodingKeys: String, CodingKey {
        case ticker, horizon, signal, confidence, date
    }
}


    // MARK: — Health check

    func isServerReachable() async -> Bool {
        guard let url = URL(string: "\(BASE_URL)/") else { return false }
        do {
            let (_, response) = try await URLSession.shared.data(from: url)
            return (response as? HTTPURLResponse)?.statusCode == 200
        } catch {
            return false
        }
    }
}


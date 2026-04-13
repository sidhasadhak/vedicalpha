// VedicAlphaApp.swift
// VedicAlpha — Vedic astrology meets modern market analysis
// iOS 17+, SwiftUI. Add NetworkManager.swift to the same target.

import SwiftUI
import Combine
import UIKit
import Charts

// ── App Entry ─────────────────────────────────────────────────────────────────

@main
struct VedicAlphaApp: App {
    var body: some Scene {
        WindowGroup { ContentView() }
    }
}

// ── Theme ─────────────────────────────────────────────────────────────────────

extension Color {
    // Signal semantics — green means BUY, red means SELL, nothing else
    static let bull    = Color(red: 0.05, green: 0.65, blue: 0.40)  // #0DA666 — emerald
    static let bear    = Color(red: 0.84, green: 0.18, blue: 0.18)  // #D72E2E — crimson
    static let neutral = Color(red: 0.50, green: 0.52, blue: 0.54)  // #808588 — slate

    // Brand identity — VedicAlpha saffron (never used for signals)
    static let accent  = Color(red: 0.73, green: 0.36, blue: 0.04)  // #BA5C0A — deep saffron
    static let gold    = Color(red: 0.70, green: 0.50, blue: 0.06)  // #B3800F — warm gold (astrological accents)

    // Surface
    static let cardBG  = Color(.systemBackground)
    static let surface = Color(.secondarySystemBackground)
}

func signalColor(_ s: String) -> Color {
    s == "bull" ? .bull : s == "bear" ? .bear : .neutral
}

func expectedMoveColor(_ move: String) -> Color {
    if move.hasPrefix("+") { return .bull }
    if move.hasPrefix("-") { return .bear }
    return .primary
}

// ── Main Tab View ─────────────────────────────────────────────────────────────

struct ContentView: View {
    @State private var tab = 0
    @StateObject private var vm = AppViewModel()

    var body: some View {
        TabView(selection: $tab) {
            DashboardView(vm: vm)
                .tabItem { Label("Dashboard", systemImage: "square.grid.2x2") }
                .tag(0)
            HistoryView(vm: vm)
                .tabItem { Label("History", systemImage: "clock.arrow.circlepath") }
                .tag(1)
            SettingsView(vm: vm)
                .tabItem { Label("Settings", systemImage: "gear") }
                .tag(2)
        }
        .tint(.accent)
        .task { await vm.checkServer() }
    }
}

// ── ViewModel ─────────────────────────────────────────────────────────────────

@MainActor
class AppViewModel: ObservableObject {
    @Published var serverOnline    = false
    @Published var isLoading       = false
    @Published var errorMsg: String?
    @Published var response: PredictionResponse?
    @Published var panchanga: Panchanga?
    @Published var history: [HistoryItem] = []
    @Published var searchResults: [SearchResult] = []
    @Published var dashboard: DashboardResponse?
    @Published var dashboardLoading = false

    let net = NetworkManager.shared

    func checkServer() async {
        serverOnline = await net.isServerReachable()
    }

    func loadDashboard() async {
        dashboardLoading = true
        do { dashboard = try await net.getDashboard() }
        catch { errorMsg = "Dashboard failed: \(error.localizedDescription)" }
        dashboardLoading = false
    }

    func runPrediction(ticker: String, exchange: String, category: String,
                       horizon: String, mode: String) async {
        isLoading = true; errorMsg = nil
        do {
            response = try await net.predict(
                ticker: ticker, exchange: exchange,
                category: category, horizon: horizon, mode: mode
            )
            await loadHistory()
        } catch {
            errorMsg = "Prediction failed: \(error.localizedDescription)"
        }
        isLoading = false
    }

    func loadPanchanga() async {
        do { panchanga = try await net.getPanchanga() }
        catch { errorMsg = error.localizedDescription }
    }

    func loadHistory() async {
        do { history = try await net.getHistory() }
        catch {}
    }

    func search(_ q: String) async {
        guard q.count >= 1 else { searchResults = []; return }
        do { searchResults = try await net.search(query: q) }
        catch {}
    }
}

// ── Predict Screen ────────────────────────────────────────────────────────────

struct PredictView: View {
    @ObservedObject var vm: AppViewModel
    @State private var query         = ""
    @State private var selected: SearchResult?
    @State private var horizon       = "1D"
    @State private var mode          = "both"
    @FocusState private var focused: Bool

    // Saved after each run so Prashna + horizon re-fetch know the context
    @State private var savedCategory = "equity"
    @State private var savedMode     = "both"

    // Prashna state (mirrors TickerDetailView)
    @State private var showPrashna    = false
    @State private var prashnaResp: PrashnaResponse?
    @State private var prashnaLoading = false
    @State private var detailLoading  = false

    private let horizons      = ["1D","1W","2W","1M","3M"]
    private let horizonLabels = ["1D":"1 Day","1W":"1 Week","2W":"2 Weeks","1M":"1 Month","3M":"3 Months"]
    private let modes         = [("both","Jyotish + Tech"),("jyotish","Jyotish"),("technical","Technical")]

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 0) {

                    // Server status banner
                    if !vm.serverOnline {
                        HStack(spacing: 6) {
                            Image(systemName: "wifi.slash")
                            Text("Backend offline — start the Python server")
                            Spacer()
                        }
                        .font(.caption)
                        .foregroundStyle(.white)
                        .padding(10)
                        .background(Color.bear)
                    }

                    VStack(alignment: .leading, spacing: 16) {

                        // ── Search field ──────────────────────────────────────
                        VStack(alignment: .leading, spacing: 6) {
                            Text("Stock or Commodity").sectionLabel()
                            HStack {
                                Image(systemName: "magnifyingglass").foregroundStyle(.secondary)
                                TextField("e.g. RELIANCE, GOLD, NIFTY50…", text: $query)
                                    .focused($focused)
                                    .autocorrectionDisabled()
                                    .textInputAutocapitalization(.characters)
                                    .onChange(of: query) { _, q in
                                        selected = nil
                                        Task { await vm.search(q) }
                                    }
                                if !query.isEmpty {
                                    Button { query = ""; selected = nil; vm.searchResults = []; vm.response = nil } label: {
                                        Image(systemName: "xmark.circle.fill").foregroundStyle(.secondary)
                                    }
                                }
                            }
                            .padding(11)
                            .background(Color.surface)
                            .clipShape(RoundedRectangle(cornerRadius: 12))

                            // Suggestions dropdown
                            if !vm.searchResults.isEmpty && selected == nil {
                                VStack(spacing: 0) {
                                    ForEach(vm.searchResults) { r in
                                        Button {
                                            selected = r
                                            query    = r.ticker
                                            vm.searchResults = []
                                            focused  = false
                                        } label: {
                                            HStack {
                                                VStack(alignment: .leading, spacing: 2) {
                                                    Text(r.ticker).font(.system(.body, weight: .medium))
                                                    Text(r.name).font(.caption).foregroundStyle(.secondary)
                                                }
                                                Spacer()
                                                Text(r.exchange)
                                                    .font(.caption2)
                                                    .padding(.horizontal, 8).padding(.vertical, 3)
                                                    .background(Color.surface)
                                                    .clipShape(Capsule())
                                            }
                                            .padding(.horizontal, 12).padding(.vertical, 10)
                                            .contentShape(Rectangle())
                                        }
                                        .buttonStyle(.plain)
                                        Divider().padding(.leading, 12)
                                    }
                                }
                                .background(Color.cardBG)
                                .clipShape(RoundedRectangle(cornerRadius: 12))
                                .overlay(RoundedRectangle(cornerRadius: 12).stroke(Color(.separator), lineWidth: 0.5))
                            }
                        }

                        // ── Horizon picker ────────────────────────────────────
                        VStack(alignment: .leading, spacing: 8) {
                            Text("Prediction Horizon").sectionLabel()
                            ScrollView(.horizontal, showsIndicators: false) {
                                HStack(spacing: 8) {
                                    ForEach(horizons, id: \.self) { h in
                                        Button { horizon = h } label: {
                                            Text(horizonLabel(h))
                                                .font(.subheadline)
                                                .padding(.horizontal, 16).padding(.vertical, 8)
                                                .background(horizon == h ? Color.accent : Color.surface)
                                                .foregroundStyle(horizon == h ? .white : Color.primary)
                                                .clipShape(Capsule())
                                        }
                                    }
                                }
                            }
                        }

                        // ── Mode picker ───────────────────────────────────────
                        VStack(alignment: .leading, spacing: 8) {
                            Text("Analysis Mode").sectionLabel()
                            HStack(spacing: 8) {
                                ForEach(modes, id: \.0) { m in
                                    Button { mode = m.0 } label: {
                                        Text(m.1).font(.caption)
                                            .padding(.horizontal, 12).padding(.vertical, 7)
                                            .background(mode == m.0 ? Color.accent : Color.surface)
                                            .foregroundStyle(mode == m.0 ? .white : Color.primary)
                                            .clipShape(Capsule())
                                    }
                                }
                            }
                        }

                        // ── Predict button ────────────────────────────────────
                        Button {
                            let ticker = selected?.ticker ?? query.uppercased()
                            let ex     = selected?.exchange ?? "NSE"
                            let cat    = selected?.category ?? "equity"
                            savedCategory = cat
                            savedMode     = mode
                            prashnaResp   = nil   // clear stale Prashna on new run
                            Task { await vm.runPrediction(
                                ticker: ticker, exchange: ex,
                                category: cat, horizon: horizon, mode: mode
                            )}
                        } label: {
                            HStack {
                                if vm.isLoading { ProgressView().tint(.white) }
                                Text(vm.isLoading ? "Calculating…" : "Generate Prediction →")
                                    .font(.system(.body, weight: .medium))
                            }
                            .frame(maxWidth: .infinity)
                            .padding(14)
                            .background(Color.accent)
                            .foregroundStyle(.white)
                            .clipShape(RoundedRectangle(cornerRadius: 14))
                        }
                        .disabled(vm.isLoading || query.isEmpty)

                        // Error
                        if let err = vm.errorMsg {
                            Text(err).font(.caption).foregroundStyle(.red)
                        }

                        // ── Full detail cards (same as TickerDetailView) ──────
                        if let r = vm.response {
                            let prediction = r.prediction

                            // 1 — Verdict
                            VerdictCard(
                                prediction: prediction,
                                prashna: prashnaResp?.prashna,
                                ticker: r.ticker,
                                horizon: r.horizon
                            )

                            // 2 — Price
                            if let price = r.price {
                                DetailPriceCard(
                                    exchange: r.exchange,
                                    signal: prediction.signal,
                                    price: price
                                )
                            }

                            // 3 — Prashna banner
                            PrashnaBannerButton(
                                isLoading: prashnaLoading,
                                response: prashnaResp
                            ) {
                                showPrashna = true
                            } onAsk: {
                                Task { await fetchPrashna(r) }
                            }

                            // 4 — Detailed Analysis (collapsible)
                            DisclosureGroup {
                                VStack(spacing: 14) {
                                    // Signal metrics + engine weights + horizon re-picker
                                    DetailSignalCard(
                                        prediction: prediction,
                                        horizon: horizon,
                                        horizons: horizons,
                                        horizonLabels: horizonLabels,
                                        isLoading: detailLoading
                                    ) { h in
                                        horizon = h
                                        Task { await fetchDetail(r) }
                                    }

                                    // Projected chart
                                    if !prediction.chartData.isEmpty {
                                        DetailChartCard(
                                            chartData: prediction.chartData,
                                            signal: prediction.signal,
                                            horizon: r.horizon
                                        )
                                    }

                                    // All factors
                                    DetailFactorsCard(prediction: prediction)
                                }
                            } label: {
                                HStack {
                                    Image(systemName: "chart.bar.doc.horizontal")
                                        .foregroundStyle(.secondary)
                                    Text("Detailed Analysis")
                                        .font(.system(.subheadline, weight: .semibold))
                                    Spacer()
                                    if let fs = prediction.factorSummary {
                                        Text("\(fs.bull)↑ \(fs.bear)↓")
                                            .font(.caption).foregroundStyle(.secondary)
                                    }
                                }
                                .padding(.vertical, 2)
                            }
                            .padding(14)
                            .background(Color.cardBG)
                            .clipShape(RoundedRectangle(cornerRadius: 16))
                            .overlay(RoundedRectangle(cornerRadius: 16).stroke(Color(.separator), lineWidth: 0.5))

                            Text(prediction.disclaimer)
                                .font(.caption2).foregroundStyle(.tertiary)
                                .multilineTextAlignment(.center)
                                .padding(.horizontal)
                        }

                        Text("VedicAlpha is for educational purposes only. Not SEBI-registered investment advice.")
                            .font(.caption2).foregroundStyle(.tertiary)
                            .multilineTextAlignment(.center)
                            .frame(maxWidth: .infinity)
                    }
                    .padding(16)
                }
            }
            .navigationTitle("VedicAlpha")
            .navigationBarTitleDisplayMode(.large)
            .sheet(isPresented: $showPrashna) {
                if let resp = prashnaResp { PrashnaDetailSheet(response: resp) }
            }
        }
    }

    // Re-fetch when user picks a different horizon inside the detail card
    private func fetchDetail(_ r: PredictionResponse) async {
        detailLoading = true
        if let resp = try? await vm.net.predict(
            ticker: r.ticker, exchange: r.exchange,
            category: savedCategory, horizon: horizon, mode: savedMode
        ) {
            vm.response = resp
        }
        detailLoading = false
    }

    private func fetchPrashna(_ r: PredictionResponse) async {
        prashnaLoading = true
        if let resp = try? await vm.net.getPrashna(
            ticker: r.ticker, exchange: r.exchange, category: savedCategory
        ) {
            prashnaResp = resp
            showPrashna = true
        }
        prashnaLoading = false
    }

    private func horizonLabel(_ h: String) -> String {
        ["1D":"Next Day","1W":"1 Week","2W":"2 Weeks","1M":"1 Month","3M":"3 Months"][h] ?? h
    }
}

struct MetricCell: View {
    let value: String; let label: String; let color: Color
    var body: some View {
        VStack(spacing: 3) {
            Text(value).font(.system(.title3, weight: .medium)).foregroundStyle(color)
            Text(label).font(.caption2).foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity)
    }
}

// ── Panchanga Screen ──────────────────────────────────────────────────────────

struct PanchaView: View {
    @ObservedObject var vm: AppViewModel

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 16) {
                    if let p = vm.panchanga {
                        PanchaGrid(p: p)
                    } else {
                        ProgressView("Loading Panchanga…")
                            .frame(maxWidth: .infinity, minHeight: 200)
                    }
                }
                .padding(16)
            }
            .navigationTitle("Panchanga")
            .task { await vm.loadPanchanga() }
        }
    }
}

struct PanchaGrid: View {
    let p: Panchanga
    var body: some View {
        LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 12) {
            PanchaCard(icon: "moon.stars",    label: "Vaar",      value: p.vaar)
            PanchaCard(icon: "circle.dotted", label: "Paksha",    value: p.tithi.paksha.capitalized)
            PanchaCard(icon: "calendar",      label: "Tithi",     value: p.tithi.name)
            PanchaCard(icon: "sun.horizon",   label: "Sankranti", value: p.sankranti)
        }
    }
}

struct PanchaCard: View {
    let icon: String; let label: String; let value: String
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Image(systemName: icon).foregroundStyle(.blue)
            Text(value).font(.system(.title3, weight: .medium))
            Text(label).font(.caption).foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(14)
        .background(Color.surface)
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }
}

// ── History Screen ────────────────────────────────────────────────────────────

struct HistoryView: View {
    @ObservedObject var vm: AppViewModel

    var body: some View {
        NavigationStack {
            List(vm.history) { item in
                HStack {
                    VStack(alignment: .leading, spacing: 3) {
                        Text(item.ticker).font(.system(.body, weight: .medium))
                        Text("\(item.horizon) · \(item.date)").font(.caption).foregroundStyle(.secondary)
                    }
                    Spacer()
                    VStack(alignment: .trailing, spacing: 3) {
                        Text(item.signal == "bull" ? "Tezi ↑" : item.signal == "bear" ? "Mandi ↓" : "Sama →")
                            .font(.subheadline).foregroundStyle(signalColor(item.signal))
                        Text("\(item.confidence)%").font(.caption2).foregroundStyle(.secondary)
                    }
                }
            }
            .navigationTitle("History")
            .overlay(Group {
                if vm.history.isEmpty {
                    ContentUnavailableView("No predictions yet",
                        systemImage: "chart.line.uptrend.xyaxis",
                        description: Text("Generate your first prediction from the Predict tab."))
                }
            })
            .task { await vm.loadHistory() }
        }
    }
}

// ── Settings Screen ───────────────────────────────────────────────────────────

struct SettingsView: View {
    @ObservedObject var vm: AppViewModel
    @State private var draftURL  = BASE_URL
    @State private var savedURL  = BASE_URL   // tracks what's persisted so the button stays correct

    var isDirty: Bool { draftURL.trimmingCharacters(in: .whitespacesAndNewlines) != savedURL }

    var body: some View {
        NavigationStack {
            Form {
                Section("Backend connection") {
                    HStack {
                        Text("Status")
                        Spacer()
                        Circle().fill(vm.serverOnline ? Color.bull : Color.bear).frame(width: 8)
                        Text(vm.serverOnline ? "Online" : "Offline")
                            .foregroundStyle(vm.serverOnline ? Color.bull : Color.bear)
                    }

                    VStack(alignment: .leading, spacing: 6) {
                        Text("Server URL")
                            .font(.caption).foregroundStyle(.secondary)
                        TextField("http://192.168.x.x:8000", text: $draftURL)
                            .font(.caption)
                            .autocorrectionDisabled()
                            .textInputAutocapitalization(.never)
                            .keyboardType(.URL)
                    }

                    HStack(spacing: 12) {
                        Button("Save & reconnect") {
                            let trimmed = draftURL.trimmingCharacters(in: .whitespacesAndNewlines)
                            BASE_URL = trimmed
                            savedURL = trimmed
                            Task { await vm.checkServer() }
                        }
                        .disabled(!isDirty)

                        if !isDirty && savedURL != kBaseURLDefault {
                            Text("Saved").font(.caption).foregroundStyle(.blue)
                        }
                    }

                    Button("Re-check connection") {
                        Task { await vm.checkServer() }
                    }
                }
                Section("About") {
                    LabeledContent("App", value: "VedicAlpha")
                    LabeledContent("Version", value: "1.0.0")
                    LabeledContent("Engines", value: "6 Vedic + Technical")
                    LabeledContent("Data sources", value: "NSE · MCX · NCDEX")
                }
                Section {
                    Text("VedicAlpha combines signals from six classical Vedic texts (Vyapar Ratna, Prasna Marga, Bhavartha Ratnakara, Uttara Kalamrita, Brihat Samhita, Mediniya Jyotish) with modern technical indicators. For educational purposes only. Not SEBI-registered investment advice.")
                        .font(.caption).foregroundStyle(.secondary)
                }
            }
            .navigationTitle("Settings")
            .onAppear { draftURL = BASE_URL }
        }
    }
}

// ── Helpers ───────────────────────────────────────────────────────────────────

extension Text {
    func sectionLabel() -> some View {
        self.font(.caption).foregroundStyle(.secondary).textCase(.uppercase)
    }
}

// ── Dashboard ─────────────────────────────────────────────────────────────────

/// Groups tickers by category for the sectioned list.
private struct DashboardGroup {
    let title: String
    let items: [DashboardTickerItem]

    static func groups(from items: [DashboardTickerItem]) -> [DashboardGroup] {
        let order: [String]  = ["index","gold","silver","commodity","equity","agri"]
        let titles: [String: String] = [
            "index":"Indices", "gold":"Gold", "silver":"Silver",
            "commodity":"Commodities", "equity":"Top Equities", "agri":"Agri"
        ]
        var buckets: [String: [DashboardTickerItem]] = [:]
        for item in items { buckets[item.category, default: []].append(item) }
        return order.compactMap { cat in
            guard let rows = buckets[cat], !rows.isEmpty else { return nil }
            return DashboardGroup(title: titles[cat] ?? cat.capitalized, items: rows)
        }
    }
}

struct DashboardView: View {
    @ObservedObject var vm: AppViewModel
    @State private var showPredict = false

    var body: some View {
        NavigationStack {
            Group {
                if vm.dashboardLoading && vm.dashboard == nil {
                    ProgressView("Loading market predictions…")
                        .frame(maxWidth: .infinity, minHeight: 300)
                } else if let db = vm.dashboard {
                    List {
                        Section {
                            PanchaBanner(panchanga: db.panchanga)
                        }
                        ForEach(DashboardGroup.groups(from: db.tickers), id: \.title) { group in
                            Section(group.title) {
                                ForEach(group.items) { item in
                                    NavigationLink {
                                        TickerDetailView(vm: vm, item: item)
                                    } label: {
                                        DashboardRowView(item: item)
                                    }
                                }
                            }
                        }
                    }
                    .listStyle(.insetGrouped)
                } else {
                    ContentUnavailableView(
                        "No Data",
                        systemImage: "wifi.slash",
                        description: Text("Start the Python backend, then refresh.")
                    )
                }
            }
            .navigationTitle("Dashboard")
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button {
                        showPredict = true
                    } label: {
                        Label("Predict", systemImage: "chart.line.uptrend.xyaxis")
                            .font(.system(.subheadline, weight: .semibold))
                    }
                }
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button {
                        Task { await vm.loadDashboard() }
                    } label: {
                        if vm.dashboardLoading {
                            ProgressView().controlSize(.small)
                        } else {
                            Image(systemName: "arrow.clockwise")    
                        }
                    }
                }
            }
            .task {
                if vm.dashboard == nil { await vm.loadDashboard() }
            }
            .sheet(isPresented: $showPredict) {
                NavigationStack {
                    PredictView(vm: vm)
                        .toolbar {
                            ToolbarItem(placement: .navigationBarTrailing) {
                                Button("Done") { showPredict = false }
                            }
                        }
                }
            }
        }
    }
}

struct PanchaBanner: View {
    let panchanga: Panchanga
    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: "moon.stars.fill").foregroundStyle(Color.gold)
            VStack(alignment: .leading, spacing: 2) {
                Text("\(panchanga.vaar)  ·  \(panchanga.tithi.paksha.capitalized) \(panchanga.tithi.name)")
                    .font(.subheadline)
                Text("Sankranti: \(panchanga.sankranti)  ·  \(panchanga.date)")
                    .font(.caption).foregroundStyle(.secondary)
            }
        }
        .padding(.vertical, 4)
    }
}

struct DashboardRowView: View {
    let item: DashboardTickerItem

    var body: some View {
        HStack(spacing: 10) {
            // Coloured signal bar
            RoundedRectangle(cornerRadius: 2)
                .fill(signalColor(item.prediction.signal))
                .frame(width: 4, height: 38)

            // Ticker + exchange
            VStack(alignment: .leading, spacing: 2) {
                Text(item.ticker).font(.system(.body, weight: .semibold))
                Text(item.exchange).font(.caption2).foregroundStyle(.secondary)
            }

            Spacer()

            // Price + change
            VStack(alignment: .trailing, spacing: 2) {
                Text(fmtPrice(item.price.price))
                    .font(.system(.subheadline, weight: .medium))
                let pct = item.price.changePct
                Text("\(pct >= 0 ? "+" : "")\(String(format: "%.2f", pct))%")
                    .font(.caption)
                    .foregroundStyle(pct >= 0 ? Color.bull : Color.bear)
            }

            // BUY / SELL / HOLD chip
            VStack(alignment: .trailing, spacing: 3) {
                let action = verdictAction(item.prediction)
                Text(action)
                    .font(.system(.caption, weight: .bold))
                    .foregroundStyle(.white)
                    .padding(.horizontal, 8).padding(.vertical, 3)
                    .background(signalColor(item.prediction.signal))
                    .clipShape(Capsule())
                Text("\(item.prediction.confidence)%")
                    .font(.caption2).foregroundStyle(.secondary)
            }
        }
        .padding(.vertical, 3)
    }

    private func fmtPrice(_ v: Double) -> String {
        v >= 1000 ? "₹\(String(format: "%.0f", v))" : "₹\(String(format: "%.2f", v))"
    }
}

// ── Ticker Detail ─────────────────────────────────────────────────────────────

struct TickerDetailView: View {
    @ObservedObject var vm: AppViewModel
    let item: DashboardTickerItem

    @State private var horizon       = "1D"
    @State private var detailResp: PredictionResponse?
    @State private var isLoading     = false
    @State private var showPrashna   = false
    @State private var prashnaResp: PrashnaResponse?
    @State private var prashnaLoading = false

    private let horizons      = ["1D","1W","2W","1M","3M"]
    private let horizonLabels = ["1D":"1 Day","1W":"1 Week","2W":"2 Weeks","1M":"1 Month","3M":"3 Months"]

    private var prediction: PredictionResult { detailResp?.prediction ?? item.prediction }
    private var price: PriceQuote            { detailResp?.price      ?? item.price }
    private var panchanga: Panchanga?        { detailResp?.panchanga  ?? vm.dashboard?.panchanga }

    var body: some View {
        ScrollView {
            VStack(spacing: 14) {

                // 1 ── Final verdict (the one clear answer)
                VerdictCard(
                    prediction: prediction,
                    prashna: prashnaResp?.prashna,
                    ticker: item.ticker,
                    horizon: horizon
                )

                // 2 ── Price facts
                DetailPriceCard(exchange: item.exchange, signal: item.prediction.signal, price: price)

                // 3 ── Prashna quick-read banner
                PrashnaBannerButton(isLoading: prashnaLoading, response: prashnaResp) {
                    showPrashna = true
                } onAsk: {
                    Task { await fetchPrashna() }
                }

                // 4 ── Deep analysis (collapsed under a disclosure group)
                DisclosureGroup {
                    VStack(spacing: 14) {
                        // Horizon picker + engine weights
                        DetailSignalCard(
                            prediction: prediction,
                            horizon: horizon,
                            horizons: horizons,
                            horizonLabels: horizonLabels,
                            isLoading: isLoading
                        ) { h in
                            horizon = h
                            Task { await fetchDetail() }
                        }

                        // Projected chart
                        if !prediction.chartData.isEmpty {
                            DetailChartCard(chartData: prediction.chartData,
                                            signal: prediction.signal, horizon: horizon)
                        }

                        // All factors
                        DetailFactorsCard(prediction: prediction)
                    }
                } label: {
                    HStack {
                        Image(systemName: "chart.bar.doc.horizontal")
                            .foregroundStyle(.secondary)
                        Text("Detailed Analysis")
                            .font(.system(.subheadline, weight: .semibold))
                        Spacer()
                        let fs = prediction.factorSummary
                        if let fs {
                            Text("\(fs.bull)↑ \(fs.bear)↓")
                                .font(.caption).foregroundStyle(.secondary)
                        }
                    }
                    .padding(.vertical, 2)
                }
                .padding(14)
                .background(Color.cardBG)
                .clipShape(RoundedRectangle(cornerRadius: 16))
                .overlay(RoundedRectangle(cornerRadius: 16).stroke(Color(.separator), lineWidth: 0.5))

                Text(prediction.disclaimer)
                    .font(.caption2).foregroundStyle(.tertiary)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal)
                    .padding(.bottom, 24)
            }
            .padding(16)
        }
        .navigationTitle(item.ticker)
        .navigationBarTitleDisplayMode(.large)
        .task { await fetchDetail() }
        .sheet(isPresented: $showPrashna) {
            if let resp = prashnaResp {
                PrashnaDetailSheet(response: resp)
            }
        }
    }

    private func fetchDetail() async {
        isLoading = true
        if let resp = try? await vm.net.predict(
            ticker: item.ticker, exchange: item.exchange,
            category: item.category, horizon: horizon, mode: "both"
        ) { detailResp = resp }
        isLoading = false
    }

    private func fetchPrashna() async {
        prashnaLoading = true
        if let resp = try? await vm.net.getPrashna(
            ticker: item.ticker, exchange: item.exchange, category: item.category
        ) {
            prashnaResp = resp
            showPrashna = true
        }
        prashnaLoading = false
    }
}

// ── Detail sub-cards ──────────────────────────────────────────────────────────

struct DetailPriceCard: View {
    let exchange: String
    let signal: String
    let price: PriceQuote

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(alignment: .top) {
                VStack(alignment: .leading, spacing: 4) {
                    HStack(alignment: .firstTextBaseline, spacing: 8) {
                        Text(fmtLarge(price.price))
                            .font(.system(.title, weight: .bold))
                        Text(exchange)
                            .font(.caption)
                            .padding(.horizontal, 8).padding(.vertical, 3)
                            .background(Color.surface)
                            .clipShape(Capsule())
                    }
                    let pos = price.changePct >= 0
                    HStack(spacing: 5) {
                        Image(systemName: pos ? "arrow.up.right" : "arrow.down.right")
                        Text("\(pos ? "+" : "")\(String(format: "%.2f", price.change))  (\(pos ? "+" : "")\(String(format: "%.2f", price.changePct))%)")
                    }
                    .font(.subheadline)
                    .foregroundStyle(pos ? Color.bull : Color.bear)
                }
                Spacer()
                VStack(alignment: .trailing, spacing: 2) {
                    Circle()
                        .fill(signalColor(signal))
                        .frame(width: 10, height: 10)
                    Text(sourceLabel(price.source))
                        .font(.caption2).foregroundStyle(.secondary)
                    if isDelayed(price.source) {
                        Text("~15 min delay")
                            .font(.system(size: 9))
                            .foregroundStyle(.tertiary)
                    }
                }
            }

            Divider()

            // OHLC
            HStack(spacing: 0) {
                OHLCCell(label: "Open",  value: fmtSmall(price.open))
                Divider()
                OHLCCell(label: "High",  value: fmtSmall(price.high))
                Divider()
                OHLCCell(label: "Low",   value: fmtSmall(price.low))
                Divider()
                OHLCCell(label: "Close", value: fmtSmall(price.close))
            }
            .frame(height: 52)
        }
        .padding(16)
        .background(Color.cardBG)
        .clipShape(RoundedRectangle(cornerRadius: 16))
        .overlay(RoundedRectangle(cornerRadius: 16).stroke(Color(.separator), lineWidth: 0.5))
    }

    private func fmtLarge(_ v: Double) -> String { v >= 1000 ? "₹\(String(format: "%.0f", v))" : "₹\(String(format: "%.2f", v))" }
    private func fmtSmall(_ v: Double) -> String { v >= 1000 ? "₹\(String(format: "%.0f", v))" : "₹\(String(format: "%.1f", v))" }
    private func sourceLabel(_ s: String) -> String {
        if s.contains("mock") { return "Simulated" }
        if s.contains("nsepython") { return "NSE Live" }
        return "yfinance"
    }
    private func isDelayed(_ s: String) -> Bool { s.contains("yfinance") }
}

struct OHLCCell: View {
    let label: String; let value: String
    var body: some View {
        VStack(spacing: 3) {
            Text(value).font(.system(.caption, weight: .medium))
            Text(label).font(.caption2).foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity)
    }
}

struct DetailSignalCard: View {
    let prediction: PredictionResult
    let horizon: String
    let horizons: [String]
    let horizonLabels: [String: String]
    let isLoading: Bool
    let onHorizonChange: (String) -> Void

    var body: some View {
        VStack(spacing: 0) {
            // Metrics row
            HStack(spacing: 0) {
                MetricCell(value: prediction.signalLabel, label: "Signal",
                           color: signalColor(prediction.signal))
                Divider()
                MetricCell(value: "\(prediction.confidence)%", label: "Confidence",
                           color: signalColor(prediction.signal))
                Divider()
                MetricCell(value: prediction.expectedMove, label: "Exp. Move",
                           color: expectedMoveColor(prediction.expectedMove))
            }
            .frame(height: 70)

            Divider()

            // Composite score
            HStack {
                Text("Composite Score").font(.caption).foregroundStyle(.secondary)
                Spacer()
                let s = prediction.score
                Text(s >= 0 ? "+\(String(format: "%.3f", s))" : String(format: "%.3f", s))
                    .font(.system(.caption, weight: .semibold))
                    .foregroundStyle(s > 0 ? Color.bull : s < 0 ? Color.bear : Color.neutral)
            }
            .padding(.horizontal, 16).padding(.vertical, 10)

            // Engine weights breakdown
            if let ew = prediction.engineWeights {
                Divider()
                EngineWeightsBar(weights: ew)
                    .padding(.horizontal, 16).padding(.vertical, 10)
            }

            Divider()

            // Horizon picker
            VStack(alignment: .leading, spacing: 8) {
                Text("Prediction Horizon")
                    .font(.caption).foregroundStyle(.secondary)
                    .padding(.horizontal, 16).padding(.top, 10)
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 8) {
                        ForEach(horizons, id: \.self) { h in
                            Button { onHorizonChange(h) } label: {
                                VStack(spacing: 1) {
                                    Text(h).font(.system(.caption, weight: .semibold))
                                    Text(horizonLabels[h] ?? h).font(.caption2)
                                }
                                .padding(.horizontal, 14).padding(.vertical, 8)
                                .background(horizon == h ? Color.accent : Color.surface)
                                .foregroundStyle(horizon == h ? .white : Color.primary)
                                .clipShape(RoundedRectangle(cornerRadius: 10))
                            }
                        }
                        if isLoading { ProgressView().controlSize(.small).padding(.leading, 4) }
                    }
                    .padding(.horizontal, 16).padding(.bottom, 12)
                }
            }
        }
        .background(Color.cardBG)
        .clipShape(RoundedRectangle(cornerRadius: 16))
        .overlay(RoundedRectangle(cornerRadius: 16).stroke(Color(.separator), lineWidth: 0.5))
    }
}

struct DetailPanchaCard: View {
    let panchanga: Panchanga
    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(spacing: 8) {
                Image(systemName: "moon.stars.fill").foregroundStyle(Color.gold)
                Text("Panchanga · \(panchanga.date)")
                    .font(.caption).foregroundStyle(.secondary)
            }
            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 8) {
                PanchaCard(icon: "sun.and.horizon",  label: "Vaar",      value: panchanga.vaar)
                PanchaCard(icon: "circle.dotted",    label: "Paksha",    value: panchanga.tithi.paksha.capitalized)
                PanchaCard(icon: "calendar",         label: "Tithi",     value: panchanga.tithi.name)
                PanchaCard(icon: "arrow.triangle.2.circlepath", label: "Sankranti", value: panchanga.sankranti)
            }
        }
        .padding(14)
        .background(Color.cardBG)
        .clipShape(RoundedRectangle(cornerRadius: 16))
        .overlay(RoundedRectangle(cornerRadius: 16).stroke(Color(.separator), lineWidth: 0.5))
    }
}

struct DetailChartCard: View {
    let chartData: [ChartPoint]
    let signal: String
    let horizon: String

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Projected Scenario · \(horizon)")
                .font(.caption).foregroundStyle(.secondary).textCase(.uppercase)

            Chart(chartData) { pt in
                LineMark(
                    x: .value("Period", pt.label),
                    y: .value("Value", pt.value)
                )
                .foregroundStyle(signalColor(signal))
                .interpolationMethod(.catmullRom)

                AreaMark(
                    x: .value("Period", pt.label),
                    y: .value("Value", pt.value)
                )
                .foregroundStyle(signalColor(signal).opacity(0.12))
                .interpolationMethod(.catmullRom)
            }
            .frame(height: 130)
            .chartYScale(domain: .automatic(includesZero: false))
            .chartXAxis {
                AxisMarks { _ in AxisValueLabel().font(.caption2) }
            }
            .chartYAxis {
                AxisMarks(position: .trailing, values: .automatic(desiredCount: 3)) { _ in
                    AxisValueLabel().font(.caption2)
                }
            }
        }
        .padding(16)
        .background(Color.cardBG)
        .clipShape(RoundedRectangle(cornerRadius: 16))
        .overlay(RoundedRectangle(cornerRadius: 16).stroke(Color(.separator), lineWidth: 0.5))
    }
}

struct DetailFactorsCard: View {
    let prediction: PredictionResult

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            // Summary header
            HStack(spacing: 14) {
                if let fs = prediction.factorSummary {
                    FactorCountBadge(count: fs.bull,    label: "Bull",    color: .bull)
                    FactorCountBadge(count: fs.bear,    label: "Bear",    color: .bear)
                    FactorCountBadge(count: fs.neutral, label: "Neutral", color: .neutral)
                }
                Spacer()
                Text("Analysis Factors")
                    .font(.caption).foregroundStyle(.secondary)
            }
            .padding(16)

            Divider()

            ForEach(Array(prediction.factors.enumerated()), id: \.element.id) { idx, f in
                DetailedFactorRow(factor: f)
                if idx < prediction.factors.count - 1 { Divider().padding(.leading, 40) }
            }
        }
        .background(Color.cardBG)
        .clipShape(RoundedRectangle(cornerRadius: 16))
        .overlay(RoundedRectangle(cornerRadius: 16).stroke(Color(.separator), lineWidth: 0.5))
    }
}

struct DetailedFactorRow: View {
    let factor: Factor

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(alignment: .top, spacing: 10) {
                Circle()
                    .fill(signalColor(factor.signal))
                    .frame(width: 10, height: 10)
                    .padding(.top, 4)

                VStack(alignment: .leading, spacing: 3) {
                    HStack {
                        Text(factor.name).font(.system(.subheadline, weight: .semibold))
                        Spacer()
                        let s = factor.score
                        Text(s >= 0 ? "+\(String(format: "%.2f", s))" : String(format: "%.2f", s))
                            .font(.caption)
                            .padding(.horizontal, 8).padding(.vertical, 2)
                            .background(signalColor(factor.signal).opacity(0.12))
                            .foregroundStyle(signalColor(factor.signal))
                            .clipShape(Capsule())
                    }
                    Text(factor.description)
                        .font(.caption).foregroundStyle(.secondary)
                        .fixedSize(horizontal: false, vertical: true)
                    Text(factor.source)
                        .font(.caption2).foregroundStyle(.tertiary)
                        .padding(.top, 1)
                }
            }

            // Confidence bar
            HStack(spacing: 6) {
                Text("Confidence").font(.caption2).foregroundStyle(.tertiary)
                    .frame(width: 68, alignment: .leading)
                GeometryReader { geo in
                    ZStack(alignment: .leading) {
                        RoundedRectangle(cornerRadius: 2).fill(Color(.systemFill))
                        RoundedRectangle(cornerRadius: 2)
                            .fill(signalColor(factor.signal))
                            .frame(width: max(0, geo.size.width * Double(factor.confidence) / 100))
                    }
                    .frame(height: 4)
                }
                Text("\(factor.confidence)%")
                    .font(.caption2).foregroundStyle(.secondary)
                    .frame(width: 30, alignment: .trailing)
            }
            .frame(height: 14)
            .padding(.leading, 20)
        }
        .padding(.horizontal, 16).padding(.vertical, 12)
    }
}

struct FactorCountBadge: View {
    let count: Int; let label: String; let color: Color
    var body: some View {
        HStack(spacing: 4) {
            Circle().fill(color).frame(width: 8, height: 8)
            Text("\(count) \(label)").font(.caption).foregroundStyle(.secondary)
        }
    }
}

// ── Verdict helpers ───────────────────────────────────────────────────────────

/// Converts a prediction into a plain BUY / SELL / HOLD string.
func verdictAction(_ p: PredictionResult) -> String {
    switch p.signal {
    case "bull": return p.confidence >= 70 ? "STRONG BUY" : "BUY"
    case "bear": return p.confidence >= 70 ? "STRONG SELL" : "SELL"
    default:     return "HOLD"
    }
}

/// One or two sentence plain-English summary for non-expert users.
func verdictSummary(_ p: PredictionResult, prashna: PrashnaReading?, horizon: String) -> String {
    let fs      = p.factorSummary
    let bull    = fs?.bull    ?? 0
    let bear    = fs?.bear    ?? 0
    let total   = bull + bear + (fs?.neutral ?? 0)
    let leading = bull > bear ? bull : bear
    let dir     = bull > bear ? "bullish" : (bear > bull ? "bearish" : "mixed")

    // Leading source — pick from top-scored factor's source field
    let topSource: String = {
        guard let top = p.factors.max(by: { abs($0.score) < abs($1.score) }) else { return "" }
        let src = top.source.lowercased()
        if src.contains("vyapar")    { return "Vyapar Ratna timing" }
        if src.contains("prasna")    { return "Prasna Marga horary" }
        if src.contains("bhavartha") { return "Bhavartha planetary yoga" }
        if src.contains("kalamrita") { return "Uttara Kalamrita" }
        if src.contains("brihat")    { return "Brihat Samhita transit" }
        if src.contains("mediniya") || src.contains("mundane") { return "Mundane Jyotish cycle" }
        if src.contains("technical") { return "technical momentum" }
        return ""
    }()

    var lines: [String] = []

    // Line 1: direction + count
    if total > 0 {
        lines.append("\(leading) of \(total) signals are \(dir)\(topSource.isEmpty ? "" : ", led by \(topSource)").")
    }

    // Line 2: Prashna alignment
    if let pr = prashna {
        if pr.signal == p.signal {
            lines.append("Horary reading (\(pr.queryPlanet.capitalized) Vaar) confirms — \(pr.action) with \(Int(pr.confidence))% confidence.")
        } else if pr.signal != "neutral" && p.signal != "neutral" {
            lines.append("⚠ Horary (\(pr.queryPlanet.capitalized) Vaar) gives a contrary \(pr.action) signal — treat with extra caution.")
        }
    } else {
        // Horizon hint
        switch horizon {
        case "1D": lines.append("Short-term view — intraday noise may override. Use tight stops.")
        case "3M": lines.append("Long-term view — Dasa timing is most reliable at this horizon.")
        default: break
        }
    }

    return lines.joined(separator: " ")
}

// ── Verdict Card ─────────────────────────────────────────────────────────────

struct VerdictCard: View {
    let prediction: PredictionResult
    let prashna: PrashnaReading?
    let ticker: String
    let horizon: String

    var body: some View {
        let action  = verdictAction(prediction)
        let summary = verdictSummary(prediction, prashna: prashna, horizon: horizon)
        let color   = signalColor(prediction.signal)

        VStack(spacing: 0) {
            // Top colour band with action
            HStack(alignment: .center, spacing: 16) {
                VStack(alignment: .leading, spacing: 4) {
                    Text(action)
                        .font(.system(size: 28, weight: .black))
                        .foregroundStyle(color)
                    Text("\(ticker) · \(horizon)")
                        .font(.caption).foregroundStyle(.secondary)
                }
                Spacer()
                // Confidence ring
                ZStack {
                    Circle()
                        .stroke(color.opacity(0.15), lineWidth: 6)
                        .frame(width: 58, height: 58)
                    Circle()
                        .trim(from: 0, to: Double(prediction.confidence) / 100)
                        .stroke(color, style: StrokeStyle(lineWidth: 6, lineCap: .round))
                        .rotationEffect(.degrees(-90))
                        .frame(width: 58, height: 58)
                    Text("\(prediction.confidence)%")
                        .font(.system(.caption, weight: .bold))
                        .foregroundStyle(color)
                }
            }
            .padding(16)

            Divider()

            // Summary text
            Text(summary)
                .font(.subheadline)
                .foregroundStyle(.primary)
                .fixedSize(horizontal: false, vertical: true)
                .padding(16)
        }
        .background(color.opacity(0.06))
        .clipShape(RoundedRectangle(cornerRadius: 18))
        .overlay(RoundedRectangle(cornerRadius: 18).stroke(color.opacity(0.25), lineWidth: 1.5))
    }
}

// ── Engine Weights Breakdown Bar ──────────────────────────────────────────────

struct EngineWeightsBar: View {
    let weights: EngineWeights

    // Fixed display order and colors
    private struct Segment: Identifiable {
        let id = UUID()
        let label: String
        let shortLabel: String
        let value: Int
        let color: Color
    }

    private var segments: [Segment] {
        var segs: [Segment] = [
            // VR: brand saffron — the flagship engine
            Segment(label: "Vyapar Ratna",    shortLabel: "VR",  value: weights.vyaparRatna,
                    color: Color(red: 0.73, green: 0.36, blue: 0.04)),
            // BR: emerald — mirrors the bull signal color (wealth yoga)
            Segment(label: "Bhavartha",        shortLabel: "BR",  value: weights.bhavartha,
                    color: Color(red: 0.05, green: 0.60, blue: 0.38)),
            // UK: deep teal — Kalidasa's systematic approach
            Segment(label: "Uttara Kalamrita", shortLabel: "UK",  value: weights.kalamrita,
                    color: Color(red: 0.04, green: 0.52, blue: 0.56)),
            // BS: rust — Varahamihira's slow planetary transits
            Segment(label: "Brihat Samhita",   shortLabel: "BS",  value: weights.brihat,
                    color: Color(red: 0.72, green: 0.25, blue: 0.06)),
            // MJ: slate blue — seasonal and mundane cycles
            Segment(label: "Mundane",          shortLabel: "MJ",  value: weights.mundane,
                    color: Color(red: 0.24, green: 0.44, blue: 0.76)),
            // TA: charcoal — technical/data-driven, intentionally muted
            Segment(label: "Technical",        shortLabel: "TA",  value: weights.technical,
                    color: Color(red: 0.32, green: 0.32, blue: 0.36)),
        ]
        // Prasna only shown when non-zero (excluded at 1M, 3M horizons)
        if weights.prasna > 0 {
            // PM: violet — horary/intuitive, distinct from all others
            segs.insert(Segment(label: "Prasna Marga", shortLabel: "PM", value: weights.prasna,
                                color: Color(red: 0.53, green: 0.22, blue: 0.78)), at: 1)
        }
        return segs
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Text("Engine Weights").font(.caption).foregroundStyle(.secondary)
                Spacer()
                Text(weights.category.capitalized + " · " + weights.horizon)
                    .font(.caption2).foregroundStyle(.tertiary)
            }

            // Stacked bar
            GeometryReader { geo in
                HStack(spacing: 2) {
                    ForEach(segments) { seg in
                        if seg.value > 0 {
                            RoundedRectangle(cornerRadius: 3)
                                .fill(seg.color)
                                .frame(width: max(0, geo.size.width * Double(seg.value) / 100))
                        }
                    }
                }
            }
            .frame(height: 8)
            .clipShape(RoundedRectangle(cornerRadius: 4))

            // Legend
            HStack(spacing: 12) {
                ForEach(segments) { seg in
                    HStack(spacing: 4) {
                        RoundedRectangle(cornerRadius: 2).fill(seg.color)
                            .frame(width: 10, height: 10)
                        Text("\(seg.shortLabel) \(seg.value)%")
                            .font(.caption2).foregroundStyle(.secondary)
                    }
                }
            }
        }
    }
}

// ── Prashna Banner + Sheet ────────────────────────────────────────────────────

struct PrashnaBannerButton: View {
    let isLoading: Bool
    let response: PrashnaResponse?
    let onShowSheet: () -> Void
    let onAsk: () -> Void

    var body: some View {
        HStack(spacing: 12) {
            // Icon
            ZStack {
                Circle().fill(Color.accent.opacity(0.12)).frame(width: 40, height: 40)
                Image(systemName: "sparkles").font(.system(size: 18)).foregroundStyle(Color.accent)
            }

            VStack(alignment: .leading, spacing: 2) {
                Text("Prashna — Horary Signal")
                    .font(.system(.subheadline, weight: .semibold))
                if let r = response?.prashna {
                    Text("\(r.queryPlanet.capitalized) Vaar · \(r.queryAbout)")
                        .font(.caption).foregroundStyle(.secondary)
                        .lineLimit(1)
                } else {
                    Text("Uttara Kalamrita · Ch VII — Ask right now")
                        .font(.caption).foregroundStyle(.secondary)
                }
            }

            Spacer()

            if let r = response?.prashna {
                // Show result badge + tap to expand
                Button(action: onShowSheet) {
                    VStack(spacing: 2) {
                        Text(r.action)
                            .font(.system(.caption, weight: .bold))
                            .foregroundStyle(.white)
                            .padding(.horizontal, 10).padding(.vertical, 4)
                            .background(actionColor(r.action))
                            .clipShape(Capsule())
                        Text("\(Int(r.confidence))%")
                            .font(.caption2).foregroundStyle(.secondary)
                    }
                }
            } else if isLoading {
                ProgressView().controlSize(.small)
            } else {
                Button(action: onAsk) {
                    Text("Ask")
                        .font(.system(.caption, weight: .semibold))
                        .foregroundStyle(.white)
                        .padding(.horizontal, 14).padding(.vertical, 6)
                        .background(Color.accent)
                        .clipShape(Capsule())
                }
            }
        }
        .padding(14)
        .background(Color.cardBG)
        .clipShape(RoundedRectangle(cornerRadius: 16))
        .overlay(RoundedRectangle(cornerRadius: 16).stroke(Color.accent.opacity(0.25), lineWidth: 1))
        .onTapGesture { if response != nil { onShowSheet() } }
    }

    private func actionColor(_ action: String) -> Color {
        switch action {
        case "BUY":  return Color.bull
        case "SELL": return Color.bear
        default:     return Color.neutral
        }
    }
}

struct PrashnaDetailSheet: View {
    let response: PrashnaResponse
    @Environment(\.dismiss) private var dismiss

    private var r: PrashnaReading { response.prashna }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 16) {

                    // Action card
                    VStack(spacing: 8) {
                        Text(r.action)
                            .font(.system(size: 48, weight: .bold))
                            .foregroundStyle(actionColor(r.action))
                        Text("\(r.ticker) · \(r.category.capitalized)")
                            .font(.subheadline).foregroundStyle(.secondary)
                        Text("Confidence \(Int(r.confidence))%")
                            .font(.system(.callout, weight: .semibold))
                            .foregroundStyle(actionColor(r.action))
                    }
                    .frame(maxWidth: .infinity)
                    .padding(24)
                    .background(actionColor(r.action).opacity(0.08))
                    .clipShape(RoundedRectangle(cornerRadius: 18))

                    // What is Prashna — explanation card
                    VStack(alignment: .leading, spacing: 8) {
                        Label("What is Prashna?", systemImage: "clock.badge.questionmark")
                            .font(.system(.subheadline, weight: .semibold))
                        Text(r.prashnaMeaning)
                            .font(.caption).foregroundStyle(.secondary)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                    .padding(14)
                    .background(Color.accent.opacity(0.07))
                    .clipShape(RoundedRectangle(cornerRadius: 14))
                    .overlay(RoundedRectangle(cornerRadius: 14).stroke(Color.accent.opacity(0.20), lineWidth: 1))

                    // Query details
                    VStack(alignment: .leading, spacing: 12) {
                        sheetRow(icon: "clock",          label: "Query Cast At", value: formattedTime(response.queryTime))
                        sheetRow(icon: "star.fill",      label: "Query Planet",  value: r.queryPlanet.capitalized)
                        sheetRow(icon: "magnifyingglass",label: "Query About",   value: r.queryAbout.capitalized)
                        sheetRow(icon: "moon.stars",     label: "Tithi Effect",  value: r.tithiEffect.capitalized,
                                 accent: r.tithiEffect == "positive" ? Color.bull : r.tithiEffect == "negative" ? Color.bear : Color.neutral)
                        Divider()
                        VStack(alignment: .leading, spacing: 4) {
                            Label("Interpretation", systemImage: "text.quote")
                                .font(.caption).foregroundStyle(.secondary)
                            Text(r.note)
                                .font(.subheadline)
                                .fixedSize(horizontal: false, vertical: true)
                        }
                        Divider()
                        sheetRow(icon: "book.closed",label: "Source",     value: r.source)
                        sheetRow(icon: "gauge",      label: "Reliability",value: r.reliability.capitalized)
                    }
                    .padding(16)
                    .background(Color.cardBG)
                    .clipShape(RoundedRectangle(cornerRadius: 16))
                    .overlay(RoundedRectangle(cornerRadius: 16).stroke(Color(.separator), lineWidth: 0.5))

                    // Reconciliation — when Prashna may differ from market prediction
                    VStack(alignment: .leading, spacing: 8) {
                        Label("If this differs from the market prediction…", systemImage: "arrow.triangle.branch")
                            .font(.system(.caption, weight: .semibold))
                            .foregroundStyle(.secondary)
                        Text(r.reconciliation)
                            .font(.caption).foregroundStyle(.secondary)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                    .padding(14)
                    .background(Color(.systemFill))
                    .clipShape(RoundedRectangle(cornerRadius: 12))

                    // Panchanga snapshot
                    VStack(alignment: .leading, spacing: 10) {
                        Label("Panchanga at Query Time", systemImage: "moon.stars.fill")
                            .font(.caption).foregroundStyle(.secondary)
                        LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 8) {
                            PanchaCard(icon: "sun.and.horizon",  label: "Vaar",    value: response.panchanga.vaar)
                            PanchaCard(icon: "circle.dotted",    label: "Paksha",  value: response.panchanga.tithi.paksha.capitalized)
                            PanchaCard(icon: "calendar",         label: "Tithi",   value: response.panchanga.tithi.name)
                            PanchaCard(icon: "arrow.triangle.2.circlepath", label: "Sankranti", value: response.panchanga.sankranti)
                        }
                    }
                    .padding(14)
                    .background(Color.cardBG)
                    .clipShape(RoundedRectangle(cornerRadius: 16))
                    .overlay(RoundedRectangle(cornerRadius: 16).stroke(Color(.separator), lineWidth: 0.5))

                    Text("Prashna (Horary) is based on the moment of the query, not a natal chart. For educational purposes only.")
                        .font(.caption2).foregroundStyle(.tertiary)
                        .multilineTextAlignment(.center)
                        .padding(.horizontal)
                        .padding(.bottom, 24)
                }
                .padding(16)
            }
            .navigationTitle("Prashna Reading")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Done") { dismiss() }
                }
            }
        }
    }

    @ViewBuilder
    private func sheetRow(icon: String, label: String, value: String, accent: Color = .primary) -> some View {
        HStack(spacing: 10) {
            Image(systemName: icon).font(.caption).foregroundStyle(.secondary).frame(width: 20)
            Text(label).font(.caption).foregroundStyle(.secondary)
            Spacer()
            Text(value).font(.system(.caption, weight: .semibold)).foregroundStyle(accent)
        }
    }

    private func actionColor(_ action: String) -> Color {
        switch action {
        case "BUY":  return Color.bull
        case "SELL": return Color.bear
        default:     return Color.neutral
        }
    }

    private func formattedTime(_ iso: String) -> String {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withFullDate, .withTime, .withColonSeparatorInTime]
        if let d = f.date(from: iso) {
            let df = DateFormatter()
            df.dateStyle = .medium
            df.timeStyle = .short
            return df.string(from: d)
        }
        return iso
    }
}

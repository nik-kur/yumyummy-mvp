import SwiftUI
import WidgetKit

// MARK: - Timeline

struct YYEntry: TimelineEntry {
    let date: Date
    let snap: YYSnapshot
}

struct YYProvider: TimelineProvider {
    func placeholder(in context: Context) -> YYEntry {
        YYEntry(date: Date(), snap: .placeholder)
    }

    func getSnapshot(in context: Context, completion: @escaping (YYEntry) -> Void) {
        completion(YYEntry(date: Date(), snap: YYSnapshot.load()))
    }

    func getTimeline(in context: Context, completion: @escaping (Timeline<YYEntry>) -> Void) {
        let entry = YYEntry(date: Date(), snap: YYSnapshot.load())
        // The app reloads the widget on every refresh; this is just a safety net.
        let next = Calendar.current.date(byAdding: .minute, value: 30, to: Date())
            ?? Date().addingTimeInterval(1800)
        completion(Timeline(entries: [entry], policy: .after(next)))
    }
}

// MARK: - Reusable pieces

struct CalorieRing: View {
    var progress: Double
    var lineWidth: CGFloat = 9

    var body: some View {
        ZStack {
            Circle().stroke(YY.hairline, lineWidth: lineWidth)
            Circle()
                .trim(from: 0, to: progress)
                .stroke(YY.terracotta, style: StrokeStyle(lineWidth: lineWidth, lineCap: .round))
                .rotationEffect(.degrees(-90))
        }
    }
}

struct MacroBar: View {
    var label: String
    var value: Int
    var goal: Int
    var color: Color

    private var pct: Double { goal > 0 ? min(Double(value) / Double(goal), 1) : 0 }

    var body: some View {
        VStack(alignment: .leading, spacing: 3) {
            HStack {
                Text(label)
                    .font(.system(size: 10, weight: .semibold))
                    .foregroundStyle(YY.inkFaint)
                Spacer()
                Text("\(value)/\(goal)g")
                    .font(.system(size: 10))
                    .foregroundStyle(YY.inkMuted)
                    .monospacedDigit()
            }
            GeometryReader { geo in
                ZStack(alignment: .leading) {
                    Capsule().fill(YY.hairline)
                    Capsule().fill(color).frame(width: max(4, geo.size.width * pct))
                }
            }
            .frame(height: 5)
        }
    }
}

struct QuickButton: View {
    var symbol: String
    var label: String
    var dest: String

    var body: some View {
        Button(intent: YYLogIntent(dest: dest)) {
            VStack(spacing: 4) {
                Image(systemName: symbol)
                    .font(.system(size: 18))
                    .foregroundStyle(YY.terracotta)
                Text(label)
                    .font(.system(size: 10, weight: .medium))
                    .foregroundStyle(YY.inkMuted)
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 8)
            .background(YY.bg, in: RoundedRectangle(cornerRadius: 12))
        }
        .buttonStyle(.plain)
    }
}

// MARK: - Home-screen views

struct BalanceSmallView: View {
    var snap: YYSnapshot

    var body: some View {
        ZStack {
            CalorieRing(progress: snap.calorieProgress, lineWidth: 10)
            VStack(spacing: 1) {
                Text("\(snap.remaining)")
                    .font(.system(size: 26, weight: .bold))
                    .foregroundStyle(YY.ink)
                    .monospacedDigit()
                Text("KCAL LEFT")
                    .font(.system(size: 9, weight: .semibold))
                    .tracking(1)
                    .foregroundStyle(YY.inkFaint)
                HStack(spacing: 5) {
                    Circle().fill(YY.protein).frame(width: 7, height: 7)
                    Circle().fill(YY.carbs).frame(width: 7, height: 7)
                    Circle().fill(YY.fat).frame(width: 7, height: 7)
                }
                .padding(.top, 4)
            }
        }
    }
}

struct QuickSmallView: View {
    var body: some View {
        VStack(spacing: 8) {
            Text("LOG A MEAL")
                .font(.system(size: 10, weight: .bold))
                .tracking(1)
                .foregroundStyle(YY.inkFaint)
                .frame(maxWidth: .infinity, alignment: .leading)
            HStack(spacing: 10) {
                QuickButton(symbol: "pencil", label: "Text", dest: "text")
                QuickButton(symbol: "camera.fill", label: "Photo", dest: "photo")
            }
            HStack(spacing: 10) {
                QuickButton(symbol: "mic.fill", label: "Voice", dest: "voice")
                QuickButton(symbol: "bookmark.fill", label: "Saved", dest: "saved")
            }
        }
    }
}

struct ComboMediumView: View {
    var snap: YYSnapshot

    var body: some View {
        HStack(spacing: 14) {
            HStack(spacing: 12) {
                ZStack {
                    CalorieRing(progress: snap.calorieProgress, lineWidth: 9)
                    VStack(spacing: 0) {
                        Text("\(snap.remaining)")
                            .font(.system(size: 20, weight: .bold))
                            .foregroundStyle(YY.ink)
                            .monospacedDigit()
                        Text("LEFT")
                            .font(.system(size: 8, weight: .semibold))
                            .tracking(1)
                            .foregroundStyle(YY.inkFaint)
                    }
                }
                .frame(width: 92, height: 92)
                VStack(spacing: 7) {
                    MacroBar(label: "P", value: snap.protein, goal: snap.proteinGoal, color: YY.protein)
                    MacroBar(label: "C", value: snap.carbs, goal: snap.carbsGoal, color: YY.carbs)
                    MacroBar(label: "F", value: snap.fat, goal: snap.fatGoal, color: YY.fat)
                }
            }
            Divider()
            VStack(spacing: 8) {
                HStack(spacing: 8) {
                    QuickButton(symbol: "pencil", label: "Text", dest: "text")
                    QuickButton(symbol: "camera.fill", label: "Photo", dest: "photo")
                }
                HStack(spacing: 8) {
                    QuickButton(symbol: "mic.fill", label: "Voice", dest: "voice")
                    QuickButton(symbol: "bookmark.fill", label: "Saved", dest: "saved")
                }
            }
            .frame(width: 124)
        }
    }
}

// MARK: - Lock-screen (accessory) views

struct BalanceCircularView: View {
    var snap: YYSnapshot
    var body: some View {
        Gauge(value: snap.calorieProgress) {
            Text("kcal")
        } currentValueLabel: {
            Text("\(Int(snap.calorieProgress * 100))%")
        }
        .gaugeStyle(.accessoryCircularCapacity)
    }
}

struct BalanceRectangularView: View {
    var snap: YYSnapshot
    var body: some View {
        HStack(spacing: 8) {
            Gauge(value: snap.calorieProgress) { Text("") }
                .gaugeStyle(.accessoryCircularCapacity)
            VStack(alignment: .leading, spacing: 1) {
                Text("\(snap.remaining) kcal left").font(.headline)
                Text("P\(snap.protein)  C\(snap.carbs)  F\(snap.fat)")
                    .font(.caption2)
                    .monospacedDigit()
            }
        }
    }
}

// MARK: - Widgets

struct BalanceWidgetView: View {
    @Environment(\.widgetFamily) private var family
    var entry: YYEntry

    var body: some View {
        switch family {
        case .accessoryCircular:
            BalanceCircularView(snap: entry.snap)
                .containerBackground(.clear, for: .widget)
        case .accessoryRectangular:
            BalanceRectangularView(snap: entry.snap)
                .containerBackground(.clear, for: .widget)
        case .accessoryInline:
            Text("\(entry.snap.remaining) kcal left")
                .containerBackground(.clear, for: .widget)
        default:
            BalanceSmallView(snap: entry.snap)
                .padding(14)
                .containerBackground(YY.surface, for: .widget)
        }
    }
}

struct YumYummyBalanceWidget: Widget {
    let kind = "YumYummyBalance"
    var body: some WidgetConfiguration {
        StaticConfiguration(kind: kind, provider: YYProvider()) { entry in
            BalanceWidgetView(entry: entry)
                .widgetURL(URL(string: "yumyummy://"))
        }
        .configurationDisplayName("Balance")
        .description("Calories left and macro progress for today.")
        .supportedFamilies([.systemSmall, .accessoryCircular, .accessoryRectangular, .accessoryInline])
    }
}

struct YumYummyQuickWidget: Widget {
    let kind = "YumYummyQuick"
    var body: some WidgetConfiguration {
        StaticConfiguration(kind: kind, provider: YYProvider()) { _ in
            QuickSmallView()
                .padding(14)
                .containerBackground(YY.surface, for: .widget)
        }
        .configurationDisplayName("Quick log")
        .description("Two-tap buttons to log a meal.")
        .supportedFamilies([.systemSmall])
    }
}

struct YumYummyComboWidget: Widget {
    let kind = "YumYummyCombo"
    var body: some WidgetConfiguration {
        StaticConfiguration(kind: kind, provider: YYProvider()) { entry in
            ComboMediumView(snap: entry.snap)
                .padding(14)
                .containerBackground(YY.surface, for: .widget)
        }
        .configurationDisplayName("Balance + Quick log")
        .description("Today's balance with quick-log buttons.")
        .supportedFamilies([.systemMedium])
    }
}

@main
struct YumYummyWidgetBundle: WidgetBundle {
    var body: some Widget {
        YumYummyBalanceWidget()
        YumYummyQuickWidget()
        YumYummyComboWidget()
    }
}

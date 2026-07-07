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

/// "1,138" — comma grouping to match the app. SwiftUI's `Text("\(Int)")` would
/// otherwise localize the number (e.g. "1 138" with a space in ru locale).
/// The POSIX locale pins the separator regardless of device settings.
func yyFormat(_ n: Int) -> String {
    let f = NumberFormatter()
    f.locale = Locale(identifier: "en_US_POSIX")
    f.numberStyle = .decimal
    f.groupingSeparator = ","
    f.usesGroupingSeparator = true
    return f.string(from: NSNumber(value: n)) ?? "\(n)"
}

struct CalorieRing: View {
    var progress: Double
    var lineWidth: CGFloat = 8

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

/// Horizontal macro bar: colored letter · flexible track · value/goal.
/// Displayed in P → F → C order by callers. Fixed-width side columns keep the
/// three rows on the same grid regardless of the numbers inside.
struct MacroRow: View {
    var label: String
    var value: Int
    var goal: Int
    var color: Color
    var compact: Bool = false

    private var pct: Double { goal > 0 ? min(Double(value) / Double(goal), 1) : 0 }

    var body: some View {
        HStack(spacing: 8) {
            Text(label)
                .font(.system(size: compact ? 11 : 12, weight: .bold))
                .foregroundStyle(color)
                .frame(width: 12, alignment: .leading)
            GeometryReader { geo in
                ZStack(alignment: .leading) {
                    Capsule().fill(YY.hairline)
                    Capsule().fill(color).frame(width: max(4, geo.size.width * pct))
                }
            }
            .frame(height: compact ? 5 : 6)
            Text(verbatim: "\(value)/\(goal)g")
                .font(.system(size: compact ? 10 : 11, weight: .medium))
                .foregroundStyle(YY.inkMuted)
                .monospacedDigit()
                .lineLimit(1)
                .minimumScaleFactor(0.8)
                .frame(width: compact ? 62 : 72, alignment: .trailing)
        }
    }
}

/// Grid cell button. Stretches to fill its row; the fixed-height icon box keeps
/// labels on one baseline even though SF Symbols differ in intrinsic height.
struct QuickButton: View {
    var symbol: String
    var label: String
    var dest: String

    var body: some View {
        Button(intent: YYLogIntent(dest: dest)) {
            VStack(spacing: 5) {
                Image(systemName: symbol)
                    .font(.system(size: 17, weight: .medium))
                    .foregroundStyle(YY.terracotta)
                    .frame(height: 20)
                Text(label)
                    .font(.system(size: 10.5, weight: .medium))
                    .foregroundStyle(YY.inkMuted)
                    .lineLimit(1)
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .background(YY.bg, in: RoundedRectangle(cornerRadius: 12))
        }
        .buttonStyle(.plain)
    }
}

/// Shared header row: progress ring with % inside + "N kcal left" beside it.
struct BalanceHeader: View {
    var snap: YYSnapshot
    var numberSize: CGFloat

    private var pct: Int { Int((snap.calorieProgress * 100).rounded()) }

    var body: some View {
        HStack(spacing: 12) {
            ZStack {
                CalorieRing(progress: snap.calorieProgress, lineWidth: 7)
                Text(verbatim: "\(pct)%")
                    .font(.system(size: 13, weight: .bold))
                    .foregroundStyle(YY.ink)
                    .monospacedDigit()
                    .lineLimit(1)
                    .minimumScaleFactor(0.7)
                    .padding(.horizontal, 7)
            }
            .frame(width: 50, height: 50)

            VStack(alignment: .leading, spacing: 1) {
                Text(verbatim: yyFormat(snap.remaining))
                    .font(.system(size: numberSize, weight: .bold))
                    .foregroundStyle(YY.ink)
                    .monospacedDigit()
                    .minimumScaleFactor(0.7)
                    .lineLimit(1)
                Text("kcal left")
                    .font(.system(size: 11, weight: .medium))
                    .foregroundStyle(YY.inkMuted)
            }
            Spacer(minLength: 0)
        }
    }
}

// MARK: - Home-screen views

/// Dashboard (small): header on top, macro bars pinned to the bottom. The
/// spacer between them stretches, so the card is filled edge-to-edge with no
/// dead zone under the C row.
struct BalanceDashboardView: View {
    var snap: YYSnapshot

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            BalanceHeader(snap: snap, numberSize: 26)
            Spacer(minLength: 10)
            VStack(spacing: 8) {
                MacroRow(label: "P", value: snap.protein, goal: snap.proteinGoal, color: YY.protein, compact: true)
                MacroRow(label: "F", value: snap.fat, goal: snap.fatGoal, color: YY.fat, compact: true)
                MacroRow(label: "C", value: snap.carbs, goal: snap.carbsGoal, color: YY.carbs, compact: true)
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

struct QuickSmallView: View {
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("LOG A MEAL")
                .font(.system(size: 10, weight: .bold))
                .tracking(1)
                .foregroundStyle(YY.inkFaint)
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
            .frame(maxWidth: .infinity, maxHeight: .infinity)
        }
    }
}

/// Medium: the left column mirrors the small Balance layout (same grid), the
/// right column is a 2×2 button grid stretched to the full card height.
struct ComboMediumView: View {
    var snap: YYSnapshot

    var body: some View {
        HStack(spacing: 14) {
            VStack(alignment: .leading, spacing: 0) {
                BalanceHeader(snap: snap, numberSize: 24)
                Spacer(minLength: 10)
                VStack(spacing: 8) {
                    MacroRow(label: "P", value: snap.protein, goal: snap.proteinGoal, color: YY.protein, compact: true)
                    MacroRow(label: "F", value: snap.fat, goal: snap.fatGoal, color: YY.fat, compact: true)
                    MacroRow(label: "C", value: snap.carbs, goal: snap.carbsGoal, color: YY.carbs, compact: true)
                }
            }

            Divider().padding(.vertical, 2)

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
            .frame(width: 132)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

// MARK: - Lock-screen (single accessory widget)

/// Text-only lock-screen layout (no ring). `verbatim` keeps integers free of the
/// device's grouping separator (e.g. "1463", not "1 463") so nothing truncates.
struct BalanceRectangularView: View {
    var snap: YYSnapshot
    private var pct: Int { Int((snap.calorieProgress * 100).rounded()) }

    var body: some View {
        VStack(alignment: .leading, spacing: 3) {
            Text(verbatim: "\(pct)% · \(snap.eaten)/\(snap.goal) kcal")
                .font(.system(size: 12, weight: .medium))
                .foregroundStyle(.secondary)
                .lineLimit(1)

            (Text(verbatim: "\(snap.remaining)").font(.system(size: 19, weight: .bold))
                + Text(verbatim: " kcal left").font(.system(size: 15, weight: .regular)).foregroundColor(.secondary))
                .minimumScaleFactor(0.7)
                .lineLimit(1)
                .widgetAccentable()

            Text(verbatim: "P \(snap.protein)   F \(snap.fat)   C \(snap.carbs)")
                .font(.system(size: 12, weight: .medium))
                .monospacedDigit()
                .lineLimit(1)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

// MARK: - Widgets

struct BalanceWidgetView: View {
    @Environment(\.widgetFamily) private var family
    var entry: YYEntry

    var body: some View {
        switch family {
        case .accessoryRectangular:
            BalanceRectangularView(snap: entry.snap)
                .containerBackground(.clear, for: .widget)
        default:
            BalanceDashboardView(snap: entry.snap)
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
        .supportedFamilies([.systemSmall, .accessoryRectangular])
        .contentMarginsDisabled()
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
        .contentMarginsDisabled()
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
        .contentMarginsDisabled()
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

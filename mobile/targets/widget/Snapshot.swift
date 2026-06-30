import Foundation

/// Today's nutrition snapshot, written by the React Native app into the shared
/// App Group via `ExtensionStorage` and read here by the widget.
struct YYSnapshot: Codable {
    var eaten: Int
    var goal: Int
    var protein: Int
    var proteinGoal: Int
    var carbs: Int
    var carbsGoal: Int
    var fat: Int
    var fatGoal: Int
    var date: String      // YYYY-MM-DD the snapshot represents
    var updatedAt: Double // epoch seconds

    static let appGroup = "group.ai.yumyummy.app"
    static let storageKey = "today"

    /// Shown in the widget gallery and before the app has written real data.
    static var placeholder: YYSnapshot {
        YYSnapshot(
            eaten: 932, goal: 2080,
            protein: 113, proteinGoal: 180,
            carbs: 58, carbsGoal: 201,
            fat: 29, fatGoal: 62,
            date: "", updatedAt: 0
        )
    }

    static func load() -> YYSnapshot {
        guard
            let defaults = UserDefaults(suiteName: appGroup),
            let raw = defaults.string(forKey: storageKey),
            let data = raw.data(using: .utf8),
            var snap = try? JSONDecoder().decode(YYSnapshot.self, from: data)
        else {
            return placeholder
        }
        // Goals carry over day-to-day, but consumed values reset at midnight.
        // If the stored snapshot is from a previous day, zero the consumed side.
        let fmt = DateFormatter()
        fmt.calendar = Calendar(identifier: .gregorian)
        fmt.locale = Locale(identifier: "en_US_POSIX")
        fmt.dateFormat = "yyyy-MM-dd"
        let today = fmt.string(from: Date())
        if !snap.date.isEmpty && snap.date != today {
            snap.eaten = 0
            snap.protein = 0
            snap.carbs = 0
            snap.fat = 0
        }
        return snap
    }

    var remaining: Int { max(goal - eaten, 0) }
    var calorieProgress: Double { goal > 0 ? min(Double(eaten) / Double(goal), 1) : 0 }
}

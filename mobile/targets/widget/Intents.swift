import AppIntents
import Foundation

/// Opens the app at the right logging destination when a widget quick-button is
/// tapped. Deterministic navigation only — no AI runs in the widget process.
struct YYLogIntent: AppIntent {
    static var title: LocalizedStringResource = "Log a meal"
    static var openAppWhenRun: Bool = true

    @Parameter(title: "Destination")
    var dest: String

    init() {}
    init(dest: String) { self.dest = dest }

    @MainActor
    func perform() async throws -> some IntentResult & OpensIntent {
        let urlString: String
        switch dest {
        case "photo": urlString = "yumyummy://capture?mode=photo"
        case "voice": urlString = "yumyummy://capture?mode=voice"
        case "saved": urlString = "yumyummy://menu"
        default: urlString = "yumyummy://capture"
        }
        return .result(opensIntent: OpenURLIntent(URL(string: urlString)!))
    }
}

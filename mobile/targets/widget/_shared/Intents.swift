import AppIntents
import Foundation

/// Records which logging destination the user tapped in a widget, then opens the
/// app. The app reads `pendingCaptureMode` from the shared App Group on launch/
/// foreground and performs the navigation itself (see WidgetActionBridge on the
/// React Native side).
///
/// IMPORTANT: this file lives in `_shared/` so @bacons/apple-targets links it
/// into BOTH the widget extension AND the main app target. That dual membership
/// is required for `openAppWhenRun` to actually launch the host app when a
/// `Button(intent:)` is tapped — otherwise the intent runs only in the widget
/// process and the tap appears to do nothing.
///
/// Self-contained on purpose: it must compile in the app target, which does not
/// include the widget-only `YYSnapshot`, so the App Group is hardcoded here.
///
/// Gated to iOS 16 because the app target's deployment floor is 15.1 (RN/Expo
/// default) while `AppIntent` requires iOS 16+. Interactive widget buttons need
/// iOS 17 anyway, so this never restricts a real caller.
@available(iOS 16.0, *)
struct YYLogIntent: AppIntent {
    static var title: LocalizedStringResource = "Log a meal"
    static var openAppWhenRun: Bool = true

    static let appGroup = "group.ai.yumyummy.app"
    static let pendingKey = "pendingCaptureMode"

    @Parameter(title: "Destination")
    var dest: String

    init() {}
    init(dest: String) { self.dest = dest }

    func perform() async throws -> some IntentResult {
        let allowed: Set<String> = ["text", "photo", "voice", "saved"]
        let mode = allowed.contains(dest) ? dest : "text"
        UserDefaults(suiteName: Self.appGroup)?.set(mode, forKey: Self.pendingKey)
        return .result()
    }
}

import ExpoModulesCore
import WidgetKit

public class WidgetStatusModule: Module {
  public func definition() -> ModuleDefinition {
    Name("WidgetStatus")

    AsyncFunction("getInstalledWidgets") { (promise: Promise) in
      if #available(iOS 14.0, *) {
        WidgetCenter.shared.getCurrentConfigurations { result in
          switch result {
          case .success(let infos):
            let kinds = infos.map { $0.kind }
            promise.resolve(kinds)
          case .failure:
            promise.resolve([] as [String])
          }
        }
      } else {
        promise.resolve([] as [String])
      }
    }
  }
}

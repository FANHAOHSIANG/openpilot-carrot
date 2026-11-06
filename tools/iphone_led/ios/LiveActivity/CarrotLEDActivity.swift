import ActivityKit
import SwiftUI
import WidgetKit

@main
struct CarrotLEDWidgets: WidgetBundle {
    var body: some Widget { CarrotLEDActivity() }
}

struct CarrotLEDActivity: Widget {
    var body: some WidgetConfiguration {
        ActivityConfiguration(for: LEDActivityAttributes.self) { context in
            VStack(alignment: .leading, spacing: 6) {
                Label(context.attributes.title, systemImage: "car.side.fill").font(.headline)
                Text(status(context)).font(.subheadline)
                Text(context.state.screenConnected ? "屏幕：最近回報藍牙已連線" : "屏幕：藍牙未連線")
                    .font(.caption)
                HStack {
                    Text("最後車況")
                    if context.state.sampledAt > Date(timeIntervalSince1970: 0) {
                        Text(context.state.sampledAt, style: .time)
                    } else { Text("尚無有效資料") }
                }.font(.caption)
                Text("連線狀態非即時保證；點此回 App 檢查").font(.caption2)
            }.padding().activityBackgroundTint(Color.black).activitySystemActionForegroundColor(.white)
                .foregroundStyle(.white)
        } dynamicIsland: { context in
            DynamicIsland {
                DynamicIslandExpandedRegion(.leading) { Image(systemName: "car.side.fill") }
                DynamicIslandExpandedRegion(.trailing) { Text("Carrot LED") }
                DynamicIslandExpandedRegion(.bottom) { Text(status(context)).font(.caption) }
            } compactLeading: {
                Image(systemName: "car.side.fill")
            } compactTrailing: {
                Image(systemName: context.isStale || !context.state.fresh ? "exclamationmark.triangle" : "antenna.radiowaves.left.and.right")
            } minimal: {
                Image(systemName: context.isStale || !context.state.fresh ? "exclamationmark.triangle" : "car.side.fill")
            }
        }
    }

    private func status(_ context: ActivityViewContext<LEDActivityAttributes>) -> String {
        if context.isStale || !context.state.fresh { return "資料已過期，請回 App 確認" }
        if !context.state.automatic { return "自動顯示已暫停" }
        if !context.state.screenConnected { return "已收到車況，屏幕未連線" }
        return "最近收到車況；背景連動測試中"
    }
}

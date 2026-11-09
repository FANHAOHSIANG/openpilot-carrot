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
                Text("最近送出：" + displayText(context)).font(.title2.bold())
                    .lineLimit(2).minimumScaleFactor(0.7)
                Text(status(context)).font(.subheadline)
                tripText(context).font(.caption)
                Text(context.state.screenConnected ? "屏幕：最近回報藍牙已連線" : "屏幕：藍牙未連線")
                    .font(.caption)
                HStack {
                    Text("最後車況")
                    if context.state.sampledAt > Date(timeIntervalSince1970: 0) {
                        Text(context.state.sampledAt, style: .time)
                    } else { Text("尚無有效資料") }
                }.font(.caption)
                Text("內容為 App 最近送出，非屏幕回讀；點此回 App").font(.caption2)
            }.padding().activityBackgroundTint(Color.black).activitySystemActionForegroundColor(.white)
                .foregroundStyle(.white)
        } dynamicIsland: { context in
            DynamicIsland {
                DynamicIslandExpandedRegion(.leading) { Image(systemName: "car.side.fill") }
                DynamicIslandExpandedRegion(.trailing) { Text("Carrot LED") }
                DynamicIslandExpandedRegion(.bottom) {
                    VStack(spacing: 4) {
                        Text(displayText(context)).font(.title2.bold()).lineLimit(2).minimumScaleFactor(0.7)
                        Text(status(context)).font(.caption)
                        tripText(context).font(.caption2)
                        Text("App 最近送出內容，非屏幕回讀").font(.caption2).foregroundStyle(.secondary)
                    }
                }
            } compactLeading: {
                Image(systemName: "car.side.fill")
            } compactTrailing: {
                Text(compactText(context)).font(.caption.bold())
                    .lineLimit(1).truncationMode(.tail).frame(maxWidth: 85)
            } minimal: {
                Image(systemName: context.isStale || !context.state.fresh ? "exclamationmark.triangle" : "car.side.fill")
            }
        }
    }

    @ViewBuilder private func tripText(_ context: ActivityViewContext<LEDActivityAttributes>) -> some View {
        if let km = context.state.tripDistanceKm {
            if !context.isStale, let at = context.state.gpsSampledAt, Date().timeIntervalSince(at) < 15,
               let speed = context.state.gpsSpeedKmh {
                Text(String(format: "手機 GPS %.0f km/h · 本次約 %.2f km", speed, km))
            } else { Text(String(format: "手機 GPS 暫無新定位 · 本次約 %.2f km", km)) }
        }
    }

    private func displayText(_ context: ActivityViewContext<LEDActivityAttributes>) -> String {
        guard let text = context.state.displayText, !text.isEmpty else { return "尚無顯示資訊" }
        return text
    }

    private func compactText(_ context: ActivityViewContext<LEDActivityAttributes>) -> String {
        if !context.state.screenConnected { return "屏幕斷線" }
        if context.isStale { return "更新逾時" }
        if !context.state.fresh { return "車況中斷" }
        let text = displayText(context)
        return text.count > 5 ? String(text.prefix(5)) + "…" : text
    }

    private func status(_ context: ActivityViewContext<LEDActivityAttributes>) -> String {
        if context.isStale { return "動態島更新逾時；以下為最後回報，請回 App 確認" }
        if !context.state.fresh { return "C4 車況資料中斷，請回 App 確認" }
        if !context.state.automatic { return "自動顯示已暫停" }
        if !context.state.screenConnected { return "已收到車況，屏幕未連線" }
        return "車況連動中 · App 最近送出內容"
    }
}

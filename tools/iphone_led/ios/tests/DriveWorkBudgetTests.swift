import Foundation
@main struct DriveWorkBudgetTests {
    static var checks = 0
    static func check(_ value: Bool, _ message: String) { precondition(value, message); checks += 1 }
    static func main() {
        var budget = DriveWorkBudget(now:100)
        let progress = Progress(totalUnitCount:0)
        budget.reportProgress(progress)
        check(budget.samples == 0 && budget.elapsedMinutes(now:100) == 0,"no invented samples or elapsed time")
        check(progress.isIndeterminate && !progress.isFinished,"unknown stream total is not complete")
        for _ in 0..<50 { budget.received(now:100.2) }
        check(budget.samples == 1,"duplicate callback cannot inflate progress")
        budget.received(now:99); budget.received(now:Double.nan)
        check(budget.samples == 1,"bad clock ignored")
        check(budget.end(now:400.1) == nil,"reconnect grace")
        check(budget.end(now:400.3) == .disconnected,"missing samples end task")
        budget.received(now:401)
        check(budget.samples == 1 && budget.end(now:401) == .disconnected,"late response cannot revive disconnected task")
        check(budget.end(now:99) == .invalidClock && budget.end(now:.nan) == .invalidClock,"bad clock ends session")
        budget = DriveWorkBudget(now:0)
        // Virtual-time replay: valid 5 Hz data for 24 hours, including the old
        // 60-minute boundary. This is not a physical iOS background-runtime test.
        for i in 0...432000 {
            let now = Double(i)/5
            budget.received(now:now)
            check(budget.end(now:now) == nil,"valid stream never ends because of session age")
            if i % 18000 == 0 {
                budget.reportProgress(progress)
                check(progress.completedUnitCount == Int64(i+1),"actual processed sample count")
                check(progress.isIndeterminate && !progress.isFinished,"hour boundary never completes the stream")
            }
        }
        check(budget.samples == 432001,"24-hour replay processed all actual samples")
        check(budget.elapsedMinutes(now:86400) == 1440,"elapsed time counts up beyond one hour")
        check(budget.end(now:86699.9) == nil,"late-session reconnect grace")
        check(budget.end(now:86700) == .disconnected,"late-session missing data still ends task")
        budget.received(now:86700)
        check(budget.samples == 432001,"no sample accepts itself after disconnect deadline")
        // Live bridge heartbeats never invent carState or refresh its age.
        var heartbeat = DriveWorkBudget(now:0)
        heartbeat.received(now:0)
        check(heartbeat.hasFreshVehicle(now:0.1),"a real vehicle sample is fresh")
        for i in 1...720 { // one hour of decoded valid:false replies, every five seconds
            let now = Double(i)*5
            heartbeat.receivedResponse(hasVehicle:false,now:now)
            check(heartbeat.end(now:now) == nil,"live bridge can wait for carState beyond one hour")
            check(heartbeat.hasRecentResponse(now:now) && !heartbeat.hasFreshVehicle(now:now),"heartbeat is not vehicle freshness")
            check(heartbeat.samples == 1 && heartbeat.lastSample == 0,"heartbeat never creates or renews vehicle samples")
        }
        heartbeat.reportProgress(progress)
        check(progress.completedUnitCount == 721 && progress.isIndeterminate && !progress.isFinished,"progress counts actual decoded bridge replies")
        check(heartbeat.end(now:3899.9) == nil && heartbeat.end(now:3900) == .disconnected,"five minutes without any response ends the session")
        heartbeat.receivedResponse(hasVehicle:false,now:3900)
        check(heartbeat.responses == 721,"late heartbeat cannot revive an ended session")
        var recovery = DriveWorkBudget(now:0)
        recovery.received(now:0)
        check(recovery.end(now:31) == nil && !recovery.hasFreshVehicle(now:31),"thirty-second interruption keeps retrying with stale data hidden")
        recovery.received(now:299)
        check(recovery.samples == 2 && recovery.hasFreshVehicle(now:299),"real carState resumes before grace expires")
        recovery.receivedResponse(hasVehicle:false,now:299.2)
        check(!recovery.hasFreshVehicle(now:299.2),"invalid response immediately marks vehicle unavailable")
        recovery.received(now:299.4)
        check(recovery.samples == 3 && recovery.hasFreshVehicle(now:299.4),"valid carState recovers after heartbeat-only period")
        var waiting = DriveWorkBudget(now:0)
        check(waiting.end(now:31) == nil && waiting.end(now:300) == .disconnected,"failed polling alone never extends the five-minute grace")
        waiting.reportProgress(progress)
        check(progress.completedUnitCount == 0,"timers and missing responses cannot fabricate progress")
        for _ in 0..<50 { recovery.receivedResponse(hasVehicle:false,now:299.6) }
        check(recovery.responses == 5,"duplicate heartbeat callbacks do not inflate response counts")
        var lease = PollLease()
        let old = lease.begin(now:0)!
        check(lease.begin(now:0.2) == nil,"one network request in flight")
        let replacement = lease.begin(now:2)!
        check(replacement != old,"stalled request replaced")
        lease.finish(old)
        check(lease.ticket == replacement,"late callback cannot release new request")
        lease.finish(replacement)
        check(lease.ticket == nil,"current completion releases lease")
        let suspended = lease.begin(now:3)!
        lease.reset()
        let foreground = lease.begin(now:3.1)!
        lease.finish(suspended)
        check(lease.ticket == foreground,"foreground recovery ignores pre-suspension completion")
        print("\(checks) session, bridge heartbeat isolation, Foundation progress and polling recovery checks passed")
    }
}

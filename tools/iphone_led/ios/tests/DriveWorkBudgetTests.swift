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
        check(budget.end(now:130.1) == nil,"reconnect grace")
        check(budget.end(now:130.3) == .disconnected,"missing samples end task")
        budget.received(now:131)
        check(budget.samples == 1 && budget.end(now:131) == .disconnected,"late response cannot revive disconnected task")
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
        check(budget.end(now:86429.9) == nil,"late-session reconnect grace")
        check(budget.end(now:86430) == .disconnected,"late-session missing data still ends task")
        budget.received(now:86430)
        check(budget.samples == 432001,"no sample accepts itself after disconnect deadline")
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
        print("\(checks) no-duration-limit session, Foundation progress and polling recovery checks passed")
    }
}

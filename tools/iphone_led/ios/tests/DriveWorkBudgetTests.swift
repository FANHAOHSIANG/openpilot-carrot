import Foundation
@main struct DriveWorkBudgetTests {
    static var checks = 0
    static func check(_ value: Bool, _ message: String) { precondition(value, message); checks += 1 }
    static func main() {
        var budget = DriveWorkBudget(now:100)
        check(budget.samples == 0 && budget.remaining(now:100) == 3600,"no invented samples")
        for _ in 0..<50 { budget.received(now:100.2) }
        check(budget.samples == 1,"duplicate callback cannot inflate progress")
        budget.received(now:99); budget.received(now:Double.nan)
        check(budget.samples == 1,"bad clock ignored")
        check(budget.end(now:130.1) == nil,"reconnect grace")
        check(budget.end(now:130.3) == .disconnected,"missing samples end task")
        budget.received(now:131)
        check(budget.samples == 1 && budget.end(now:131) == .disconnected,"late response cannot revive expired task")
        budget = DriveWorkBudget(now:0)
        for i in 0..<18000 {
            let now = Double(i)/5
            budget.received(now:now)
            check(budget.end(now:now) == nil,"valid sample stream continues")
        }
        check(budget.samples == 18000,"progress is real 5 Hz samples")
        check(budget.end(now:3600) == .duration,"hard one-hour end")
        budget.received(now:3601)
        check(budget.samples == 18000,"no work after horizon")
        check(budget.remaining(now:3601) == 0,"nonnegative countdown")
        var short = DriveWorkBudget(now:10,duration:60)
        short.received(now:39); short.received(now:68)
        check(short.end(now:69) == nil && short.end(now:70) == .duration,"duration and data-loss clocks independent")
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
        print("\(checks) bounded drive session and polling recovery checks passed")
    }
}

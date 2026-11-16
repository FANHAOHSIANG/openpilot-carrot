# Carrot DEC upstream synchronization

The `Sync official carrot-wip into Carrot DEC` GitHub Actions workflow runs
hourly at minute 23, or manually from the Actions page. It lives on this
repository's default `carrot-wip` branch because scheduled workflows only run
from the default branch. The default branch's vehicle code is not changed by
this workflow.

Source: `ajouatom/openpilot`, branch `carrot-wip`.
Destination: `FANHAOHSIANG/openpilot-carrot`, branch `carrotpilot-dec`.

The workflow merges into a temporary checkout. It preserves the integrated
DEC/parked-switch commit, refuses automatic conflict resolution, protects the
downstream test files, runs the 49 focused DEC/parked/configuration tests and
checks the integrated Python files' syntax. Only a passing candidate is pushed.
If someone changes the destination while validation runs, publication stops
and the next scheduled run starts again. No force push is used.

Conflicts and failed checks appear as failed Actions runs; the installed
branch keeps its previous commit until the problem is resolved. These CPU
checks do not establish C4 build compatibility or road behavior. Official
changes may therefore require further manual adaptation and device testing.

C4 installations keep the `carrotpilot-dec` branch and their normal updater;
this workflow publishes repository updates and does not itself install or
restart a vehicle. Installation URL remains
`https://installer.comma.ai/FANHAOHSIANG/carrotpilot-dec`.

GitHub can delay scheduled runs or disable them after 60 days without repository
activity. Check the workflow page if updates stop; it also offers Run workflow.

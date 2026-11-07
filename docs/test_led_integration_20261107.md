# LED-only integration into long-term Test

This change is a source-code integration candidate, not a vehicle release or device installation. Current validation results are recorded in its pull request and checks, not inferred from historical README claims.

## Pinned inputs

- Target before integration: `test/carrot-wip-upstream-20261104` at `946de3ac2166267cd81a4e74fe311227ca474e72`.
- LED source: `carrot-wip` at `b9c16ec9808ef7b5e1f3bd675ae08ec7e3b9da31`.
- Backup: `backup/test-before-led-20261107-946de3ac`.
- Scoped import commit: `1bb4123641705930d8bf567436c5df99746deb79`.

## Scope and provenance

The import reuses the exact `tools/iphone_led` Git subtree, the production read-only bridge, manager registration and its spawn regression, and the two companion build workflows from the source SHA. The import commit lists the original LED source commits. Those original commits and the formal branch remain unchanged. The entire formal branch is NOT merged and must not be treated as an ancestor of Test merely because LED was transferred.

The initial source commit also included navigation ownership changes and another source commit included container-registry naming changes. Those unrelated changes are deliberately excluded. In particular this integration does not modify cereal schema, CarrotMan, navd, Google Maps, modeld/locationd, Jetlink/N16, HUD rendering, Hyundai CAN FD, Panda safety, FCA/AEB, or firmware. Existing Test content outside the scoped paths is retained.

The transferred top-level LED README describes its earlier integration into the formal branch. Its navigation changes and historical test counts are NOT a claim that those changes or tests were performed by this Test integration. Use this document and the PR for this integration's scope.

## Complete LED components

- iPhone app, background-session/Live Activity/Dynamic Island sources and resources.
- Android app, foreground-service and local regression/build scripts.
- Mac companion and offline tests.
- `openpilot/selfdrive/carrot/iphone_led_bridge.py` and matching standalone copies.
- Token/device/onroad-gated manager registration and admission/crash-restart coverage.

The bridge subscribes to carState and exposes authorized read-only local-network data; it does not publish CAN/control messages. No token, pairing, process launch or device configuration is performed by this integration.

## Validation gates and limits

The focused workflow checks exact source Git objects and a LED-only import scope, verifies that removing the LED registration leaves the previous process configuration unchanged, and runs mocked desktop LED tests, bridge authorization/staleness tests, manager spawn/admission regressions and syntax checks. Companion workflows build Android and the iOS Simulator app/extension, including the Swift alert-policy tests.

At candidate creation these new workflow results are pending. The source iPhone simulator run was cancelled with no steps, not passed. No successful full build or vehicle validation is asserted. Required checks and branch protections must be respected; unexplained new regressions must block promotion. Physical BLE animation, background behavior and Dynamic Island presentation require separate device evidence. Merging GitHub source does not install it on C4, Mac, iPhone, Android or the vehicle.

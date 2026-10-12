# Carrot wip Map HUD (CPdazi 7.7)

This experimental branch starts from official carrot-wip commit
`5e187ab9da726c524ca51aebacc6120802480415`. It adds a display-only bridge from
CPdazi's existing JPEG projection into `carrotNaviMedia` / `render:map_main`.
The existing JetLink navigation child transports the media to the Mac HUD.
No Android APK modification or new JetLink protocol is required for this first version.

## Setup

1. Install branch `carrot-wip-map-hud` from `FANHAOHSIANG/openpilot-carrot`.
2. Put the Android projection device and comma on the same LAN. Connect CPdazi's
   Navi v2 to the comma (TCP 7714), then start Amap projection using the app's
   normal activation and permissions. The app's projection HTTP port is separate
   from 7714: use the exact URL shown by its projection page, not an assumed port.
3. Open `http://<comma-IP>:7000/map-hud` or **Carrot Web → Tools → Map HUD**.
4. Enter the app's projection base URL including its port (or its `/frame` URL),
   enable the relay and save. Default 2 FPS, selectable 1–5 FPS.
5. Check for **Streaming** and a rising frame count. Keep the existing JetLink
   HUD/map display enabled; use its regular map view, not only the legacy
   navigation debug/3D-guide panel. A map need not contain separate 3D junction imagery.

The settings page explains the source URL, refresh limit, stale-frame behavior
and native-map priority in Chinese, English and Korean. Settings persist outside
the checkout under `/data/carrot/state/map_hud.json` and apply without reboot.
The bridge runs within carrot_navi but in its own network/decode thread; the
single existing Cereal publisher sends the resulting media. The driving-model,
control and navigation speed-selection code is unchanged.

## Display limits

- JPEG is resized with preserved aspect ratio to fit 800 × 480; each frame is
  capped at 128 KiB. Actual device timing and inference coexistence need parked testing.
- Only private LAN numeric-IP HTTP URLs with an explicit port are accepted.
  Redirects/proxies are disabled. Input is capped at 2 MiB, decode at 8 MP.
- No frame is published twice for an unchanged source sequence/content. After
  three seconds without a new frame, the bridge clears its map. Source failures
  clear the map after the same deadline. Disabling/changing the URL clears its map.
- A live Navi v2 session is required; images are tied to that session. A frame
  completing after a session change is dropped. A fresh native map is preferred;
  bridge clears never erase native media.
- In CPdazi 7.7 route summaries can be present while `polyline` is empty. This
  bridge does not invent coordinates, road limits, lane data or junction pictures.
- Navi v2 debug status now shows received turn/distance information and missing
  coordinates instead of claiming to wait for legacy POST while v2 data is fresh.

## Verification and troubleshooting

Before driving, use a parked vehicle. Confirm the projection URL displays a
fresh JPEG in a browser, Navi v2 is connected, relay frames advance and the
physical HUD shows the map. Then observe model cadence/drop counts and CPU load.
Desktop tests do not establish live HUD, Wi-Fi latency or model-performance results.

`waiting_navigation`: connect CPdazi Navi v2 to this comma.
`source_error`: check source URL/port, projection activation, LAN and app permissions.
`stalled`: projection frame sequence/content stopped updating.
`native_map_or_session_changed`: native media is active or the navigation session changed.
`not_running`: check carrot_navi is running; the relay does not run with `--no-cereal`.

Turning the relay off restores the regular upstream media path. This branch does
not automatically track future upstream commits; synchronize deliberately and
repeat focused regression checks.

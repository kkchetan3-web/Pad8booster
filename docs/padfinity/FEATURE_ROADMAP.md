# FEATURE_ROADMAP.md

Legend: ✅ done & verified · 🟡 written, not compiled/verified · ⛔ not started · 🔒 needs device

| Phase | Deliverable | Status |
| --- | --- | --- |
| 1 | Device research & capability matrix | ✅ `DEVICE_RESEARCH.md`, `COMPATIBILITY.md` |
| 2 | Architecture & permission model | ✅ `ARCHITECTURE.md`, `PERMISSIONS.md`, `SECURITY.md` |
| 3 | Window engine (geometry, z-order, snap, tile, workspaces, persistence) | ✅ compiled + 135 checks |
| 3 | Taskbar rules, insights rules, recommender ranking | ✅ compiled + tested |
| 3 | Compose desktop shell, window chrome, taskbar, launcher | 🟡 written |
| 4 | **MVP:** desktop + windows + workspaces + taskbar + launcher + insights + discovery + persistence | 🟡 engine ✅ / UI 🟡 |
| 4 | Settings & configuration persistence in the app | 🟡 |
| 4 | Permission/capability surfaces | 🟡 |
| 5 | Shizuku gateway (freeform launch, density, settings, buckets) | 🟡 engine-level design ✅, integration 🟡 |
| 5 | Keyboard shortcuts (in-app), pointer affordances | ⛔ |
| 5 | Automation profiles (keyboard-connected, workspace switch) | ⛔ |
| 5 | Desktop-style file browser (SAF) | ⛔ |
| 5 | Themes editor & per-workspace accents | 🟡 data model ✅ |
| 6 | Real-device testing (D1–D12) | 🔒 blocked: no device |
| 6 | APK build & signing | 🔒 blocked: no Android SDK in build env |
| 7 | Release notes, setup guide, permission guide | ✅ docs; APK ❌ |

## Ordered next work (highest value first)

1. **Compile the app module** on a machine with the Android SDK; fix the UI layer compile errors. Nothing else matters until the UI has been through a compiler.
2. **D6/D7 device tests** — workspace switching and relaunch restore are the two behaviours that make or break the "desktop" feel.
3. **Drag performance pass** — measure with Macrobenchmark; target < 4 ms frame work during drag.
4. **Shizuku gateway** — freeform launch with graceful fallback, plus density/settings/bucket actions with read-back verification.
5. **Automation v1** — three triggers only: keyboard connected, workspace switch, time-of-day. Resist scope creep.
6. **File browser** — SAF-based, dual pane, no `MANAGE_EXTERNAL_STORAGE`.
7. **Themes** — accent per workspace, wallpaper picker, taskbar style variants.

## Explicit non-goals (will not be built)

Window management of *other* apps' windows; system-bar replacement; kernel tuning; RAM cleaning;
task killing; telemetry; cloud sync; ad-supported surfaces.

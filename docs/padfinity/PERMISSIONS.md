# PERMISSIONS.md — what PADFINITY asks for, why, and what happens if you refuse

Principle: **every permission is optional and degrading**. The app's core (desktop, windows,
workspaces, taskbar, launcher of apps you pick, insights from public APIs) needs **no dangerous
permission at all**. Refusing an optional grant removes one feature, never the app.

## Tier 0 — none (default install)

| Data / action | API | Permission needed |
| --- | --- | --- |
| RAM totals and availability | `ActivityManager.MemoryInfo` | none |
| Storage totals/free | `StatFs` on app-visible dirs | none |
| Battery level, temperature, charging | `BatteryManager`, `ACTION_BATTERY_CHANGED` | none |
| Thermal status | `PowerManager.getCurrentThermalStatus()` | none |
| Refresh rate (current) | `Display.refreshRate` | none |
| Launch apps you choose | `Intent` | none |
| Persist desktop layout | app-private storage | none |

This is the whole MVP. If a feature needs more, the UI says so explicitly.

## Tier 1 — user-granted, revocable

| Permission | Feature it unlocks | Request timing | If denied |
| --- | --- | --- | --- |
| `QUERY_ALL_PACKAGES` **or** `<queries>` manifest entries | Full app library in launcher/search | install-time, but prefer scoping `<queries>` | Launcher shows only declared/known apps |
| `PACKAGE_USAGE_STATS` (Settings → Special access) | Per-app storage/usage insights, recents | only when you open Insights | Insights degrade to system-wide metrics |
| `SYSTEM_ALERT_WINDOW` | Edge panel / floating HUD overlay | when you enable the panel | Panel feature hidden |
| `NotificationListenerService` | Optional notification integration | when you enable it | No notification features; everything else works |
| `POST_NOTIFICATIONS` | Progress/status notifications | first foreground task | Silent operation |
| Accessibility service | Global key remapping, gesture macros | when you enable Input tools | Input remapping unavailable |

**Accessibility is a high-trust permission.** It can observe screen content. PADFINITY uses it
only for input events, never reads screen text, and the setting is off by default with an
explanation shown before the system dialog.

## Tier 2 — Shizuku / ADB (no root)

Shizuku runs a process with **shell** (uid 2000) identity, which is far more privileged than a
normal app. Granting an app access to it is a real trust decision — treat it like root.

| Operation | Command executed | Reversible? |
| --- | --- | --- |
| Freeform launch | `am start --windowingMode 5 -n pkg/activity` | yes (just launch again) |
| Display density | `wm density <n>` / `wm density reset` | yes |
| Animation scales | `settings put global …` | yes (journalled) |
| Refresh rate cap | `settings put system peak_refresh_rate` | yes, if the build honours it |
| Standby bucket | `am set-standby-bucket pkg <bucket>` | yes |
| Remove a package | `pm uninstall --user 0 pkg` | yes — `cmd package install-existing` |
| Doze whitelist | `dumpsys deviceidle whitelist [+pkg]` | yes (`-pkg`) |

PADFINITY never runs a shell command it has not first read back to verify, and every write is
recorded in a journal so it can be undone (same model as the host-side Pad8Booster toolkit).

## Tier 3 — root

**Not implemented, and not planned.** The bootloader path on HyperOS 3 is quota-gated, forfeits
OTA updates, and breaks Play Integrity. Any feature that would need root is either dropped or
implemented at Shizuku level instead.

## What PADFINITY will never request

- `READ_SMS`, `READ_CALL_LOG`, `READ_CONTACTS`
- `ACCESS_FINE_LOCATION` (no location feature exists)
- `MANAGE_EXTERNAL_STORAGE` ("all files access" — scoped storage + SAF is sufficient)
- `REQUEST_INSTALL_PACKAGES`, `SYSTEM_ALERT_WINDOW` for ads, `BIND_DEVICE_ADMIN`
- Silent `MediaProjection` (impossible anyway — consent is per-session by design)

## Manifest hygiene

- `android:allowBackup="false"` — desktop layout lives locally; no cloud copy by accident.
- `android:usesCleartextTraffic="false"`.
- No `INTERNET` permission in the MVP. The app makes **no network calls**; the recommender
  catalogue ships in the APK so recommendations work offline and cannot phone home.
- `<queries>` block lists only packages PADFINITY needs to resolve, instead of
  `QUERY_ALL_PACKAGES`.

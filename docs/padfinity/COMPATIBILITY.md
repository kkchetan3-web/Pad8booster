# COMPATIBILITY.md — PADFINITY feature matrix

Every feature in PADFINITY carries exactly one status. Nothing is marked **Tested** until it has
run on a physical Xiaomi Pad 8 — and as of this commit, **no row is Tested**, because the build
environment had no device attached. That honesty is a product feature, not a disclaimer.

| Status | Meaning |
| --- | --- |
| **Confirmed** | Platform/vendor behaviour documented; implementation is straightforward |
| **Tested** | Verified by us on a physical Pad 8 — currently **none** |
| **Tested³** | Verified third-party on a physical Pad 8, cited |
| **Compatible** | Should work; not yet exercised on hardware |
| **Restricted** | Requires an explicit user-granted permission |
| **Advanced** | Requires Shizuku/ADB (no root) |
| **Experimental** | Unverified; may break on firmware updates |
| **Unavailable** | Not possible for a third-party app on this device |

## MVP capabilities

| # | Feature | Status | Access | Notes |
| --- | --- | --- | --- | --- |
| 1 | Desktop shell (wallpaper, grid, free placement) | Confirmed | none | Engine verified by tests |
| 2 | Internal window manager (open/close/focus/z-order) | Confirmed | none | 135 engine checks pass |
| 3 | Drag + resize with min-size and off-screen clamps | Confirmed | none | Title bar always reachable |
| 4 | Minimise / maximise / restore with geometry memory | Confirmed | none | Unit-tested |
| 5 | Edge & quadrant snapping with custom split ratios | Confirmed | none | Ratio clamped 0.2–0.8 |
| 6 | Tiling: 2/3 columns, 2×2 grid, main+stack, cascade | Confirmed | none | Unit-tested |
| 7 | Alt-Tab style MRU switcher | Confirmed | none | MRU order unit-tested |
| 8 | Multi-workspace with per-workspace windows | Confirmed | none | Independent WindowManager per workspace |
| 9 | Persistent desktop (windows, geometry, meta) | Confirmed | internal storage | Codec round-trip tested |
| 10 | Taskbar (pinned / running / recents, overflow) | Confirmed | none | Rules unit-tested |
| 11 | App launcher (search, categories, recents) | Compatible | `QUERY_ALL_PACKAGES` or `<queries>` | Prefer `<queries>` to avoid broad permission |
| 12 | Launch external apps | Confirmed | none | Standard `Intent` |
| 13 | Device insights (RAM/storage/battery/thermal/refresh) | Confirmed | none | Public APIs only |
| 14 | Rule-based recommendations | Confirmed | none | Anti-placebo terms asserted in tests |
| 15 | App discovery / ranking engine | Confirmed | none | Weighted ranking unit-tested |
| 16 | Customisation centre (guided settings) | Compatible | none | Deep links where no writable API |

## Advanced capabilities

| # | Feature | Status | Access | Notes |
| --- | --- | --- | --- | --- |
| 17 | Launch other apps in **real freeform windows** | Advanced | Shizuku | `am start --windowingMode 5`; **Tested³** on Pad 8 |
| 18 | Control freeform geometry | Unavailable | — | Build rejects bounds (Tested³) |
| 19 | Change display density | Advanced | Shizuku / ADB | `wm density`; reversible; Pad8Booster does it host-side today |
| 20 | Animation scale tuning | Advanced | Shizuku / ADB | `settings put global …`; verify read-back |
| 21 | Refresh-rate cap/floor | Advanced | Shizuku / ADB | Build may ignore keys — probe first |
| 22 | App Standby Bucket assignment | Advanced | Shizuku | `am set-standby-bucket` |
| 23 | Remove/re-enable other apps | Advanced | Shizuku | `pm uninstall --user 0` + `install-existing` |
| 24 | Doze whitelist management | Advanced | Shizuku | `dumpsys deviceidle whitelist` |
| 25 | Global key remapping | Restricted | Accessibility | Privacy-sensitive; opt-in only |
| 26 | Edge panel overlay | Restricted | `SYSTEM_ALERT_WINDOW` | User grant |
| 27 | App usage statistics | Restricted | `PACKAGE_USAGE_STATS` | Explicit, revocable |
| 28 | Notification actions | Restricted | `NotificationListenerService` | Explicit grant |
| 29 | Screen recording | Restricted | `MediaProjection` | Per-session consent |
| 30 | Automation triggers | Restricted / Advanced | varies | Event-driven only, never polling |

## Explicitly out of scope

| Capability | Why |
| --- | --- |
| Managing other apps' windows directly | No third-party API; would require system signature |
| Redesigning the system status bar / shade | No vendor API without root |
| Kernel, governor or thermal tuning | Requires root; bootloader is quota-gated |
| Custom ROM / kernel flashing | Forfeits OTA, trips Play Integrity |
| Silently reading other apps' data | Scoped storage; also unethical |
| RAM "cleaning" / task killing | Placebo at best, counter-productive at worst |
| Forcing per-app resolution | Not supported on this platform |

## How to promote a row to **Tested**

1. `python -m pad8booster probe` to record firmware.
2. Exercise the feature on the physical tablet (landscape *and* portrait).
3. Record firmware, result, and any workaround in `TESTING.md`.
4. Update the row's status and cite the test row number.

Do not mark a row Tested because it compiled, ran in an emulator, or "should work".

# DEVICE_RESEARCH.md — Xiaomi Pad 8 environment & capability study

**Status:** living document · last verified 2026-11-06
**Target unit:** Xiaomi Pad 8, 12 GB LPDDR5T / 256 GB UFS 4.1, India region
**Product:** PADFINITY

> **Verify your own unit before trusting anything here.** Run
> `python -m pad8booster probe` (this repo) or
> `adb shell getprop ro.product.model; adb shell getprop ro.soc.model; adb shell getprop ro.build.version.sdk`
> and compare with §1. Regional firmware differs; a feature confirmed on Global firmware is
> not automatically confirmed on Indian firmware, and vice versa.

---

## 1. Verified hardware / software facts

| Property | Value | Source confidence |
| --- | --- | --- |
| SoC | Qualcomm **Snapdragon 8s Gen 4** (`SM8735`), 4 nm | Multiple independent spec databases + launch coverage |
| CPU | 1× Cortex-X4 @ 3.21 GHz, 3× A720 @ 3.0 GHz, 2× A720 @ 2.8 GHz, 2× A720 @ 2.02 GHz | ✓ |
| GPU | **Adreno 825**, ~1.15 GHz | ✓ |
| RAM | 8 GB LPDDR5X / **12 GB LPDDR5T** (4800 MHz) | ✓ |
| Storage | 128 GB **UFS 3.1** / 256·512 GB **UFS 4.1** — no microSD | ✓ (the 128 GB SKU is measurably slower: plan around it) |
| Display | 11.2" IPS **LCD**, 3200×2136, 3:2, 345 ppi, 144 Hz adaptive, 800 nits peak | ✓ |
| OS | **HyperOS 3** on **Android 16** → `Build.VERSION.SDK_INT == 36` | ✓ |
| Update policy | Xiaomi quotes ~4 yrs OS + 6 yrs security patches | Vendor claim, not independently audited |
| Charging | 45 W (Pad 8) / 67 W (Pro); 67 W charger bundled in India | Region-dependent — verify in box |
| Connectivity | Wi-Fi 7, BT 5.4 (LHDC 5), USB-C 3.2 Gen 1 (5 Gbps), IR blaster | ✓ |
| Absent | microSD, headphone jack, cellular/5G, OLED, wireless charging | ✓ |
| Security | Side fingerprint; Play Integrity enforced for banking/Wallet | ✓ |

### Display consequences for a desktop UI

- **LCD, not OLED**: dark themes save *zero* power. Any "black theme = battery" claim is false
  on this panel. Design dark mode for comfort only.
- **3:2 at 3.2K**: 3200×2136 px. At 320 dpi that is ~1600×1068 dp — a genuinely desktop-class
  canvas. PADFINITY's engine is unit-tested against exactly this rect.
- **144 Hz + 360 Hz touch sampling**: window drag/resize must be frame-paced; recomposing the
  whole desktop per pointer event is the main jank risk.

---

## 2. Platform realities that shape the product

### 2.1 Root is not a design option

HyperOS 3 gates bootloader unlocking behind daily quotas, account-age/activity gates, and
one-device-per-account-per-year limits; unlocked devices lose HyperOS OTA updates until relocked
and trip Play Integrity (breaking banking, Wallet, some DRM streaming). **PADFINITY therefore
targets zero-root operation.** Anything requiring root is documented and marked optional, never
required.

### 2.2 WebView / Compose / Compose-Material3 versions are not pinned by Xiaomi

HyperOS 3 ships Android 16 with its own WebView and system UI chrome. PADFINITY must not assume
Pixel behaviour for: gesture nav insets, predictive back, notification shade layout, status bar
height, or taskbar behaviour.

### 2.3 Real freeform windows — measured on this exact device

This is the single most important capability question for a "desktop" app, so it gets its own
table. A third-party developer measured these results **on a Xiaomi Pad 8 running HyperOS 3.0 /
Android 16** (the `SideBar` project):

| Approach | Result on Pad 8 | Notes |
| --- | --- | --- |
| `FEATURE_FREEFORM_WINDOW_MANAGEMENT` present | ✅ **present** | The device supports freeform |
| `ActivityOptions.setLaunchBounds()` (public API) | ❌ bounds only | Cannot select windowing mode |
| `ActivityOptions.setLaunchWindowingMode()` | ❌ blocked | Hidden API, denied to third-party apps |
| HyperOS "mini window" entry point | ❌ unreachable | Proprietary, no public contract |
| `am start --windowingMode 5` as **shell** | ✅ **works** | Task reports `mode=freeform` |
| Specifying freeform bounds as shell | ❌ not on this build | Window uses HyperOS default size/position |

**Conclusion for PADFINITY:**

- **Internal windows** (our own surfaces) are fully implementable — the engine in
  `android/engine` is the real thing, not a mock.
- **System-level floating windows** for *other* apps are achievable **only through a Shizuku
  (shell-identity) call**: `am start --windowingMode 5 -n <pkg>/<activity>`. Status:
  **Advanced**, requires Shizuku, cannot control geometry on this build.
- Never label an internal window as a system window. The UI distinguishes them
  ([`WindowKind.INTERNAL`](../android/engine/src/main/kotlin/dev/padfinity/engine/Window.kt) vs
  `SYSTEM_APP`).

### 2.4 Android 16 large-screen changes that help

- Platform-level enforcement of app-specified orientation, resizability and aspect-ratio
  constraints is **relaxed on displays with smallest width ≥ 600 dp** — the Pad 8 qualifies, so
  apps are less likely to refuse resizing in freeform.
- AOSP improved freeform/desktop windowing (task limits, internal-display support).
- Predictive back is stable; PADFINITY should opt in with a modern `OnBackPressedCallback`
  design rather than legacy `onBackPressed`.

### 2.5 Background execution

Android 16 restricts background work harder than earlier releases: foreground services need
declared types and justification, exact alarms are gated, and HyperOS adds its own killer
(battery saver + "private protection"). PADFINITY's automation must be **event-driven and
foreground-visible**, not a background poller.

---

## 3. Capability matrix

Status vocabulary (used identically in `COMPATIBILITY.md`):

| Status | Meaning |
| --- | --- |
| **Confirmed** | Officially documented platform/vendor behaviour |
| **Tested** | Verified by *us* on a physical Pad 8 — **currently zero rows carry this** |
| **Tested³** | Verified by a third party on a physical Pad 8, source cited |
| **Compatible** | API exists and should work on this device; not yet run here |
| **Restricted** | Needs a special permission the user must grant explicitly |
| **Advanced** | Needs Shizuku/ADB (no root) |
| **Experimental** | Unverified, may break across firmware updates |
| **Unavailable** | Not reachable by a third-party app on this device |

| Capability | Status | Requirements | Notes |
| --- | --- | --- | --- |
| Internal window manager (own surfaces) | **Confirmed** | none | Implemented + 135 engine checks |
| Custom taskbar / launcher UI | **Confirmed** | none | Ordinary Compose surface |
| Distinct home-screen replacement | **Compatible** | `HOME` intent filter, user default-launcher choice | Replacing `com.miui.home` also loses HyperOS dock + 1:9 split |
| Workspaces with independent layouts | **Confirmed** | none | Implemented in engine |
| Overlay panels (edge panel, HUD) | **Restricted** | `SYSTEM_ALERT_WINDOW` | User-visible "display over other apps" grant |
| Freeform launch of other apps | **Advanced** | Shizuku (shell identity) | `am start --windowingMode 5`; geometry not controllable |
| Control freeform window bounds | **Unavailable** | — | Not accepted by this build (Tested³) |
| Change display density (dpi) | **Advanced** | Shizuku/ADB (`wm density`) | Reversible; also available host-side via Pad8Booster |
| Cap/floor refresh rate | **Restricted** | `WRITE_SECURE_SETTINGS` via Shizuku, or OEM UI | Keys may be ignored by build; must verify read-back |
| Change animation scales | **Advanced** | Shizuku/ADB (`settings put global …`) | Perceived-speed win, reversible |
| App Standby Bucket control | **Advanced** | Shizuku (`am set-standby-bucket`) | Real background control |
| Remove/disable other apps | **Advanced** | Shizuku (`pm uninstall --user 0`) | Reversible via `install-existing` |
| Read RAM / storage / battery / thermal | **Confirmed** | none | `ActivityManager`, `StatFs`, `BatteryManager`, `PowerManager.getCurrentThermalStatus` |
| Battery *health* (cycle count) | **Restricted** | hidden API or vendor service | Often unavailable to third-party apps; do not fake it |
| Per-app storage usage | **Restricted** | `PACKAGE_USAGE_STATS` (user grant) | Needed for "largest apps" insights |
| App usage history | **Restricted** | `PACKAGE_USAGE_STATS` | Explicit, revocable grant |
| Notifications (read/act) | **Restricted** | `NotificationListenerService` | Explicit grant; sensitive |
| Global gesture/key remapping | **Restricted** | Accessibility service (or Shizuku) | Powerful and privacy-sensitive — opt-in only |
| Screen capture / recording | **Restricted** | `MediaProjection` consent dialog | Per-session consent, cannot be silent |
| Read other apps' internal storage | **Unavailable** | — | Scoped storage; SAF only |
| Modify system UI (status bar icons etc.) | **Unavailable** | — | No root, no vendor API |
| Kernel/governor tuning | **Unavailable** | root | Explicitly out of scope |
| Boot logo / custom kernel / ROM | **Unavailable** | unlocked bootloader | Quota-gated; not pursued |
| Overlay another app's window content | **Unavailable** | — | Android forbids cross-app surface composition |

---

## 4. What this means for the feature set

**Fully achievable today:** desktop shell, real internal window manager, taskbar, launcher,
workspaces with persistence, device insights (RAM/storage/battery/thermal/refresh), profile-based
automation with explicit triggers, app recommendations, density/settings management *via Shizuku*
when available.

**Achievable with limitations:** freeform launch of external apps (geometry uncontrolled),
"desktop-class" multitasking (bounded by Android app scaling quality), clipboard tooling
(Android 13+ restricts background clipboard reads), global keyboard shortcuts (only while
PADFINITY has focus or via Accessibility).

**Not achievable without privileged/root access:** managing *other* apps' windows, system-wide
status/notification bar redesign, kernel tuning, per-app forced resolution, true multi-user
virtual desktops.

---

## 5. Open questions to resolve on your unit

1. `ro.product.device` codename and `ro.build.version.incremental` for the Indian SKU.
2. Whether `settings get system peak_refresh_rate` is honoured on your build (read-back test).
3. Whether Shizuku stays alive under HyperOS battery management (may need exclusion).
4. USB-C → HDMI/DisplayPort Alt-Mode behaviour on your unit (reports vary by region).
5. Whether AVF / on-device Linux VM is enabled (`adb shell cmd virtmanager`).

Each answer updates this document — that is the point of it.

---

## 6. Sources

- Xiaomi Pad 8 specifications: [DeviceSpecifications](https://www.devicespecifications.com/en/model/ae326515), [GSMArena](https://www.gsmarena.com/), [Gizmochina launch coverage](https://www.gizmochina.com/2026/03/10/xiaomi-pad-8-india-launch-price-specs-snapdragon-8s-gen-4/)
- Freeform measurements on Pad 8 / HyperOS 3: [unauthorisedusername/SideBar](https://github.com/unauthorisedusername/SideBar)
- Android 16 large-screen behaviour & freeform: [Android Developers — large screens](https://developer.android.com/guide/topics/large-screens), [AOSP windowing](https://source.android.com/docs/core/display)
- Shizuku (Android 16 support, shell identity): [Shizuku docs](https://shizuku.rikka.app/), [RikkaApps/Shizuku](https://github.com/RikkaApps/Shizuku)
- HyperOS bootloader policy: [miuirom.org unlock rules](https://miuirom.org/updates/xiaomi-bootloader)
- Permissions & background limits: [Android background execution limits](https://developer.android.com/guide/components/activities/background-starts)

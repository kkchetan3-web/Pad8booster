# The Xiaomi Pad 8 Transformation Playbook

*Written 2026-11-06. Covers Xiaomi Pad 8 and Pad 8 Pro (both ship HyperOS 3 on Android 16).*

---

## 0. The honest multiplier

You asked how to make it "20× or 30× better." I'm not going to sell you that number in
benchmark terms, because it is not physically available: no software change makes a
Snapdragon 8s Gen 4 execute 30× more instructions, and any app claiming it is measuring
something other than your workload.

But there is a version of "30×" that is completely real, and it's the one worth chasing:

| Dimension | Realistic change | Why that ceiling exists |
| --- | --- | --- |
| App cold start | **10–25 % faster** | Launch latency is dominated by dexopt state, IO and broadcast storms — not CPU clocks |
| Perceived UI responsiveness | **~2× smoother** | Animation scale 1.0 → 0.5 halves every transition you look at; frame rate is already 144 Hz |
| Idle battery drain | **10–30 % less** | Removing telemetry/wakelock offenders and disabling always-on scans |
| Free RAM at idle | **+400–900 MB** | Killing ad SDKs and duplicate storefronts, not "cleaning" caches Android needs |
| Storage reclaimed | **1.5–4 GB** | Removing preloaded apps and their data |
| Multitasking surface | **Qualitative jump** | Workstation Mode + 1:9 split + dock + external display |
| *Jobs the device can do* | **~3 → ~12** | This is the real multiplier: terminal, code editor, Linux userland, local AI, second monitor, PC game streaming, stylus workstation… |

**The 30× is in capability surface, not clock speed.** A stock Pad 8 is a media tablet that
also does Office. A transformed one is a Linux development machine, a second monitor, a
local-AI box, a pen workstation, and a game-streaming client — while remaining a media
tablet. That's the transformation this document engineers, tier by tier, with the
measurement to prove each step.

Everything below is **no-root**. That is not caution for its own sake; it is the only
path that currently exists on this hardware (see §2).

---

## 1. Ground truth: what you actually own

Verified from multiple independent sources rather than a single spec sheet:

| Item | Value | Note |
| --- | --- | --- |
| SoC | Qualcomm **Snapdragon 8s Gen 4** (SM8735, 4 nm) | 1× Cortex-X4 @ 3.21 GHz, 3× A720 @ 3.0, 2× A720 @ 2.8, 2× A720 @ 2.02 |
| GPU | **Adreno 825** @ ~1.15 GHz | |
| RAM | 8 GB LPDDR5X or **12 GB LPDDR5T** | 12 GB is the SKU worth transforming |
| Storage | 128 GB (UFS 3.1) / 256 GB (UFS 4.1) | **No microSD slot** — plan storage deliberately |
| Display | 11.2" IPS **LCD**, 3200×2136 (3:2, 345 ppi), 144 Hz | Glossy or nano-texture (AG) variants |
| Battery | 9200 mAh, **45 W** charge (67 W charger bundled in India) | PD 3.0 / QC 3+/3.0, 22.5 W reverse |
| OS | **HyperOS 3 / Android 16 (API 36)** | Xiaomi quotes 4 yrs OS + 6 yrs security |
| Ports | USB-C 3.2 Gen 1 (5 Gbps), IR blaster | **No headphone jack**, no cellular/5G |
| Wireless | Wi-Fi 7, BT 5.4 (LHDC 5), quad speakers + Dolby Atmos | |
| Security | Side fingerprint | |

Two consequences people miss:

1. **It's an LCD.** Dark mode saves *zero* battery here (the backlight is constant). Every
   "AMOLED dark theme battery trick" article does not apply to you. Dark mode is a comfort
   choice, not a power strategy.
2. **No SD card and no cellular.** Storage discipline and offline media caching are not
   optional optimisations; they are structural constraints.

---

## 2. The privilege map — and why root is off the table

| Level | Access | What it unlocks | Verdict |
| --- | --- | --- | --- |
| **A. Stock** | Settings app only | Themes, launchers, Workstation Mode, app choices | Safe, ~40 % of the win |
| **B. ADB / Shizuku** | `shell` uid via USB debugging | Package removal/restore, settings writes, standby buckets, density, benchmarks | **The sweet spot — ~95 % of the win, zero warranty risk** |
| **C. Root / custom ROM** | `system` + kernel | Governors, sysfs tunables, kernels, ROMs | **Not practically available — do not plan around it** |

### The bootloader reality (verified, not rumour)

On HyperOS 3, unlocking is quota-gated: applications open at Beijing midnight and slots are
reportedly gone in milliseconds, accounts face age/activity gates, and limits of **one device
per account per year** are enforced. Even successful unlocks forfeit HyperOS OTA updates
until you relock, and trip Play Integrity — which breaks banking, Google Wallet and some
DRM/streaming apps.

**So: no custom ROM, no custom kernel, no Magisk module stack, no overclocking.** If someone
sells you a "Pad 8 performance kernel," it is either fake or a scam. Everything in this
playbook works on a locked, stock, fully warrantied device.

### Level B setup (10 minutes, one time)

1. Settings → About tablet → tap **HyperOS version** 7× → Developer options.
2. Enable **USB debugging**. For the wireless path, enable **Wireless debugging**.
3. Install **Shizuku** (v13.6.0 or newer — it explicitly adds Android 16 QPR1 support) and
   start it via wireless debugging pairing.
4. On HyperOS, if Shizuku won't stay alive: exclude it from battery optimisation and disable
   "private protection"/second-space isolation for that app.

**Security warning, stated plainly:** Shizuku grants apps *shell*-level access — that is
close to root for practical purposes. Any app you authorise through it can read your
package list, change settings and remove apps. Only authorise tools you trust, and keep the
service stopped when you're not using it.

---

## 3. Tier 0 — Measure before you touch anything (non-negotiable)

Optimisation without a baseline is storytelling. This repo gives you the instrument:

```bash
pip install -e .
python -m pad8booster probe                                    # identify + verify + probe capabilities
python -m pad8booster snapshot --label before --out before.json
python -m pad8booster bench --package com.android.chrome --runs 7 --out bench-before.json
python -m pad8booster display                                  # current density
```

Do the bench on a **cool, idle device at the same brightness, in the same orientation**, with
nothing else running. Record it. If you skip this, every later claim is unfalsifiable — including
mine.

---

## 4. Tier 1 — Delete the bloat (largest single win)

This is where most of the measurable gain lives, because these components hold wakelocks,
request location and preload content while you're not looking.

**Safe tier** — ads, telemetry, duplicate storefronts. Zero user-facing loss:

| Package | What it is | Why it goes |
| --- | --- | --- |
| `com.miui.msa.global` | MSA system ads | Serves ads inside Xiaomi apps; observed top CPU consumer |
| `com.miui.systemAdSolution` | Second ad component | Must go with MSA to actually stop ads |
| `com.miui.analytics` | Usage analytics | Pure upload, no user function |
| `com.xiaomi.metoknlp` | Xiaomi network location | Android's own location stack covers you |
| `com.miui.miservice` | Feedback/bug channel | Reinstall if you file a bug report |
| `com.xiaomi.mipicks` | GetApps store | Play Store covers everything; known wakelock offender |
| `com.mi.globalbrowser` | Mi Browser | Duplicate browser with telemetry |
| `com.miui.hybrid` / `.accessory` | Quick Apps runtime | Background mini-app preloading |
| `com.xiaomi.glgm` | Xiaomi Games | Storefront |
| `com.xiaomi.mirecycle` | Trade-in booking | Not a dependency |

**Caution tier** — real apps you might actually use (Mi Video, Mi Music, Mi Gallery, Weather,
Cleaner, Mi Cloud, Mi Push, Google apps). Read each note in `pad8booster/packages.py` before
removing. Two deserve special mention:

- `com.xiaomi.xmsf` (Mi Push) — removing it **silently breaks notifications** for Xiaomi
  first-party apps. Do not remove if you rely on them.
- `com.miui.gallery` — doubles as the system image viewer; removing it can break "view image"
  intents in other apps.

Run it through the toolkit, which enforces the guardrails:

```bash
python -m pad8booster debloat plan --tags battery privacy       # preview
python -m pad8booster debloat apply --tags battery privacy --yes
```

**Hard-protected and cannot be removed by any flag:** `com.miui.home`, `com.miui.securitycenter`,
`com.android.systemui`, `com.android.settings`, `com.google.android.gms`, `com.miui.powerkeeper`,
and ~17 others. Removing those is how people end up factory-resetting.

**Expected:** 400–900 MB more free RAM at idle, 1.5–4 GB storage, measurably lower idle load.
**Undo:** `python -m pad8booster debloat restore --yes` (uses `cmd package install-existing`;
nothing is ever deleted from `/system`).

---

## 5. Tier 2 — Retune the OS

### 5.1 Animation scale — the best ratio of win to risk

```bash
python -m pad8booster profile apply responsive --yes     # scales 1.0 → 0.5
```

Every transition you look at takes half as long. This is **perceived** latency, not CPU speed —
the honest framing matters. `instant` (0.0) is faster still but a minority of apps sequence work
on animation callbacks and can misbehave.

### 5.2 Display density — the biggest productivity lever on any tablet

The stock 320 dpi on an 11.2" 3:2 panel wastes enormous space. Dropping density fits
dramatically more content in every app — this is the change that makes it feel like a laptop,
not a phone with a big screen:

```bash
python -m pad8booster display --density 280 --yes     # ~14 % more content, still comfortable
python -m pad8booster display --density 264 --yes     # ~21 % more, for keyboard/mouse work
python -m pad8booster display --reset --yes
```

220–420 is the accepted range; below ~240, touch targets get hostile with fingers (fine with a
trackpad). This is fully reversible and survives until you reset it.

### 5.3 Refresh-rate policy

144 Hz is lovely and costs power. If you want endurance for reading/writing:

```bash
python -m pad8booster profile apply battery --yes      # caps 60 Hz, kills always-on Wi-Fi/BLE scans
```

Expect single-digit-percent battery gain over a full charge — measurable, not dramatic.
The capability probe marks the refresh-rate keys `rejected` on builds that ignore them, so you
never get a false sense of having changed something.

### 5.4 App Standby Buckets — the *real* "background app management"

This is what "booster" apps pretend to do. It's a documented Android API and it's reversible:

```bash
# Freeze a storefront you open once a month
python -m pad8booster bucket --package com.xiaomi.mipicks --bucket restricted --yes
# Protect a messenger you must never miss
python -m pad8booster bucket --package com.whatsapp --bucket active --yes
```

`restricted` means jobs and alarms almost never fire; `active` protects an app from doze.
Used asymmetrically, this is genuinely powerful — and unlike "RAM cleaners", it doesn't cause
the cold-restart battery penalty.

### 5.5 The settings worth changing by hand (2 minutes)

- **Font size + display size** together, so text stays legible when density drops.
- **Screen timeout** — the toolkit's `developer` profile sets 10 min for measurement runs.
- **Auto-brightness off** in a fixed room: the LCD's 800 nits peak is rarely needed indoors.
- **Dolby Atmos** EQ per content type (quad speakers are genuinely good).
- **HDR/Dolby Vision** per-app in the display settings.

---

## 6. Tier 3 — Turn it into a workstation (the real 10×)

### 6.1 Native: Workstation Mode and friends

HyperOS 3 has the most credible Android desktop mode shipping today:

- **Workstation Mode** — floating, resizable windows instead of full-screen apps. Toggle from
  Control Center.
- **1:9 split** and **5:5 split**, plus floating windows for chat/notes.
- **Persistent dock** for fast switching.
- **Desktop-class browser** with tabbed browsing and right-click.

Honest caveat from every reviewer: **app scaling is inconsistent**. Some apps open as stretched
phone UIs in a window. That is an Android ecosystem problem, not a Pad 8 problem — plan around
it by preferring web apps (which scale properly) for productivity.

### 6.2 Hardware that actually changes what it is

- **Focus Keyboard** (with trackpad) — turns it into a laptop; the trackpad is what makes
  Workstation Mode usable.
- **Focus Pen Pro** — pressure-sensitive notes/sketch; works with Sketchbook, Infinite Painter,
  Concepts, Nebo (handwriting-to-text).
- **USB-C hub + monitor + wired keyboard/mouse** — verify display output with a known-good
  USB-C→HDMI adapter on your unit before buying a dock; reports on Alt-Mode support vary by
  region. Miracast casting is the fallback.
- **External storage via USB-C** — since there is no SD slot, an SSD on a hub is the practical
  answer for video projects.

### 6.3 Linux userland without root

This is the single most transformative piece, and it does not need root:

```bash
pkg update && pkg upgrade
pkg install proot-distro git python nodejs-lts
proot-distro install debian
proot-distro login debian        # full Debian userland, apt, gcc, python
```

Then, on-device:

- **`code-server`** in Debian → full VS Code in Chrome at `localhost:8080`.
- **SSH** (`pkg install openssh`) → your Pad becomes a real terminal client for remote boxes.
- **GUI** via `termux-x11`, or a Wayland/VirGL stack for GL apps.
- **Note:** `proot` is not virtualisation. CPU-bound work runs near-native; syscall-heavy work is
  slowed. It is excellent for dev, scripting and CLI tools, not for kernel work.

Android 16's **AVF/pKVM** on-device Linux VM requires OEM enablement (Google ships a Terminal app
on Pixel). I have **not** verified it on HyperOS 3 — check `adb shell cmd virtmanager` on your
build rather than assuming.

### 6.4 Local AI, on-device

12 GB RAM makes this real: `llama.cpp` built or installed in Termux, running **3B–4B models at
Q4** comfortably, 7–8B tight. Expect conversational but not fast token rates, and CPU-bound
inference that heats the chassis. One report notes the **Vulkan backend is blocked by SELinux
without an unlocked bootloader** — so plan on CPU inference. Useful for offline summarising,
translation and drafting without sending data anywhere.

### 6.5 PC and console games

- **Winlator** (Box86/Box64 + Wine) runs older x86 Windows apps and games — experimental, thermal-heavy.
- **GeForce NOW / Xbox Cloud / Steam Link / Moonlight** — the Pad 8 is a superb thin client:
  144 Hz, Wi-Fi 7, great speakers, and the heavy lifting happens elsewhere. This is the
  highest-quality gaming experience the device can deliver, and it costs it nothing thermally.

### 6.6 Second-screen duty

HyperOS mirrors macOS/iPadOS and pairs with Xiaomi phones for **HyperConnect** (cross-device
clipboard, camera sharing, screen mirroring, Home Screen+). A Pad used as a second monitor with
the keyboard detached is one of the best value-per-rupee upgrades available.

---

## 7. Tier 4 — Make it *yours* (themes, UI, feel)

- **Themes app** — HyperOS 3 supports depth-effect lock screens, widget stacks and full themes.
  Xiaomi's theme store is uneven; filter by rating and check tablet screenshots specifically.
- **Launchers** — Nova, Lawnchair, Niagara all work. **Important trade-off:** the persistent dock,
  1:9 split and some Workstation affordances are features of the *system* launcher. Replacing it
  can cost you those. If you want Workstation Mode, keep `com.miui.home`.
- **Icon packs / KWGT** — a consistent icon grid and 2–3 well-built widgets do more for perceived
  quality than a full theme swap.
- **Wallpaper** — with the AG (nano-texture) variant, keep wallpapers low-contrast; you bought
  that panel to kill reflections.
- **Material You / per-app language** — both in Settings; per-app language is genuinely useful on
  a shared/family tablet.
- **Fonts** — system font replacement is OEM-gated (Themes store, no root). App-level font choice
  is the practical lever.
- **Automation** — MacroDroid or Tasker, optionally via Shizuku, for: "when Chrome opens → battery
  profile", "when keyboard connected → density 264", "22:00 → 60 Hz + DND". This is where the
  device starts feeling engineered around you instead of the other way round.
- **Audio** — quad speakers with Dolby Atmos; USB-C DAC for wired headphones (no 3.5 mm jack);
  LDAC/LHDC 5 over Bluetooth.

---

## 8. Tier 5 — Privacy and security hardening

Do these; they cost nothing and close real holes.

1. **Private DNS** (Settings → Network → Private DNS): `dns.nextdns.io`, `dns.adguard-dns.com`, or
   Cloudflare `one.one.one.one`. Blocks trackers system-wide including inside apps.
2. **Kill telemetry properly** — removing `com.miui.analytics` and MSA (§4) does more than any
   toggle, and it survives reboots.
3. **Permission audit** — Settings → Privacy → Permission manager. Revoke background location,
   microphone and camera from everything that doesn't demonstrably need them. Enable "Remove
   permissions if unused".
4. **Per-app network blocking without root** — a local-VPN firewall (NetGuard) gives you real
   per-app network control; this is the no-root way to starve an ad SDK you can't remove.
5. **Lock screen** — hide sensitive notification content; biometrics plus a strong PIN.
6. **USB debugging off when not in use.** ADB over an unlocked, unattended device is a full
   compromise. Treat Shizuku exactly the same way.
7. **Backups that survive the device** — 3-2-1: local (USB-C SSD), cloud, and an export of anything
   that only lives in a Xiaomi app. Mi Cloud alone is not a backup strategy.
8. **Do not install "booster", "cleaner", "RAM expander" or "overclock" APKs.** On a device with
   no root path, they cannot do what they claim — which makes them pure attack surface. This is
   the number one way tablets get compromised.

---

## 9. Anti-patterns — things that make it measurably worse

| Tempting | Why it backfires |
| --- | --- |
| "Free RAM" cleaners | Android uses free RAM as cache. Flushing it forces re-reads from UFS and makes launches slower. |
| Task-killer apps on a schedule | Apps relaunch cold, burning *more* power than staying resident. |
| Enlarging ZRAM/swap | No-root devices can't tune it; "swap expander" apps just burn CPU and storage. |
| Rooting for a "performance kernel" | No unlock path exists; and OTA/Play Integrity loss breaks banking, Wallet and some streaming. |
| Disabling system apps wholesale via `pm disable` | OTA updates and security patches often depend on them. Prefer per-user uninstall of *app-level* packages only. |
| Dark mode for battery | IPS LCD — the backlight doesn't care. |
| Sustained "performance mode" | Fixed-performance mode pins clocks; on a 5.75 mm fanless chassis that means heat and throttle, not speed. |
| Benchmark-chasing | `set-fixed-performance-mode-enabled` inflates scores while doing nothing for your actual workload. |

---

## 10. What to expect — with verification

| Change | Expected | How to verify |
| --- | --- | --- |
| Safe-tier debloat | +400–900 MB free RAM, +1.5–4 GB storage, lower idle load | `snapshot` before/after, `compare` |
| Animation scale 0.5 | No CPU change; transitions halve | Perceptual; `dumpsys gfxinfo` unchanged |
| Density 280 | ~+14 % content per screen | Visual; `display` readback |
| Battery profile | 10–30 % less idle drain; single-digit % total | Snapshot temp/load; overnight % drop |
| Standby buckets | Fewer background wakeups for restricted apps | `am get-standby-bucket`, `dumpsys batterystats` |
| Cold start | 10–25 % faster | `bench --runs 7` twice, `compare` (reports `within-noise` when it is) |
| Termux + proot Debian | A full Linux userland appeared | `uname -a`, `apt install` |

If a change doesn't show up in a before/after pair, it didn't happen — revert it.

---

## 11. The 90-minute execution order

```bash
# 0-10 min: baseline (do not skip)
python -m pad8booster probe
python -m pad8booster snapshot --label before --out before.json
python -m pad8booster bench --package com.android.chrome --runs 7 --out b-before.json

# 10-25 min: remove the ad/telemetry/storefront tier
python -m pad8booster debloat plan --tags battery privacy
python -m pad8booster debloat apply --tags battery privacy --yes

# 25-35 min: restore and reboot, then re-measure idle
python -m pad8booster snapshot --label after-debloat --out a1.json
python -m pad8booster compare before.json a1.json --offline --out report-1.md

# 35-50 min: retune the OS
python -m pad8booster profile apply responsive --yes
python -m pad8booster display --density 280 --yes
python -m pad8booster bucket --package com.xiaomi.mipicks --bucket restricted --yes

# 50-65 min: verify the win
python -m pad8booster snapshot --label after --out after.json
python -m pad8booster bench --package com.android.chrome --runs 7 --out b-after.json
python -m pad8booster compare before.json after.json --bench-before b-before.json \
    --bench-after b-after.json --offline --out report.md

# 65-90 min: capability layer
#   Termux -> proot-distro debian -> code-server;  Workstation Mode + keyboard;
#   Private DNS; permission audit; enable Shizuku-based automation.
```

Then weekly: one `snapshot`, and prune anything installed that you haven't opened in 30 days.

---

## 12. Rollback

Everything in this playbook is reversible, and the toolkit keeps the receipt:

```bash
python -m pad8booster revert --yes            # restore every journalled setting
python -m pad8booster debloat restore --yes   # reinstall removed packages
python -m pad8booster display --reset --yes   # stock density
```

The journal lives at `~/.local/state/pad8booster/journal.json`. If a reboot ever leaves you
stuck, `adb shell wm density reset` and `adb shell settings put global window_animation_scale 1.0`
recover the two riskiest changes.

---

## 13. Sources

- [Xiaomi Pad 8 specifications — GSMArena / DeviceSpecifications](https://www.devicespecifications.com/en/model/ae326515)
- [Xiaomi Pad 8 India launch: SD 8s Gen 4, 9200 mAh, HyperOS 3 — Gizmochina](https://www.gizmochina.com/2026/03/10/xiaomi-pad-8-india-launch-price-specs-snapdragon-8s-gen-4/)
- [Xiaomi Pad 8 / 8 Pro global specs — Gizmochina](https://www.gizmochina.com/2026/02/28/xiaomi-pad-8-and-pad-8-pro-launched-globally-specs-price/)
- [Pad 8 Pro review: Workstation Mode, USB-C 3.2, update policy — T3](https://www.t3.com/tech/tablets/xiaomi-pad-8-pro-review)
- [Pad 8 Pro review: thermals/throttling, Workstation Mode — Digital Trends](https://www.digitaltrends.com/tablets/xiaomi-pad-8-pro-review/)
- [HyperOS 3 bootloader unlock quotas and 1-device-per-year limits — r/androidroot](https://www.reddit.com/r/androidroot/comments/1rx8mdm/xiaomi_hyperos_3_bootloader_unlock_slots_are/)
- [Xiaomi bootloader unlock rules and wait times — miuirom.org](https://miuirom.org/updates/xiaomi-bootloader)
- [Shizuku v13.6.0: Android 16 QPR1 support, no-root setup](https://shizuku-apk.com/faqs.html)
- [App Standby Buckets — Android developer documentation](https://developer.android.com/topic/performance/appstandby)
- [Android Virtualization Framework (AVF)](https://source.android.com/docs/core/virtualization)
- [Termux](https://termux.dev/) · [proot-distro](https://github.com/termux/proot-distro) · [llama.cpp](https://github.com/ggml-org/llama.cpp) · [Winlator](https://github.com/brunodev85/winlator)

*Specifications and unlock policy were cross-checked across the sources above on 2026-11-06.
Regional SKUs differ (charging wattage, bundled charger, storage speed on the 128 GB model);
verify against your unit's `ro.product.model` and `ro.soc.model` with `python -m pad8booster probe`.*

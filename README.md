# Pad8booster + PADFINITY

Two things for one tablet — a **Xiaomi Pad 8 (12 GB / 256 GB, HyperOS 3 / Android 16)**:

| | What it is | State |
| --- | --- | --- |
| **PADFINITY** | A desktop-environment app for the tablet: real internal window manager, taskbar, workspaces, insights, app discovery | Engine **compiled + 135 tests passing** · App layer written, **no APK yet** |
| **Pad8Booster** | A host-side (Python) measurement + debloat + reversible-tuning toolkit | **63 tests passing** · runs against a real device over ADB |

Both are no-root. Read [`docs/padfinity/KNOWN_LIMITATIONS.md`](docs/padfinity/KNOWN_LIMITATIONS.md)
before expecting an installable APK — there isn't one, and that document explains exactly why.

---

# PADFINITY

**Your tablet. Your workspace. Your rules.**

A desktop-inspired workspace that lives *inside* HyperOS rather than replacing it.

## The honest engineering position

The hardest part of a desktop environment is not the pixels — it is geometry, z-order, focus,
snapping, tiling, workspace isolation and persistence. So that part was built first, as a
**dependency-free Kotlin engine** that compiles and runs on a bare JVM:

```
android/engine/    pure Kotlin · zero dependencies · no Android imports
```

```bash
cd android/engine
kotlinc src/main/kotlin src/test/kotlin -include-runtime -d engine-tests.jar
java -jar engine-tests.jar      # PASSED: 135  FAILED: 0
```

What those 135 checks actually prove: drag clamping keeps a title bar reachable; snapping to 8
zones honours custom split ratios; 2×2 tiling conserves the workspace area exactly; maximised
windows track workspace resizes; workspace switching preserves each window set; the persistence
codec round-trips names containing separators and rejects malformed input; the taskbar keeps pinned
order stable; and the insights engine **cannot** emit placebo advice (that's an executable
assertion, not a promise).

## Capability reality (measured on this device, not assumed)

A third-party project measured freeform behaviour **on a Xiaomi Pad 8 running HyperOS 3.0**:

| Approach | Result |
| --- | --- |
| `FEATURE_FREEFORM_WINDOW_MANAGEMENT` | ✅ present |
| `ActivityOptions.setLaunchWindowingMode()` | ❌ hidden API, blocked |
| `am start --windowingMode 5` as **shell** (Shizuku) | ✅ works |
| Specifying freeform bounds | ❌ not accepted by this build |

So PADFINITY can open *other* apps in real floating windows **via Shizuku**, but cannot control
their geometry. Internal windows are fully managed; external apps are not. The UI never pretends
otherwise. Full detail: [`DEVICE_RESEARCH.md`](docs/padfinity/DEVICE_RESEARCH.md).

## Documentation

| Document | Contents |
| --- | --- |
| [DEVICE_RESEARCH.md](docs/padfinity/DEVICE_RESEARCH.md) | Verified hardware, HyperOS 3 realities, capability matrix |
| [COMPATIBILITY.md](docs/padfinity/COMPATIBILITY.md) | Every feature with a status (Confirmed/Compatible/Restricted/Advanced/Unavailable) |
| [ARCHITECTURE.md](docs/padfinity/ARCHITECTURE.md) | Stack rationale, module boundaries, state flow |
| [PERMISSIONS.md](docs/padfinity/PERMISSIONS.md) | What is requested, why, and what degrades if refused |
| [SECURITY.md](docs/padfinity/SECURITY.md) | Threat model, trust boundaries, emergency reset |
| [TESTING.md](docs/padfinity/TESTING.md) | What was executed vs what never ran, plus the device test plan |
| [KNOWN_LIMITATIONS.md](docs/padfinity/KNOWN_LIMITATIONS.md) | No APK, no device test, uncontrollable freeform bounds… |
| [FEATURE_ROADMAP.md](docs/padfinity/FEATURE_ROADMAP.md) | Phases with honest status |
| [APP_DISCOVERY.md](docs/padfinity/APP_DISCOVERY.md) | Evaluated third-party apps and the recommended 5-app setup |
| [CHANGELOG.md](docs/padfinity/CHANGELOG.md) | 0.1.0 "Engine first" |

## Build

```bash
# Engine only — no Android SDK required
cd android/engine && kotlinc src/main/kotlin src/test/kotlin -include-runtime -d t.jar && java -jar t.jar

# Full app — requires Android SDK 36 + network access to Google Maven
cd android && ./gradlew :app:assembleDebug
```

## Principles encoded in code, not prose

- **No `INTERNET` permission.** No telemetry, no accounts, no cloud. The recommendation catalogue
  ships inside the APK.
- **No `QUERY_ALL_PACKAGES`** — a scoped `<queries>` block resolves only launcher activities.
- **No root, ever.** Shizuku (shell identity) is the ceiling, and it is optional.
- **No placebo.** The insights engine asserts that it never says "free up RAM" or "kill background
  apps" — tested across a 288-case metric matrix.
- **Everything reversible.** System writes are journalled with read-back verification.

---

# Pad8Booster (host-side toolkit)

Measurement-first optimisation for the same tablet, driven from a computer over ADB.

```bash
pip install -e .
python -m pad8booster probe
python -m pad8booster snapshot --label before --out before.json
python -m pad8booster debloat apply --tags battery privacy --yes
python -m pad8booster profile apply responsive --yes
python -m pad8booster display --density 280 --yes
python -m pad8booster compare before.json after.json --offline --out report.md
python -m pad8booster revert --yes        # undo everything, from the journal
```

- `probe` verifies the device really is a Pad 8 (SM8735/SM8750, API 36) before permitting any write
- `bench` measures cold starts with a **noise band** — a delta inside the noise is reported as
  `within-noise`, never as a win
- `debloat` ships 28 catalogued packages, 23 hard-protected, reversible per-user uninstall
- Everything mutating is dry-run by default and journalled for exact restore

Dashboard: `python3 web/server.py` (dependency-free, demo data unless `--live`).
Tests: `python -m pytest -q` → **63 passing**.
Full transformation guide: [`docs/PAD8_TRANSFORMATION_PLAYBOOK.md`](docs/PAD8_TRANSFORMATION_PLAYBOOK.md).

---

## Repository layout

```
pad8booster/           host-side Python toolkit (ADB, measurement, debloat, profiles)
web/                   its dependency-free dashboard
android/engine/        PADFINITY window engine — pure Kotlin, 135 checks
android/app/           PADFINITY Compose application (uncompiled: no Android SDK here)
docs/                  transformation playbook + all PADFINITY documents
tests/                 Python test suite (63 tests)
```

No licence is set yet — add one before distributing.

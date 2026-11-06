# CHANGELOG

All notable changes to PADFINITY. Format loosely follows Keep a Changelog; versions follow SemVer.

## [0.1.0] — 2026-11-06 — "Engine first"

First milestone. Deliberately engine-first: the part of a desktop environment that is hardest to
get right (geometry, z-order, focus, snapping, workspaces, persistence) is implemented and
**verified by 135 executed checks** before any pixels were drawn.

### Added — engine (compiled with Kotlin 2.4.21, JDK 25; 135 checks passing)
- `Geometry.kt` — `Rect` with clamping, overlap fraction, hit testing; `SnapZone`; `TileLayout`.
- `Window.kt` — immutable window records, modes, `WindowKind` (internal vs system app).
- `WindowManager.kt` — open/close, raise/focus with MRU history, Alt-Tab cycling, drag with
  off-screen clamps, resize with minimum sizes, minimise/maximise/restore with geometry memory,
  8-zone snapping with ratio clamping, 4 tiling layouts, cascade, live snap preview, hit testing,
  workspace-resize safety.
- `Workspaces.kt` — one `WindowManager` per workspace, last-workspace protection, active-workspace
  fallback, snapshot/restore.
- `DesktopCodec` — versioned (`PADFINITY-DESKTOP v1`), escaped, line-oriented persistence with
  hostile-input rejection and round-trip fidelity.
- `TaskbarModel` — pinned/running/recents composition, dedupe, overflow counting, reordering.
- `InsightEngine` — six measured rules (storage, thermal, battery heat, memory pressure, jank,
  package count, low-battery refresh advice) with an **executable anti-placebo policy**.
- `Recommender` + `SeedCatalogue` — weighted 8-criterion ranking with policy filters
  (root/Shizuku/Accessibility/duplicates) and one-per-category setup builder.

### Added — application layer (written, **not compiled**: no Android SDK in build environment)
- Gradle project (`settings.gradle.kts`, version catalog, `:engine` as `kotlin("jvm")`,
  `:app` as `com.android.application` with Compose).
- Compose desktop surface with draggable/resizable window chrome, snap preview, taskbar, launcher
  overlay, insights and discovery screens, theme, `DesktopViewModel`, persistent repository.

### Added — documentation
- `DEVICE_RESEARCH.md`, `COMPATIBILITY.md`, `ARCHITECTURE.md`, `PERMISSIONS.md`, `SECURITY.md`,
  `TESTING.md`, `KNOWN_LIMITATIONS.md`, `FEATURE_ROADMAP.md`, `APP_DISCOVERY.md`, this changelog.

### Known gaps at this version
- **No APK.** Build environment lacks the Android SDK and access to Google Maven / Maven Central.
- **No device testing.** Zero rows in `COMPATIBILITY.md` are marked *Tested*.
- Freeform geometry control unavailable on this firmware (third-party-verified).

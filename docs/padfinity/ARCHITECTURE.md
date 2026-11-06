# ARCHITECTURE.md — PADFINITY

## 0. One-sentence architecture

A **Kotlin/Compose Android app** whose desktop environment is driven by a **dependency-free window
engine** (`android/engine`) that owns geometry, z-order, focus, snapping, tiling, workspaces and
persistence — with every privileged capability quarantined behind a **capability gateway** that
reports honestly whether it is available.

```
┌──────────────────────────────────────────────────────────────┐
│ app (Compose UI)                                             │
│  DesktopSurface · WindowChrome · Taskbar · Launcher          │
│  CustomisationCentre · InsightsScreen · DiscoveryScreen      │
└───────────────┬──────────────────────────────────────────────┘
                │ observes state, sends intents
┌───────────────▼──────────────────────────────────────────────┐
│ app/desktop  DesktopViewModel  (single source of UI state)    │
│  – translates gestures → engine calls                         │
│  – debounces layout, coalesces frames                         │
│  – persists on change (debounced)                             │
└───────────────┬──────────────────────────────────────────────┘
                │ pure Kotlin, no Android types
┌───────────────▼──────────────────────────────────────────────┐
│ engine  (JVM-only, 0 dependencies, 135 checks)                │
│  Geometry · Window · WindowManager · Workspaces + Codec       │
│  Taskbar · Insights · Recommender                             │
└───────────────┬──────────────────────────────────────────────┘
                │ capability queries
┌───────────────▼──────────────────────────────────────────────┐
│ capability gateway                                            │
│  NoneAvailable → standard Android APIs                        │
│  ShizukuGateway → shell identity (advanced features)          │
│  (RootGateway → deliberately not implemented)                 │
└──────────────────────────────────────────────────────────────┘
```

## 1. Why this stack

| Decision | Reason | Rejected alternative |
| --- | --- | --- |
| **Kotlin + Jetpack Compose** | First-class window/gesture APIs, predictable recomposition, no bridge overhead, Material 3 theming, good keyboard/pointer support on tablets | Flutter (second rendering stack, weaker platform integration), React Native (bridge latency in drag loops), Web/Electron (cannot host native windows) |
| **Pure-Kotlin engine, zero deps** | The hardest part of a desktop environment is *geometry and state*, and this can be verified on a bare JVM in CI without an emulator. It also makes the engine reusable host-side | Putting logic in `ViewModel` (untestable without Robolectric), or in Compose (logic entangled with rendering) |
| **Immutable `Window` records + explicit mutators** | Every mutation is auditable and reproducible; no observer races during drag | Mutable observable model (harder to reason about z-order/focus invariants) |
| **Hand-rolled codec** | Keeps engine dependency-free; format is versioned (`PADFINITY-DESKTOP v1`) and round-trip tested | kotlinx.serialization (a Maven dependency the engine must not need) |
| **One `DesktopViewModel`** | Single source of truth, easy to persist and to reason about frame budget | Many independent ViewModels per panel (state divergence) |
| **Capability gateway with explicit statuses** | The product must never claim a capability it lacks. Statuses come from `COMPATIBILITY.md` and are surfaced in the UI | Trying privileged calls and swallowing exceptions (silent failure) |

## 2. Modules (Gradle)

```
android/
  engine/          pure Kotlin, kotlin("jvm")  — no Android plugin, no Android deps
  app/             com.android.application, Compose
    ui/theme       design system: colours, typography, shapes, motion
    desktop        DesktopSurface, WindowChrome, snap previews
    taskbar        Taskbar composable + overflow popup
    launcher       searchable launcher overlay
    insights       device metrics + InsightEngine rendering
    discovery      recommender UI with "why this ranked" explanation
    customisation  guided settings + capability-aware deep links
    capability     Shizuku integration behind an interface
    data           repository + persistence
```

The split exists to enforce a rule: **`app` may depend on `engine`; `engine` may never depend on
`app` or on Android.** That is checked by the fact that `engine` compiles with plain `kotlinc`.

## 3. State flow

1. Pointer/touch event → `DesktopSurface` gesture handler.
2. Handler calls `WindowManager.moveBy/resizeBy/snap/…`.
3. Engine returns new state; `DesktopViewModel` publishes it.
4. Compose recomposes **only** the windows whose bounds changed (stable keys).
5. Persistence is debounced (~600 ms idle) to avoid writing on every pointer frame.

Drag performance rule: no allocation-heavy work in the gesture loop; no I/O on the main thread;
snap preview computed from a cheap rect comparison (already cheap: 8 comparisons).

## 4. Window identity: internal vs system

`WindowKind.INTERNAL` — PADFINITY surfaces. Fully managed by the engine; renders inside our
Compose tree.

`WindowKind.SYSTEM_APP` — a real installed app. Appears in the taskbar with `packageName` set. It
is **launched**, never rendered by us:

- **Standard path:** normal full-screen `Intent`.
- **Advanced path:** Shizuku shell → `am start --windowingMode 5 -n pkg/activity` (real freeform,
  geometry uncontrollable on this build).
- **Never:** draw a fake frame around a screenshot, or label an internal window as a system window.

## 5. Permission architecture

All privileged operations go through `CapabilityGateway`:

```kotlin
interface CapabilityGateway {
    val status: CapabilityStatus          // AVAILABLE / NEEDS_PERMISSION / NEEDS_SHIZUKU / UNAVAILABLE
    fun canExecute(op: CapabilityOp): Boolean
    suspend fun execute(op: CapabilityOp): CapabilityResult
}
```

The UI renders the *status* rather than a button that fails. See `PERMISSIONS.md` for the full
grant matrix and `SECURITY.md` for the threat model.

## 6. Testing strategy

| Layer | How | Status |
| --- | --- | --- |
| Engine logic | Kotlin harness, real JVM execution | ✅ 135 checks pass |
| Engine persistence | Round-trip encode/decode incl. hostile input | ✅ |
| Policy rules | Assertions that no placebo advice / no root app is emitted by default | ✅ |
| Compose UI | Instrumented tests (needs device/emulator) | ⛔ not run — no Android SDK here |
| Integration (Shizuku, freeform) | Manual on device | ⛔ not run — no device |
| Performance (drag frame budget) | Macrobenchmark | ⛔ not run |

## 7. Build & run

```bash
# engine only — works anywhere with Kotlin, no Android SDK needed
cd android/engine
kotlinc src/main/kotlin src/test/kotlin -include-runtime -d engine-tests.jar
java -jar engine-tests.jar

# full app — requires Android SDK 36 + AGP (see KNOWN_LIMITATIONS.md)
cd android
./gradlew :app:assembleDebug
```

## 8. Deliberate non-goals

Full OS replacement; system-wide chrome redesign; kernel tuning; a background daemon that watches
everything; any feature whose only implementation is a lie.

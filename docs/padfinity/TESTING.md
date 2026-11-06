# TESTING.md — what was executed, and what was not

This file distinguishes rigorously between *written*, *executed*, *passed*, *failed* and
*never ran*. The distinction is the whole point.

## 1. Executed and passing — engine (real Kotlin, real JVM)

**Environment:** Kotlin 2.4.21 (compiled with `kotlinc`), Temurin JDK 25.0.2, Linux x86-64.
**Command:**

```bash
cd android/engine
kotlinc src/main/kotlin src/test/kotlin -include-runtime -d engine-tests.jar
java -jar engine-tests.jar
```

**Result: `PASSED: 135  FAILED: 0`**

| Group | Checks | What is proven |
| --- | --- | --- |
| window lifecycle | 12 | open/close, no duplication, cascade placement, focus follows |
| focus and MRU | 8 | MRU ordering, Alt-Tab cycling, minimise removes from MRU |
| geometry constraints | 9 | off-screen clamps, title-bar reachability, minimum sizes |
| minimise/maximise/restore | 11 | geometry memory, mode transitions, input refused when maximised |
| snapping | 14 | halves, custom ratios, ratio clamping, quadrants, restore-bounds preservation |
| snap detection | 7 | edge/corner detection precedence, preview bounds == applied bounds |
| tiling | 10 | 2-col/3-col coverage, 2×2 area conservation, main+stack split, cascade offsets |
| hit testing & resize | 6 | topmost-at-point, minimised exclusion, workspace shrink safety |
| workspaces | 10 | independent window sets per workspace, last-workspace protection, fallback |
| persistence | 9 | round-trip fidelity incl. separators in names, malformed input rejection |
| taskbar | 9 | pinned order stability, dedupe, truncation, overflow count, reorder |
| insights | 11 | each rule fires at threshold; **no placebo phrasing anywhere in a 288-case metric matrix** |
| recommender | 15 | weighted ordering, policy exclusion (root/Shizuku/Accessibility), one-per-category setup |

Notable policy tests (these encode product ethics as executable assertions):

- `no placebo advice is ever emitted`
- `placebo-free across the whole metric matrix`
- `root app excluded by default`
- `accessibility app excluded unless opted in`
- `unminimised window always reachable after workspace resize`

### Bugs the tests actually caught

1. `DesktopCodec.decode` returned `null` for a windowless workspace (valid state).
2. Consumers had to distinguish "no windows" from "unknown workspace" — fixed by seeding an
   empty list per declared workspace.
3. One test assertion itself was wrong about decode semantics; corrected, engine unchanged.

## 2. Not executed — Android application layer

| Item | Why not | Consequence |
| --- | --- | --- |
| `:app:assembleDebug` (APK) | No Android SDK, no AGP: `dl.google.com`, `maven.google.com`, `repo1.maven.org`, `services.gradle.org` are unreachable from the build environment | **No APK exists.** The Compose sources are unverified |
| Compose UI rendering | Same; also no emulator | Layout/animation quality unproven |
| Shizuku integration | No device, no Shizuku service | Freeform path unproven in our build (Tested³ externally) |
| Instrumented tests | Require device/emulator | None written yet; plan below |
| Macrobenchmark (drag frame budget) | Requires device | No performance claims made |

**No feature is marked "Tested" in `COMPATIBILITY.md`.** That is deliberate.

## 3. Device test plan (execute in this order on the Pad 8)

| # | Test | Pass criterion |
| --- | --- | --- |
| D1 | Cold launch → desktop renders in landscape | < 1.5 s to first frame |
| D2 | Rotate to portrait with 3 windows open | Windows clamp inside, geometry preserved |
| D3 | Drag a window to each of 8 snap zones | Preview matches final bounds exactly |
| D4 | Resize below minimum | Stops at minWidth/minHeight |
| D5 | 6 windows + Alt-Tab ×20 | No dropped focus, no z-order corruption |
| D6 | Switch workspaces 20× | Each keeps its windows and scroll positions |
| D7 | Kill app → relaunch | Desktop restored from codec |
| D8 | Force-stop during drag | No corrupted persistence (atomic write) |
| D9 | Shizuku freeform launch of Chrome | Task reports `mode=freeform`; fallback works when Shizuku off |
| D10 | 30 min mixed workload | No ANR, no >5%/hr idle drain attributable to PADFINITY |
| D11 | Density change via Shizuku → reset | Layout adapts; reset restores |
| D12 | Emergency reset | All journalled settings restored |

Record firmware (`ro.build.version.incremental`) with every result.

## 4. Regression policy

Engine changes require `java -jar engine-tests.jar` to pass before commit. Any new engine behaviour
gets a check in the same commit — the harness is the contract.

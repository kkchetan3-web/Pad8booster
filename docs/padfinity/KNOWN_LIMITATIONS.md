# KNOWN_LIMITATIONS.md

Read this before evaluating PADFINITY. Nothing here is a temporary embarrassment; each item is a
deliberate, documented boundary.

## 1. No APK was produced in the development environment

**Stated plainly: there is no installable APK yet, and I will not claim otherwise.**

The environment used to build this had no Android SDK and no access to the repositories that
supply one:

| Needed | Host | Reachable? |
| --- | --- | --- |
| Android SDK platform 36, build-tools | `dl.google.com` | ❌ blocked |
| Android Gradle Plugin + AndroidX + Compose artifacts | `maven.google.com` | ❌ blocked |
| Third-party JVM/Android libraries | `repo1.maven.org` | ❌ blocked |
| Gradle distribution | `services.gradle.org` | ❌ blocked |

What *was* possible: JDK 25 and Kotlin 2.4.21 (via PyPI and npm). So the **engine compiles and its
135 checks pass**, while the Compose application layer is written but **uncompiled and
unrendered**.

To produce the APK yourself (any machine with Android Studio or a normal Android SDK):

```bash
cd android
./gradlew :app:assembleDebug     # needs SDK 36 + network access to Google Maven
```

Expect first-run friction in the UI layer — compilers catch what reading cannot. Treat the Compose
code as reviewed-but-unbuilt.

## 2. Zero device testing

No Xiaomi Pad 8 was attached. Every "Confirmed" status in `COMPATIBILITY.md` means *documented
platform behaviour*, not *verified on your hardware*. Rows that are third-party-verified elsewhere
are marked Tested³ with a citation.

## 3. Freeform geometry cannot be controlled

On Pad 8 / HyperOS 3 the shell accepts `am start --windowingMode 5` but **rejects bounds** (Tested³,
`SideBar` project). Consequences:

- We can open another app in a real floating window.
- We cannot choose its size or position; HyperOS does.
- Therefore PADFINITY's own tiling/snapping cannot arrange *external* apps — only internal ones.
- The UI must say this. It does.

## 4. Internal windows are not system windows

PADFINITY's window manager is genuine, but it manages *our* surfaces. It cannot move, resize or
decorate another application's window. Any product that appears to do so is either using
Accessibility to fake it or is a system app. We do neither.

## 5. Launcher replacement cost

If you set PADFINITY as the default HOME app, you lose HyperOS's own dock, 1:9 split and some
Workstation-Mode affordances, because those belong to `com.miui.home`. The recommended
configuration is: keep HyperOS as HOME, use PADFINITY as a full-screen workspace app *and* an
optional launcher overlay.

## 6. Accessibility / Shizuku are trust decisions

Advanced features require shell identity or an Accessibility service. Both are materially more
privileged than a normal app. They are opt-in, off by default, and documented in `PERMISSIONS.md`.

## 7. Metrics we cannot read

- Battery **cycle count / health percentage**: not exposed to third-party apps on this platform.
  PADFINITY shows temperature and charge behaviour instead of inventing a health number.
- Per-app CPU usage: requires privileged access; we show system-wide load instead.
- Other apps' memory: same restriction.
- Frame timing of *other* apps: requires `dumpsys gfxinfo` (shell) — available via Shizuku only.

## 8. Android app scaling

Many Android apps are phone UIs stretched across 11.2". Inside PADFINITY windows this is very
visible. Mitigations: prefer web apps in desktop mode for productivity surfaces, expose a
"letterbox to phone width" window option, and document the limitation rather than pretending it is
a bug we can fix.

## 9. Persistence is not transactional across process death

Writes are debounced and atomic (write-temp-then-rename), but a hard kill during the write window
can lose the *last* layout change. The previous good snapshot survives.

## 10. Not implemented yet (honest backlog)

Desktop icons/drag-and-drop on the wallpaper, widget host, file browser, automation runtime,
themes editor, widget preview thumbnails, external-display handling, keyboard shortcut editor.
See `FEATURE_ROADMAP.md` for the honest phase/status mapping.

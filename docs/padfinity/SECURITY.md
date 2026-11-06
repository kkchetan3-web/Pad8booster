# SECURITY.md — PADFINITY

## 1. Threat model

PADFINITY is a **local-first** productivity shell. The realistic threats, in order:

| # | Threat | Mitigation |
| --- | --- | --- |
| T1 | **Shizuku misuse** — a malicious component inheriting shell identity | Shell operations are a closed, enumerated set of commands; no dynamic/parameterised command construction from user text; journal records every write |
| T2 | **Overlay abuse** — an overlay that captures taps or spoofs UI | Overlay used only for the user-invoked edge panel; `FLAG_NOT_FOCUSABLE` where possible; panel can be killed from Quick Settings |
| T3 | **Accessibility abuse** — screen reading | Service never inspects text content; only consumes key events; disabled by default; documented before granting |
| T4 | **Data exfiltration** | App declares **no `INTERNET` permission** in the MVP. No analytics, no crash upload, no ads |
| T5 | **Config corruption / pathological state** | Codec validates and rejects malformed input; engine invariant tests; emergency reset (below) |
| T6 | **Supply-chain tampering** | Minimal dependency surface: AndroidX + Compose + Shizuku API only; lockfiles committed; no transitive-only libs for core function |
| T7 | **Shoulder-surfing of the taskbar** | Optional "hide app titles" and "blur window previews" toggles |
| T8 | **Escalation via intent redirection** | All exported components reviewed; only the launcher activity is exported; no `PendingIntent` with implicit base intents |

## 2. Trust boundaries

```
[ PADFINITY app process, uid = app ]        ← no INTERNET, no shared storage
        │  Binder (bounded, enumerated)
[ Shizuku service, uid = shell ]           ← privileged; only reachable after explicit user grant
        │  Binder
[ system_server ]                          ← platform
```

The app never holds root. Shizuku is optional; without it, everything in Tier 0/1 still works.

## 3. Data handling

- **Stored locally only:** desktop layout (windows, geometry, workspaces, pinned apps, preferences).
  Location: app-private storage; `allowBackup="false"`.
- **Never collected:** contacts, messages, location, screen content, keystroke logs, installed-app
  *usage history beyond what you explicitly enable*.
- **No telemetry.** There is no server to send it to; the app has no `INTERNET` permission.
- **Recommendations are static** and bundled, so they cannot leak what you searched for.

## 4. Emergency reset

Required by the product spec and implemented as the primary recovery path:

1. **In-app:** Settings → Advanced → *Reset PADFINITY* clears desktop state, restores every
   journalled system setting, stops the Shizuku session, and removes the overlay.
2. **Cold reset without opening the app:** long-press the taskbar clock for 5 s, or launch
   `dev.padfinity/.RecoveryActivity` via `adb shell am start`.
3. **Total reset:** `adb shell pm clear dev.padfinity` — removes all app data.
4. **Uninstall safety:** PADFINITY does not alter system state that survives uninstall *except*
   journalled system settings (density, animation scale, refresh rate, removed packages). The
   reset path is offered on the uninstall flow, and the host-side `pad8booster revert` command can
   restore them independently. **No bootloader, kernel, or partition is ever touched.**

## 5. Supply chain and release process

- Dependencies pinned in `gradle/libs.versions.toml`; no dynamic versions (`+`).
- Release builds: R8 + resource shrinking, reproducible keystore handling (key never committed).
- APKs signed with a dedicated key; `SHA-256` published with each release.
- Dependency review before each release; no new dependency without a stated reason.

## 6. Reporting

This is a personal project; still, security issues should be filed as GitHub issues **without**
public exploit details for anything affecting Shizuku integration, so users are not left exposed.

## 7. Deliberate exclusions

No device admin, no install-packages, no SMS/call access, no accessibility screen scraping, no
background location, no always-on foreground service, no auto-start of automation after boot
without explicit user opt-in.

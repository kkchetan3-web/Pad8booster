# APP_DISCOVERY.md — evaluated third-party applications

PADFINITY's Discovery Centre recommends tools **only where they add something PADFINITY cannot do
itself**. Ranking is code (`android/engine/.../Recommender.kt`) so the reasoning is auditable; this
document is the editorial justification behind those scores.

Scores are 0–10 on eight weighted criteria (compatibility, usefulness, reliability, tablet fit,
performance, privacy, ease, cost). Weights: compatibility 1.60, usefulness 1.40, reliability 1.30,
tablet fit 1.20, performance 0.90, privacy 0.90, ease 0.70, cost 0.60.

> Prices, availability and feature sets change constantly. Verify on the store page before buying.
> Anything I could not verify is marked as unverified rather than guessed.

| App | Developer | Category | Access tier | Free? | Why it matters on the Pad 8 | Caveats |
| --- | --- | --- | --- | --- | --- | --- |
| **Shizuku** | RikkaApps | Advanced access | none (grants shell) | ✅ open source | The enabler: real freeform launches, density, settings, standby buckets — all without root. Explicit Android 16 QPR1 support in 13.6.0+ | Must be restarted after reboot unless auto-start works; shell identity is a real trust decision |
| **Termux** | Termux project | Developer | none | ✅ | Full Linux userland (git, Python, Node, SSH, `proot-distro`). With the keyboard this is the single biggest capability jump | Not on Play Store — install from F-Droid/GitHub; terminal UX needs a keyboard |
| **KWGT** | Kustom Industries | Widgets | none | ✅ + paid | Per-widget sizing/custom code; the only way to get truly dense tablet widgets | Heavy widgets cost battery; steep learning curve |
| **MacroDroid** | ArloSoft | Automation | Accessibility | ✅ + paid | Trigger→action macros with a sane UI; covers most automation needs | Special permissions; overlaps PADFINITY's own profiles — use only for what those lack |
| **Tasker** | João Dias | Automation | Accessibility | ❌ paid | Most powerful automation on Android | Steep curve; many permissions; overkill unless you need its breadth |
| **MiXplorer** | Hootan Parsa | Files | none | ✅ | Dual-pane, SMB/SFTP — closest to a desktop file manager | Scoped storage limits writes to other apps' data |
| **Niagara Launcher** | Peter Huber | Launcher | none | ✅ + paid | Fast, elegant on phones | **Poor fit on 11.2" 3:2** — vertical list wastes width; replacing `com.miui.home` loses HyperOS dock/1:9 split |
| **Key Mapper** | Key Mapper contributors | Input | Shizuku/Accessibility | ✅ open source | Remaps keyboard/mouse buttons; complements PADFINITY's in-app shortcuts | Accessibility grant; verify current availability of releases |
| **Panels** | Panels | Edge panel | Accessibility | ✅ + paid | Edge launcher with freeform-friendly workflow | HyperOS already has a sidebar; only add if you need multi-app freeform launch |

## Deliberate omissions

- **"RAM booster" / "cleaner" / "battery saver" apps** — excluded on principle. On Android they
  flush the page cache that makes launches fast, or toggle settings you already control. Including
  them would make the recommender untrustworthy.
- **Root-only tools** (kernel managers, Magisk modules) — excluded by policy; the bootloader path
  is quota-gated and forfeits OTA + Play Integrity.
- **Duplicate launchers** when you have already chosen one — the ranking filters duplicates by
  category so the Setup view does not stack five launchers.

## Recommended setup (one per category)

1. **Shizuku** (advanced access) — unlock the Shizuku tier in PADFINITY's settings.
2. **Termux** (developer) — install once; use `proot-distro` for Debian when you need real tooling.
3. **KWGT** (widgets) — only if you want tablets-dense widgets; otherwise use PADFINITY's own.
4. **MacroDroid** (automation) — only for triggers PADFINITY's profiles do not cover.
5. **MiXplorer** (files) — until PADFINITY's own SAF browser ships.
6. Keep HyperOS as your default launcher; run PADFINITY as a workspace app.

That is five apps, not fifty. A personalisation stack that needs constant maintenance is not
personalisation — it is a second job.

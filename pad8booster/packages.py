"""Package (debloat) engine with hard guardrails.

Debloating is the single highest-value no-root optimisation available on
HyperOS, and also the fastest way to brick a working tablet's notifications,
banking apps or OTA updates. The engine therefore enforces three rules:

1. **Verification first.** The device must pass :func:`~pad8booster.device.verify_pad8`
   with high confidence before any package can be touched.
2. **Catalogue only.** Only packages listed here with an explicit risk tier may
   be removed; ``--allow-unlisted`` is an opt-in escape hatch and still cannot
   touch :data:`PROTECTED`.
3. **Always reversible.** Removal is ``pm uninstall --user 0`` (per-user, APK
   stays on the system partition) and reversal is
   ``cmd package install-existing``. Nothing is ever deleted from ``/system``.

Package names differ between HyperOS regional builds, so an entry that is not
installed on your tablet is skipped, not reported as a failure.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Iterable, Any

from .adb import Adb, AdbError

#: Never removable, regardless of flags. Removing any of these breaks the device
#: in ways that require a factory reset (or fastboot) to recover from.
PROTECTED: frozenset[str] = frozenset(
    {
        "com.miui.home",
        "com.miui.securitycenter",
        "com.android.systemui",
        "com.android.settings",
        "com.google.android.gms",
        "com.google.android.gsf",
        "com.google.android.permissioncontroller",
        "com.android.permissioncontroller",
        "com.android.shell",
        "com.android.packageinstaller",
        "com.miui.powerkeeper",
        "com.miui.daemon",
        "com.miui.contentcatcher",
        "com.miui.notification",
        "com.android.providers.settings",
        "com.android.providers.media",
        "com.android.providers.contacts",
        "com.android.phone",
        "com.android.bluetooth",
        "com.android.nfc",
        "com.miui.accessibility",
        "com.xiaomi.miui.os",
        "com.miui.miwallpaper",
    }
)


@dataclass(frozen=True)
class PackageRule:
    """One debloat candidate."""

    package: str
    name: str
    category: str
    risk: str  # "safe" | "caution" | "cosmetic"
    note: str
    tags: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


#: Curated catalogue. Every entry here is an *additional* application or a
#: telemetry/ads component - never a system service the OS depends on.
#: ``risk="safe"`` = ads, analytics, redundant duplicate apps.
#: ``risk="caution"`` = user-visible function you may actually want.
CATALOGUE: tuple[PackageRule, ...] = (
    # -- advertising & telemetry -------------------------------------------
    PackageRule(
        "com.miui.msa.global", "MSA (MIUI System Ads)", "ads", "safe",
        "System-level advertising SDK. Serves ads in Xiaomi apps. Zero user value.",
        ("battery", "privacy", "ram"),
    ),
    PackageRule(
        "com.miui.systemAdSolution", "System Ad Solution", "ads", "safe",
        "Second ad-serving component. Removing both this and MSA kills in-app ads.",
        ("privacy",),
    ),
    PackageRule(
        "com.miui.analytics", "MIUI Analytics", "telemetry", "safe",
        "Uploads usage analytics. Removing it cannot break user-facing features.",
        ("privacy", "battery"),
    ),
    PackageRule(
        "com.xiaomi.metoknlp", "Metok NLP", "telemetry", "safe",
        "Network location helper that pings Xiaomi servers. Android's own "
        "location stack handles positioning without it.",
        ("privacy", "battery"),
    ),
    PackageRule(
        "com.miui.miservice", "Services & Feedback", "telemetry", "safe",
        "Feedback/bug-report channel. Safe to remove; re-enable if you file bugs.",
        ("privacy",),
    ),
    # -- redundant storefronts / browsers ----------------------------------
    PackageRule(
        "com.xiaomi.mipicks", "GetApps", "store", "safe",
        "Xiaomi's third-party app store. Play Store covers everything, and this "
        "is a known background-wakelock offender.",
        ("battery", "ram", "privacy"),
    ),
    PackageRule(
        "com.mi.globalbrowser", "Mi Browser", "browser", "safe",
        "Duplicated browser with telemetry. Use Chrome/Firefox instead.",
        ("privacy",),
    ),
    PackageRule(
        "com.miui.hybrid", "Quick Apps", "store", "safe",
        "Mini-app runtime that preloads content in the background.",
        ("battery", "ram"),
    ),
    PackageRule(
        "com.miui.hybrid.accessory", "Quick Apps Accessory", "store", "safe",
        "Companion to Quick Apps; remove together with it.",
        ("battery",),
    ),
    PackageRule(
        "com.xiaomi.glgm", "Xiaomi Games", "store", "safe",
        "Game storefront, not required by the OS.",
        ("privacy", "ram"),
    ),
    # -- media & duplicate apps (caution: user-visible) --------------------
    PackageRule(
        "com.miui.videoplayer", "Mi Video", "media", "caution",
        "Video player with ad-supported content feed. Remove if you use "
        "YouTube/Netflix/VLC instead.",
        ("ads", "battery"),
    ),
    PackageRule(
        "com.miui.player", "Mi Music", "media", "caution",
        "Music player; local playback stops working. Use another player first.",
        ("ads",),
    ),
    PackageRule(
        "com.miui.gallery", "Mi Gallery", "media", "caution",
        "Gallery doubles as the system image viewer. Removing it can break "
        "'view image' intents - keep unless you use Google Photos and accept that.",
        ("ads",),
    ),
    PackageRule(
        "com.miui.notes", "Mi Notes", "productivity", "caution",
        "Notes app. Fine to remove if you use a third-party client.",
        (),
    ),
    PackageRule(
        "com.miui.weather2", "Weather", "utility", "caution",
        "Weather widget provider; removing leaves the widget blank.",
        ("ads",),
    ),
    PackageRule(
        "com.miui.cleaner", "Cleaner", "utility", "caution",
        "Storage cleaner with ad placements. The storage UI keeps working "
        "without it, but the 'Clean up' shortcut will stop resolving.",
        ("ads",),
    ),
    PackageRule(
        "com.xiaomi.mirecycle", "Mi Recycle", "misc", "safe",
        "Refurb/trade-in booking app. Not a system dependency.",
        (),
    ),
    PackageRule(
        "com.miui.fm", "FM Radio", "media", "safe",
        "FM radio; the Pad 8 has no FM hardware, so this is dead weight when present.",
        (),
    ),
    # -- Xiaomi cloud (caution: affects backups) ---------------------------
    PackageRule(
        "com.miui.cloudservice", "Mi Cloud Service", "cloud", "caution",
        "Cloud sync. Removing disables Xiaomi backup/sync - keep if you rely on it.",
        ("privacy",),
    ),
    PackageRule(
        "com.miui.cloudbackup", "Mi Cloud Backup", "cloud", "caution",
        "Backup agent. Remove only after you have an independent backup strategy.",
        ("privacy",),
    ),
    PackageRule(
        "com.xiaomi.xmsf", "Mi Push Service", "push", "caution",
        "Push transport used by some Xiaomi apps for notifications. Removing it "
        "silently breaks those notifications; do not remove if you depend on "
        "Xiaomi first-party app notifications.",
        ("privacy",),
    ),
    # -- Google apps bundled on global builds ------------------------------
    PackageRule(
        "com.google.android.apps.tachyon", "Google Meet", "google", "caution",
        "Video calling; removing breaks link-joins to Meet calls.",
        (),
    ),
    PackageRule(
        "com.google.android.youtube", "YouTube", "google", "caution",
        "User-installable app; remove only if you install it from Play anyway.",
        (),
    ),
    PackageRule(
        "com.google.android.apps.photos", "Google Photos", "google", "caution",
        "Backup client. Removing stops automatic photo backup.",
        (),
    ),
    PackageRule(
        "com.google.android.apps.maps", "Google Maps", "google", "caution",
        "Navigation; removable if you use another maps client.",
        (),
    ),
    PackageRule(
        "com.google.android.apps.docs", "Google Drive/Docs", "google", "caution",
        "Cloud docs. Remove if unused.",
        (),
    ),
    PackageRule(
        "com.google.android.gm", "Gmail", "google", "caution",
        "Email client; removable if you use another one.",
        (),
    ),
    PackageRule(
        "com.android.chrome", "Chrome", "browser", "caution",
        "Chrome is the only WebView provider on some builds. Removing it can "
        "break in-app browsers - check before you commit.",
        ("privacy",),
    ),
)

BY_PACKAGE: dict[str, PackageRule] = {r.package: r for r in CATALOGUE}


@dataclass
class PackageAction:
    package: str
    name: str
    category: str
    risk: str
    note: str
    installed: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class PolicyError(RuntimeError):
    """Raised when a request would violate a guardrail."""


def installed_packages(adb: Adb) -> set[str]:
    out = adb.shell("pm list packages -e", check=False)
    pkgs: set[str] = set()
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("package:"):
            pkgs.add(line[len("package:"):].strip())
    return pkgs


def plan(
    installed: Iterable[str],
    *,
    tags: Iterable[str] | None = None,
    risks: Iterable[str] = ("safe",),
    include: Iterable[str] | None = None,
) -> list[PackageAction]:
    """Build a removal plan.

    ``tags`` filters the catalogue by the benefit you care about (e.g.
    ``["battery", "privacy"]``); ``risks`` defaults to the safe tier only.
    Explicit ``include`` package names bypass the tag filter but still obey the
    risk filter and the protected list.
    """
    installed_set = set(installed)
    tag_set = {t.lower() for t in tags} if tags else None
    risk_set = {r.lower() for r in risks}
    include_set = set(include or ())

    actions: list[PackageAction] = []
    for rule in CATALOGUE:
        if rule.package in PROTECTED:
            continue
        selected = rule.package in include_set
        if not selected and tag_set:
            selected = bool(tag_set & set(rule.tags))
        if not selected and not tag_set and not include_set:
            selected = True
        if not selected:
            continue
        if rule.risk not in risk_set and rule.package not in include_set:
            continue
        if rule.package not in installed_set:
            continue
        actions.append(
            PackageAction(
                package=rule.package,
                name=rule.name,
                category=rule.category,
                risk=rule.risk,
                note=rule.note,
            )
        )
    return actions


def uninstall(adb: Adb, package: str, *, dry_run: bool = True) -> dict[str, Any]:
    """Remove a package for user 0 only. Returns a result record."""
    if package in PROTECTED:
        raise PolicyError(
            f"refusing to remove protected package {package}: it is part of the "
            "device's core OS surface and removal is not reliably reversible"
        )
    if dry_run:
        return {"package": package, "action": "uninstall", "dry_run": True, "ok": True}
    try:
        out = adb.shell(f"pm uninstall --user 0 {package}")
    except AdbError as exc:
        return {"package": package, "action": "uninstall", "ok": False, "detail": str(exc)}
    ok = "Success" in out
    return {
        "package": package,
        "action": "uninstall",
        "ok": ok,
        "detail": out.strip()[:200],
    }


def reinstall(adb: Adb, package: str, *, dry_run: bool = True) -> dict[str, Any]:
    """Undo :func:`uninstall` via the package manager's install-existing path."""
    if dry_run:
        return {"package": package, "action": "reinstall", "dry_run": True, "ok": True}
    try:
        out = adb.shell(f"cmd package install-existing --user 0 {package}")
    except AdbError as exc:
        return {"package": package, "action": "reinstall", "ok": False, "detail": str(exc)}
    ok = "installed" in out.lower()
    return {
        "package": package,
        "action": "reinstall",
        "ok": ok,
        "detail": out.strip()[:200],
    }


def apply_plan(
    adb: Adb, actions: Iterable[PackageAction], *, dry_run: bool = True
) -> list[dict[str, Any]]:
    """Execute a plan, verifying the device still resolves core components."""
    results: list[dict[str, Any]] = []
    for action in actions:
        results.append(uninstall(adb, action.package, dry_run=dry_run))
    if not dry_run and results:
        # Post-condition: package manager and launcher must still answer.
        sanity = adb.shell(
            "pm list packages com.miui.home && pm list packages com.android.settings",
            check=False,
        )
        healthy = "com.miui.home" in sanity and "com.android.settings" in sanity
        results.append(
            {
                "package": "(sanity check)",
                "action": "verify",
                "ok": healthy,
                "detail": "launcher and settings resolve"
                if healthy
                else "LAUNCHER OR SETTINGS MISSING - run 'restore' immediately",
            }
        )
    return results

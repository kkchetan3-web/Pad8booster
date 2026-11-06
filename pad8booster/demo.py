"""A synthetic device, so the whole toolkit is demonstrable without hardware.

**This is simulated data.** It exists for three legitimate reasons:

1. Unit tests need a device-free transport.
2. The dashboard needs to render for a user who has not plugged in a tablet yet.
3. Reviewers can see the full report format without owning the device.

Numbers below are plausible for a Snapdragon 8s Gen 4 tablet, but they are
invented. Nothing produced by this module may be presented as a measurement of
real hardware - the CLI and the dashboard both label it ``DEMO``.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from .adb import Adb, CommandResult

DEMO_PROPS = {
    "ro.product.manufacturer": "Xiaomi",
    "ro.product.brand": "Xiaomi",
    "ro.product.model": "Xiaomi Pad 8",
    "ro.product.device": "pipa",
    "ro.product.name": "pipa_global",
    "ro.build.version.sdk": "36",
    "ro.build.version.release": "16",
    "ro.soc.manufacturer": "QTI",
    "ro.soc.model": "SM8735",
    "ro.product.cpu.abi": "arm64-v8a",
    "ro.build.id": "BP2A.260201.001",
    "ro.build.version.incremental": "OS3.0.4.0.WPYINXM",
    "ro.build.version.security_patch": "2026-09-01",
    "ro.mi.os.version.name": "V130.0.4.0.WPYINXM",
    "ro.sf.lcd_density": "320",
}

_INSTALLED = {
    "com.miui.home",
    "com.android.settings",
    "com.android.systemui",
    "com.google.android.gms",
    "com.miui.securitycenter",
    "com.miui.powerkeeper",
    "com.miui.msa.global",
    "com.miui.systemAdSolution",
    "com.miui.analytics",
    "com.xiaomi.mipicks",
    "com.mi.globalbrowser",
    "com.miui.hybrid",
    "com.miui.hybrid.accessory",
    "com.xiaomi.glgm",
    "com.miui.videoplayer",
    "com.miui.player",
    "com.miui.gallery",
    "com.miui.weather2",
    "com.miui.cleaner",
    "com.xiaomi.mirecycle",
    "com.miui.cloudservice",
    "com.xiaomi.xmsf",
    "com.google.android.youtube",
    "com.android.chrome",
    "com.google.android.apps.photos",
    "com.example.notes",
}

_DEFAULT_SETTINGS = {
    ("global", "window_animation_scale"): "1.0",
    ("global", "transition_animation_scale"): "1.0",
    ("global", "animator_duration_scale"): "1.0",
    ("global", "wifi_scan_always_enabled"): "1",
    ("global", "ble_scan_always_enabled"): "1",
    ("system", "peak_refresh_rate"): "144.0",
    ("system", "min_refresh_rate"): "60.0",
    ("system", "screen_off_timeout"): "300000",
}


#: Packages the demo's "after" phase has removed - the safe ads/telemetry tier.
_AFTER_REMOVED = {
    "com.miui.msa.global",
    "com.miui.systemAdSolution",
    "com.miui.analytics",
    "com.xiaomi.mipicks",
    "com.mi.globalbrowser",
    "com.miui.hybrid",
}


@dataclass
class DemoDevice:
    phase: str = "before"  # "before" | "after"
    seed: int = 7
    installed: set[str] = field(default_factory=lambda: set(_INSTALLED))
    settings: dict[tuple[str, str], str] = field(
        default_factory=lambda: dict(_DEFAULT_SETTINGS)
    )
    buckets: dict[str, str] = field(default_factory=dict)
    fixed_perf: bool = False
    density_override: int | None = None
    uninstalled: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        if self.phase == "after":
            self.installed -= _AFTER_REMOVED
            self.uninstalled |= _AFTER_REMOVED

    # -- simulated hardware state -----------------------------------------

    def _meminfo(self) -> str:
        total_kb = 12_027_904  # ~11.5 GiB usable on a 12 GB LPDDR5T SKU
        avail = 4_180_000 if self.phase == "before" else 6_940_000
        cached = 2_600_000 if self.phase == "before" else 3_050_000
        return (
            f"MemTotal:       {total_kb} kB\n"
            f"MemFree:          {820_000 if self.phase == 'before' else 1_910_000} kB\n"
            f"MemAvailable:   {avail} kB\n"
            f"Buffers:           62_144 kB\n"
            f"Cached:         {cached} kB\n"
            f"SwapTotal:      2_097_152 kB\n"
            f"SwapFree:       1_614_592 kB\n"
        )

    def _thermal(self) -> str:
        base = 1.4 if self.phase == "before" else 0.6
        rng = random.Random(self.seed + (0 if self.phase == "before" else 1))
        rows = []
        for index, (name, celsius) in enumerate(
            (("cpu-0-0", 41.2), ("cpu-1-0", 40.8), ("gpu-0", 39.5), ("skin", 32.1))
        ):
            value = int((celsius + base + rng.random()) * 1000)
            rows.append(f"/sys/class/thermal/thermal_zone{index}/temp={value}")
        return "\n".join(rows)

    def _battery(self) -> str:
        temp = 289 if self.phase == "before" else 273
        return (
            "Current Battery Service state:\n"
            "  AC powered: false\n"
            "  USB powered: false\n"
            "  Wireless powered: false\n"
            "  status: 2\n"
            "  health: 2\n"
            "  present: true\n"
            f"  level: {82 if self.phase == 'before' else 79}\n"
            "  scale: 100\n"
            f"  voltage: {8352 if self.phase == 'before' else 8301}\n"
            f"  temperature: {temp}\n"
            "  technology: Li-ion\n"
        )

    def _top(self) -> str:
        busy = (
            [("com.miui.msa.global", 14.2), ("com.xiaomi.mipicks", 8.7), ("system_server", 6.1)]
            if self.phase == "before"
            else [("system_server", 4.2), ("com.android.chrome", 3.1), ("surfaceflinger", 2.4)]
        )
        lines = [
            "Tasks: 612 total,   1 running, 608 sleeping",
            "  PID     USER  %CPU  ARGS",
        ]
        for index, (name, pct) in enumerate(busy):
            lines.append(f" {2100 + index}  u0_a{index}  {pct}  {name}")
        return "\n".join(lines)

    def _start_time(self, component: str) -> str:
        rng = random.Random(self.seed * 31 + len(component))
        baseline = 1180 if self.phase == "before" else 910
        total = baseline + rng.randint(-45, 65)
        return (
            "Starting: Intent { cmp=" + component + " }\n"
            "Status: ok\n"
            "LaunchState: COLD\n"
            f"TotalTime: {total}\n"
            f"WaitTime: {total + 40}\n"
        )

    # -- command dispatch --------------------------------------------------

    def run(self, argv: list[str]) -> CommandResult:
        cmd = argv[-1] if argv else ""
        ok = lambda out="": CommandResult(0, out)  # noqa: E731

        if cmd == "getprop":
            return ok("\n".join(f"[{k}]: [{v}]" for k, v in DEMO_PROPS.items()))
        if cmd == "cat /proc/meminfo":
            return ok(self._meminfo())
        if cmd == "cat /proc/loadavg":
            first = 3.42 if self.phase == "before" else 0.94
            return ok(f"{first:.2f} 2.10 1.55 3/1402 22114")
        if cmd == "dumpsys battery":
            return ok(self._battery())
        if cmd.startswith("for f in /sys/class/thermal"):
            return ok(self._thermal())
        if cmd == "cat /proc/uptime":
            return ok("184233.42 912344.11")
        if cmd == "df -h /data":
            return ok(
                "Filesystem      Size  Used Avail Use% Mounted on\n"
                f"/dev/block/dm-42 233G  {88 if self.phase == 'before' else 61}G  172G  "
                f"{38 if self.phase == 'before' else 27}% /data"
            )
        if cmd.startswith("top -b"):
            return ok(self._top())
        if cmd.startswith("pm list packages -e | wc"):
            return ok(str(len(self.installed)))
        if cmd.startswith("pm list packages -e"):
            return ok("\n".join(f"package:{p}" for p in sorted(self.installed)))
        if cmd.startswith("pm list packages "):
            return ok("\n".join(f"package:{p}" for p in sorted(self.installed)))
        if cmd.startswith("settings get"):
            _, _, namespace, key = cmd.split()
            value = self.settings.get((namespace, key), "null")
            return ok(value)
        if cmd.startswith("settings put"):
            parts = cmd.split()
            if len(parts) < 5:
                return CommandResult(1, "", "usage: settings put NAMESPACE KEY VALUE")
            namespace, key, value = parts[2], parts[3], parts[4]
            if (namespace, key) not in self.settings:
                # Simulate a build that does not support the key at all.
                return ok("")
            self.settings[(namespace, key)] = value
            return ok("")
        if cmd.startswith("am get-standby-bucket"):
            pkg = cmd.split()[-1]
            return ok(self.buckets.get(pkg, "5"))
        if cmd.startswith("am set-standby-bucket"):
            parts = cmd.split()
            self.buckets[parts[2]] = parts[3]
            return ok("")
        if cmd == "wm density":
            lines = ["Physical density: 320"]
            if self.density_override:
                lines.append(f"Override density: {self.density_override}")
            return ok("\n".join(lines))
        if cmd.startswith("wm density reset"):
            self.density_override = None
            return ok("")
        if cmd.startswith("wm density "):
            try:
                self.density_override = int(cmd.split()[-1])
            except ValueError:
                return CommandResult(1, "", "bad density")
            return ok("")
        if cmd.startswith("cmd power set-fixed-performance-mode-enabled"):
            self.fixed_perf = cmd.strip().endswith("true")
            return ok("")
        if cmd.startswith("cmd power help"):
            return ok("set-fixed-performance-mode-enabled (true|false)")
        if cmd.startswith("cmd package resolve-activity"):
            pkg = cmd.split()[-1]
            if pkg in self.installed:
                return ok(f"priority=0\n{pkg}/.MainActivity")
            return CommandResult(1, "", "No activity found")
        if cmd.startswith("am force-stop"):
            return ok("")
        if cmd.startswith("am start -W -n"):
            component = cmd.split()[-1]
            return ok(self._start_time(component))
        if cmd.startswith("pm uninstall --user 0"):
            pkg = cmd.split()[-1]
            if pkg in self.installed:
                self.installed.discard(pkg)
                self.uninstalled.add(pkg)
                return ok("Success")
            return ok("Failure [not installed for 0]")
        if cmd.startswith("cmd package install-existing"):
            pkg = cmd.split()[-1]
            self.installed.add(pkg)
            self.uninstalled.discard(pkg)
            return ok(f"Package {pkg} installed for user: 0")
        if cmd.startswith("dumpsys batterystats"):
            return ok("Battery History (2% used, 0KB used of 8MB)\n 0 (9) RESET:TIME: 0")
        if cmd.startswith("ls /sys/class/thermal"):
            return ok("cooling_device0\nthermal_zone0")
        if cmd.startswith("top -b -n 1 -o"):
            return ok(self._top())
        if cmd == "devices":
            return ok("List of devices attached\nDEMO\tdevice")
        if cmd.startswith("dumpsys gfxinfo"):
            return ok(
                "Total frames rendered: 412\n"
                "Janky frames: 18 (4.37%)\n"
                "90th percentile: 11ms\n"
                "99th percentile: 24ms\n"
            )
        return ok("")


def demo_adb(phase: str = "before", seed: int = 7) -> Adb:
    """Return an :class:`Adb` backed by the synthetic device."""
    device = DemoDevice(phase=phase, seed=seed)
    return Adb(serial="DEMO", runner=device.run, label="demo")

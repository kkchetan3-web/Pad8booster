"""Snapshot collection and parsing.

All parsers here are **pure functions over text**, so they can be unit-tested
against fixtures without a device. That separation matters: parsing bugs are the
number one source of false optimisation claims (a mis-parsed thermal zone makes
a device look cooler than it is).

Every field is optional. A metric the device will not reveal becomes ``None``,
and the report says "unavailable" rather than inventing a zero.
"""

from __future__ import annotations

import json
import re
import statistics
import time
from dataclasses import dataclass, field, asdict
from typing import Any

from .adb import Adb

_ANSI = re.compile(r"\x1b\[[0-9;]*m")


# --------------------------------------------------------------------------
# parsers
# --------------------------------------------------------------------------

def parse_meminfo(text: str) -> dict[str, int]:
    """Parse /proc/meminfo into a kb-valued dict."""
    out: dict[str, int] = {}
    for line in text.splitlines():
        m = re.match(r"^(\w+):\s+(\d+)", line)
        if m:
            out[m.group(1)] = int(m.group(2))
    return out


def mem_available_mb(pairs: dict[str, int]) -> float | None:
    kb = pairs.get("MemAvailable")
    return round(kb / 1024, 1) if isinstance(kb, int) else None


def mem_used_pct(pairs: dict[str, int]) -> float | None:
    total = pairs.get("MemTotal")
    avail = pairs.get("MemAvailable")
    if not total or not isinstance(avail, int):
        return None
    return round((total - avail) / total * 100, 1)


def parse_loadavg(text: str) -> tuple[float, float, float] | None:
    parts = text.split()
    if len(parts) < 3:
        return None
    try:
        return (float(parts[0]), float(parts[1]), float(parts[2]))
    except ValueError:
        return None


def parse_battery(text: str) -> dict[str, Any]:
    """Parse ``dumpsys battery``.

    Returns level (%), temperature in Celsius, voltage in mV, plus raw status
    strings. ``scale`` is honoured because some builds are not 0-100.
    """
    raw: dict[str, str] = {}
    for line in text.splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            raw[key.strip().lower()] = value.strip()

    result: dict[str, Any] = {}
    level = raw.get("level", "")
    scale = raw.get("scale", "100")
    try:
        result["level_pct"] = round(int(level) / max(int(scale), 1) * 100)
    except ValueError:
        result["level_pct"] = None
    try:
        result["temperature_c"] = round(int(raw["temperature"]) / 10, 1)
    except (KeyError, ValueError):
        result["temperature_c"] = None
    try:
        result["voltage_mv"] = int(raw["voltage"])
    except (KeyError, ValueError):
        result["voltage_mv"] = None
    result["status"] = raw.get("status")
    result["health"] = raw.get("health")
    result["ac_powered"] = raw.get("ac powered") == "true" or raw.get(
        "usb powered"
    ) == "true"
    return result


def parse_thermal_zones(text: str) -> dict[str, float]:
    """Parse ``zone=/path temp`` pairs emitted by the collection command.

    sysfs thermal values are millidegrees on Linux, but several Android vendor
    kernels report decis/degrees. We normalise using magnitude heuristics and
    flag implausible values out rather than reporting them as real.
    """
    zones: dict[str, float] = {}
    for line in text.splitlines():
        if "=" not in line:
            continue
        name, _, raw = line.partition("=")
        name = name.strip()
        # Key on the thermal_zoneN directory, not the "temp" leaf file.
        match = re.search(r"(thermal_zone\d+)", name)
        if match:
            key = match.group(1)
        else:
            parts = name.split("/")
            key = parts[-2] if parts and parts[-1] == "temp" and len(parts) > 1 else parts[-1]
        try:
            value = float(raw.strip())
        except ValueError:
            continue
        if value > 10000:  # millidegrees
            value /= 1000
        elif value > 200:  # decisdegrees, e.g. 423 -> 42.3
            value /= 10
        if 0 < value < 120:
            zones[key] = round(value, 1)
    return zones


def hottest_zone(zones: dict[str, float]) -> tuple[str, float] | None:
    if not zones:
        return None
    name = max(zones, key=lambda k: zones[k])
    return name, zones[name]


def parse_top_cpu(text: str, limit: int = 8) -> list[dict[str, Any]]:
    """Parse ``top -b -n 1 -o PID,%CPU,ARGS`` output tolerantly.

    Toybox and busybox emit different column orders, so we require the numeric
    first field to be a PID and locate the percentage by regex rather than
    assuming a fixed column.
    """
    rows: list[dict[str, Any]] = []
    for line in text.splitlines():
        line = _ANSI.sub("", line).strip()
        if not line or "PID" in line.upper()[:12]:
            continue
        m = re.match(r"^(\d+)\s+(.+)$", line)
        if not m:
            continue
        pid = int(m.group(1))
        rest = m.group(2)
        pct = re.search(r"(\d{1,3}(?:\.\d+)?)\s*%?", rest.split()[-2]) if len(
            rest.split()
        ) >= 2 else None
        name = rest.split()[-1]
        if pct:
            rows.append({"pid": pid, "cpu_pct": float(pct.group(1)), "name": name})
        if len(rows) >= limit:
            break
    return rows[:limit]


def parse_df(text: str) -> dict[str, float] | None:
    """Return {"used_pct": n} from ``df -h /data``.

    Skips the header and any malformed column rather than aborting the whole
    parse on the first unparsable cell (the header contains "Use%").
    """
    for line in text.splitlines():
        if not line.startswith("/dev") and not line.startswith("/"):
            continue
        for part in line.split():
            if not part.endswith("%"):
                continue
            try:
                return {"used_pct": float(part.rstrip("%"))}
            except ValueError:
                continue
    return None


def parse_frame_stats(text: str) -> dict[str, Any] | None:
    """Parse ``dumpsys gfxinfo <pkg>`` summary block.

    Janky frames and 90th percentile are the two numbers worth trusting; a
    single ``Total frames`` count is meaningless without a workload attached.
    """
    stats: dict[str, Any] = {}
    m = re.search(r"Total frames rendered:\s*(\d+)", text)
    if m:
        total = int(m.group(1))
        stats["total_frames"] = total
        j = re.search(r"Janky frames:\s*(\d+)", text)
        if j and total:
            stats["janky_pct"] = round(int(j.group(1)) / total * 100, 1)
        p90 = re.search(r"90th percentile:\s*(\d+)ms", text)
        if p90:
            stats["p90_ms"] = int(p90.group(1))
        p99 = re.search(r"99th percentile:\s*(\d+)ms", text)
        if p99:
            stats["p99_ms"] = int(p99.group(1))
    return stats or None


# --------------------------------------------------------------------------
# snapshot
# --------------------------------------------------------------------------

@dataclass
class Snapshot:
    """One point-in-time measurement of device state."""

    taken_at: str
    label: str = "unlabelled"
    battery: dict[str, Any] = field(default_factory=dict)
    memory: dict[str, Any] = field(default_factory=dict)
    thermal: dict[str, float] = field(default_factory=dict)
    loadavg: tuple[float, float, float] | None = None
    uptime_s: int | None = None
    storage: dict[str, float] | None = None
    top_cpu: list[dict[str, Any]] = field(default_factory=list)
    running_packages: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Snapshot":
        loadavg = data.get("loadavg")
        return cls(
            taken_at=data.get("taken_at", ""),
            label=data.get("label", "unlabelled"),
            battery=data.get("battery") or {},
            memory=data.get("memory") or {},
            thermal=data.get("thermal") or {},
            loadavg=tuple(loadavg) if loadavg else None,  # type: ignore[arg-type]
            uptime_s=data.get("uptime_s"),
            storage=data.get("storage"),
            top_cpu=data.get("top_cpu") or [],
            running_packages=data.get("running_packages"),
        )


def take_snapshot(adb: Adb, label: str = "unlabelled") -> Snapshot:
    """Collect every readable metric in one pass."""
    meminfo = parse_meminfo(adb.shell("cat /proc/meminfo", check=False))
    loadavg = parse_loadavg(adb.shell("cat /proc/loadavg", check=False))
    battery = parse_battery(adb.shell("dumpsys battery", check=False))
    zones_raw = adb.shell(
        'for f in /sys/class/thermal/thermal_zone*/temp; do '
        'echo "$f=$(cat $f 2>/dev/null)"; done',
        check=False,
    )
    zones = parse_thermal_zones(zones_raw)
    uptime_raw = adb.shell("cat /proc/uptime", check=False).split()
    try:
        uptime = int(float(uptime_raw[0]))
    except (IndexError, ValueError):
        uptime = None
    pkg_count_raw = adb.shell("pm list packages -e | wc -l", check=False)
    try:
        pkg_count = int(pkg_count_raw.strip())
    except ValueError:
        pkg_count = None

    return Snapshot(
        taken_at=time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        label=label,
        battery=battery,
        memory={
            "available_mb": mem_available_mb(meminfo),
            "used_pct": mem_used_pct(meminfo),
            "total_mb": round(meminfo["MemTotal"] / 1024, 1)
            if "MemTotal" in meminfo
            else None,
        },
        thermal=zones,
        loadavg=loadavg,
        uptime_s=uptime,
        storage=parse_df(adb.shell("df -h /data", check=False)),
        top_cpu=parse_top_cpu(
            adb.shell("top -b -n 1 -o PID,%CPU,ARGS 2>/dev/null", check=False)
        ),
        running_packages=pkg_count,
    )


# --------------------------------------------------------------------------
# comparison
# --------------------------------------------------------------------------

def _pct_delta(before: float | None, after: float | None) -> float | None:
    if before in (None, 0) or after is None:
        return None
    return round((after - before) / abs(before) * 100, 1)


def compare(before: Snapshot, after: Snapshot) -> dict[str, Any]:
    """Produce a machine-readable delta between two snapshots.

    ``direction`` states whether more is better, so the report can colour a
    rise in free RAM green and a rise in temperature red without the caller
    having to hardcode semantics.
    """
    rows: list[dict[str, Any]] = []

    def add(
        metric: str,
        b: float | None,
        a: float | None,
        unit: str,
        better: str,
    ) -> None:
        delta = _pct_delta(b, a)
        verdict = "flat"
        if delta is not None and abs(delta) >= 1:
            improved = (delta > 0) == (better == "higher")
            verdict = "improved" if improved else "regressed"
        rows.append(
            {
                "metric": metric,
                "before": b,
                "after": a,
                "delta_pct": delta,
                "unit": unit,
                "better": better,
                "verdict": verdict,
            }
        )

    add("Memory used", before.memory.get("used_pct"), after.memory.get("used_pct"), "%", "lower")
    add(
        "Memory available",
        before.memory.get("available_mb"),
        after.memory.get("available_mb"),
        "MB",
        "higher",
    )
    add(
        "Battery temperature",
        before.battery.get("temperature_c"),
        after.battery.get("temperature_c"),
        "C",
        "lower",
    )
    hot_b = hottest_zone(before.thermal)
    hot_a = hottest_zone(after.thermal)
    add(
        "Hottest thermal zone",
        hot_b[1] if hot_b else None,
        hot_a[1] if hot_a else None,
        "C",
        "lower",
    )
    add(
        "1-min load average",
        before.loadavg[0] if before.loadavg else None,
        after.loadavg[0] if after.loadavg else None,
        "load",
        "lower",
    )
    add(
        "Enabled packages",
        before.running_packages,
        after.running_packages,
        "pkgs",
        "lower",
    )

    improved = sum(1 for r in rows if r["verdict"] == "improved")
    regressed = sum(1 for r in rows if r["verdict"] == "regressed")
    return {
        "before_label": before.label,
        "after_label": after.label,
        "rows": rows,
        "improved": improved,
        "regressed": regressed,
        "measured": sum(1 for r in rows if r["before"] is not None),
    }


def summarise(values: list[float]) -> dict[str, float | None]:
    """Summary statistics for a timing series."""
    if not values:
        return {"n": 0, "min": None, "median": None, "mean": None, "p90": None, "max": None}
    ordered = sorted(values)
    p90_index = min(len(ordered) - 1, max(0, int(round(0.9 * len(ordered))) - 1))
    return {
        "n": len(values),
        "min": round(min(values), 1),
        "median": round(statistics.median(values), 1),
        "mean": round(statistics.fmean(values), 1),
        "p90": round(ordered[p90_index], 1),
        "max": round(max(values), 1),
    }

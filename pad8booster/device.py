"""Device identification, verification and capability detection.

Rationale: a debloat catalogue or a settings profile that is correct on a
Redmi Note and wrong on a Pad 8 is a liability. So before the toolkit will touch
anything it identifies the hardware and *verifies* it is the device the rules
were written for, then probes which of the optional capabilities are actually
available on this build.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any

from . import PAD8_MIN_SDK, PAD8_MODEL_TOKENS, PAD8_SOC_IDS
from .adb import Adb


@dataclass
class DeviceInfo:
    serial: str
    manufacturer: str = ""
    brand: str = ""
    model: str = ""
    device_codename: str = ""
    product: str = ""
    sdk: int = 0
    release: str = ""
    soc_manufacturer: str = ""
    soc_model: str = ""
    abi: str = ""
    build_id: str = ""
    incremental: str = ""
    security_patch: str = ""
    hyperos: str = ""
    density: str = ""

    @property
    def android_version(self) -> str:
        return f"{self.release} (API {self.sdk})" if self.release else f"API {self.sdk}"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Verification:
    """Result of checking a device against the Pad 8 fingerprint."""

    is_pad8: bool
    confidence: str  # "high" | "medium" | "low"
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _int(value: str, default: int = 0) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def probe(adb: Adb) -> DeviceInfo:
    """Read the property table and build a :class:`DeviceInfo`."""
    props = adb.getprop()
    return DeviceInfo(
        serial=adb.serial or props.get("ro.serialno", "default"),
        manufacturer=props.get("ro.product.manufacturer", ""),
        brand=props.get("ro.product.brand", ""),
        model=props.get("ro.product.model", ""),
        device_codename=props.get("ro.product.device", ""),
        product=props.get("ro.product.name", ""),
        sdk=_int(props.get("ro.build.version.sdk", "0")),
        release=props.get("ro.build.version.release", ""),
        soc_manufacturer=props.get("ro.soc.manufacturer", ""),
        soc_model=props.get("ro.soc.model", ""),
        abi=props.get("ro.product.cpu.abi", ""),
        build_id=props.get("ro.build.id", ""),
        incremental=props.get("ro.build.version.incremental", ""),
        security_patch=props.get("ro.build.version.security_patch", ""),
        hyperos=(
            props.get("ro.mi.os.version.name")
            or props.get("ro.miui.ui.version.name")
            or props.get("ro.build.version.incremental", "")
        ),
        density=props.get("ro.sf.lcd_density", ""),
    )


def verify_pad8(info: DeviceInfo) -> Verification:
    """Decide whether this really is a Xiaomi Pad 8 / Pad 8 Pro.

    Deliberately conservative: a *medium* verdict still allows read-only
    measurement, but destructive-ish operations require *high* confidence.
    """
    reasons: list[str] = []
    score = 0

    make = f"{info.manufacturer} {info.brand}".lower()
    if "xiaomi" in make:
        reasons.append("manufacturer is Xiaomi")
        score += 1
    else:
        reasons.append(f"manufacturer is not Xiaomi ({info.manufacturer or 'unknown'})")

    model = info.model.lower()
    if any(tok in model for tok in PAD8_MODEL_TOKENS):
        reasons.append(f'model matches "Pad 8" ({info.model})')
        score += 2
    else:
        reasons.append(f'model does not contain "Pad 8" ({info.model or "unknown"})')

    soc = (info.soc_model or "").upper()
    if any(soc.startswith(pid) for pid in PAD8_SOC_IDS):
        reasons.append(f"SoC is a Pad 8 part ({soc})")
        score += 2
    elif soc:
        reasons.append(f"SoC {soc} is not a documented Pad 8 part")

    if info.sdk >= PAD8_MIN_SDK:
        reasons.append(f"API level {info.sdk} is HyperOS 3 era")
        score += 1
    else:
        reasons.append(f"API level {info.sdk} predates HyperOS 3")

    if score >= 5:
        confidence = "high"
    elif score >= 3:
        confidence = "medium"
    else:
        confidence = "low"
    return Verification(score >= 5, confidence, reasons)


def capabilities(adb: Adb) -> dict[str, bool]:
    """Probe optional capabilities instead of assuming they exist.

    Each probe is a read-only command whose success implies the writable
    counterpart is likely to work. Anything reported ``False`` is skipped by
    the profile engine rather than attempted and half-applied.
    """
    probes = {
        # `settings` is present from API 17 onward but locked down on some builds.
        "settings_write": 'settings get global window_animation_scale',
        # Doze/standby-bucket control (App Standby Buckets, API 28+).
        "standby_buckets": 'am get-standby-bucket com.android.settings',
        # Fixed-performance mode is the only *legitimate* way to pin clocks
        # from userspace; it exists on Android 11+ but OEMs can remove it.
        "fixed_performance": 'cmd power help | grep -q set-fixed-performance-mode-enabled',
        # Thermal zone temperatures are world-readable on most Qualcomm builds.
        "thermal_zones": 'ls /sys/class/thermal/ 2>/dev/null | head -1',
        # Per-uid/per-package network + battery stats.
        "batterystats": 'dumpsys batterystats --checkin | head -1',
        # `pm list packages` is required for any package work.
        "pm": 'pm list packages -e | head -1',
    }
    result: dict[str, bool] = {}
    for name, command in probes.items():
        out = adb.shell(command, check=False)
        result[name] = bool(out) and "error" not in out.lower()[:40]
    return result

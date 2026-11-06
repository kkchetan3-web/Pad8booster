"""Cold-start benchmarking.

This is the module that makes honest claims possible. ``am start -W`` reports the
framework's own measured launch latency, so a before/after pair taken under the
same conditions is a real number from the device - not a marketing score.

Methodology enforced by the code, because a benchmark without controls is
theatre:

* every run is preceded by ``am force-stop`` (a true cold start, not a warm one)
* a settle delay lets the CPU governor ramp down between runs
* the median and p90 are reported, never the best single run
* the sample count and spread are printed with the result so you can see whether
  a difference is larger than the noise
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, asdict
from typing import Any

from .adb import Adb
from .metrics import summarise

_TOTAL = re.compile(r"TotalTime:\s*(\d+)")
_WAIT = re.compile(r"WaitTime:\s*(\d+)")


@dataclass
class LaunchResult:
    package: str
    component: str | None
    total_ms: list[int]
    wait_ms: list[int]
    error: str | None = None

    def summary(self) -> dict[str, Any]:
        return {
            "package": self.package,
            "component": self.component,
            "total": summarise([float(v) for v in self.total_ms]),
            "wait": summarise([float(v) for v in self.wait_ms]),
            "error": self.error,
        }

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["summary"] = self.summary()
        return data


def resolve_launch_component(adb: Adb, package: str) -> str | None:
    """Find the launcher activity for a package.

    ``cmd package resolve-activity`` output is verbose and version-dependent, so
    we take the last line containing a ``package/activity`` pair.
    """
    out = adb.shell(
        f"cmd package resolve-activity --brief -c android.intent.category.LAUNCHER {package}",
        check=False,
    )
    candidate = None
    for line in out.splitlines():
        line = line.strip()
        if "/" in line and " " not in line:
            candidate = line
    if candidate:
        return candidate
    # Fallback for builds where resolve-activity prints 'priority=... pkg/.Act'
    m = re.search(rf"({re.escape(package)}/[\w.$]+)", out)
    return m.group(1) if m else None


def cold_start(
    adb: Adb,
    package: str,
    *,
    runs: int = 5,
    settle_s: float = 1.5,
    sleep=time.sleep,
) -> LaunchResult:
    """Measure cold start latency ``runs`` times."""
    component = resolve_launch_component(adb, package)
    if not component:
        return LaunchResult(package, None, [], [], error="no launcher activity found")

    totals: list[int] = []
    waits: list[int] = []
    for _ in range(runs):
        adb.shell(f"am force-stop {package}", check=False)
        sleep(settle_s)
        out = adb.shell(f"am start -W -n {component}", check=False)
        t = _TOTAL.search(out)
        w = _WAIT.search(out)
        if t:
            totals.append(int(t.group(1)))
        if w:
            waits.append(int(w.group(1)))
        sleep(0.2)
    error = None if totals else "am start -W produced no TotalTime line"
    return LaunchResult(package, component, totals, waits, error)


def compare_launches(before: LaunchResult, after: LaunchResult) -> dict[str, Any]:
    """Delta between two cold-start campaigns, expressed on the median."""
    b = before.summary()["total"]["median"]
    a = after.summary()["total"]["median"]
    delta_pct = None
    speedup = None
    if b and a is not None:
        delta_pct = round((a - b) / b * 100, 1)
        speedup = round(b / a, 2) if a else None
    # Only call it an improvement if it clears the p90 spread of both samples.
    noise = max(
        (before.summary()["total"]["p90"] or 0) - (before.summary()["total"]["min"] or 0),
        (after.summary()["total"]["p90"] or 0) - (after.summary()["total"]["min"] or 0),
        0,
    )
    real_change = (
        delta_pct is not None and abs((b or 0) - (a or 0)) > noise
    )
    return {
        "package": before.package,
        "before_median_ms": b,
        "after_median_ms": a,
        "delta_pct": delta_pct,
        "speedup_x": speedup,
        "noise_band_ms": round(noise, 1),
        "verdict": (
            "significant" if real_change else "within-noise" if delta_pct is not None
            else "inconclusive"
        ),
    }

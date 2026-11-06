"""Report rendering: Markdown for humans, JSON for tooling.

The report is deliberately blunt. It prints what was measured, what the error
bars were, and what could *not* be measured on this device - because the fastest
way to lose a user's trust is to claim a win you never observed.
"""

from __future__ import annotations

import json
import time
from typing import Any, Iterable

from . import __version__
from .device import DeviceInfo, Verification
from .metrics import Snapshot, compare

_BADGE = {"improved": "🟢", "regressed": "🔴", "flat": "⚪"}


def _fmt(value: Any, unit: str = "") -> str:
    if value is None:
        return "_unavailable_"
    if isinstance(value, float):
        return f"{value:g}{unit}"
    return f"{value}{unit}"


def render_markdown(
    *,
    info: DeviceInfo,
    verdict: Verification,
    snapshots: Iterable[Snapshot] = (),
    bench_results: Iterable[dict[str, Any]] = (),
    actions: Iterable[dict[str, Any]] = (),
    notes: Iterable[str] = (),
) -> str:
    snapshots = list(snapshots)
    lines: list[str] = []
    add = lines.append

    add(f"# Pad8Booster report")
    add("")
    add(f"Generated {time.strftime('%Y-%m-%d %H:%M:%S%z')} · Pad8Booster {__version__}")
    add("")
    add("## Device")
    add("")
    add("| Field | Value |")
    add("| --- | --- |")
    for key, value in (
        ("Model", info.model),
        ("Manufacturer", info.manufacturer),
        ("Codename", info.device_codename),
        ("SoC", f"{info.soc_manufacturer} {info.soc_model}".strip()),
        ("Android", info.android_version),
        ("HyperOS build", info.hyperos),
        ("Security patch", info.security_patch),
        ("ABI", info.abi),
        ("Density", info.density),
    ):
        add(f"| {key} | {value or '—'} |")
    add("")
    add(f"**Pad 8 verification:** {verdict.confidence} confidence — "
        f"{'PASS' if verdict.is_pad8 else 'FAIL'}")
    add("")
    for reason in verdict.reasons:
        add(f"- {reason}")
    add("")

    if snapshots:
        add("## Snapshots")
        add("")
        for snap in snapshots:
            hot = max(snap.thermal.items(), key=lambda kv: kv[1]) if snap.thermal else None
            add(f"### {snap.label}  `{snap.taken_at}`")
            add("")
            add(f"- Memory: **{_fmt(snap.memory.get('used_pct'), '%')} used** "
                f"({_fmt(snap.memory.get('available_mb'), ' MB')} available of "
                f"{_fmt(snap.memory.get('total_mb'), ' MB')})")
            add(f"- Battery: {_fmt(snap.battery.get('level_pct'), '%')} · "
                f"{_fmt(snap.battery.get('temperature_c'), ' °C')} · "
                f"{_fmt(snap.battery.get('voltage_mv'), ' mV')}")
            add(f"- Hottest zone: "
                f"{_fmt(hot[1], ' °C') + f' ({hot[0]})' if hot else '_unavailable_'}")
            add(f"- Load average: "
                f"{', '.join(f'{v:.2f}' for v in snap.loadavg) if snap.loadavg else '_unavailable_'}")
            add(f"- Enabled packages: {_fmt(snap.running_packages)}")
            add(f"- `/data` used: {_fmt((snap.storage or {}).get('used_pct'), '%')}")
            if snap.top_cpu:
                add("- Top CPU consumers: " + ", ".join(
                    f"`{r['name']}` {r.get('cpu_pct', '?')}%" for r in snap.top_cpu[:5]
                ))
            add("")

        if len(snapshots) >= 2:
            delta = compare(snapshots[0], snapshots[-1])
            add("## Before / after")
            add("")
            add("| Metric | Before | After | Δ | Verdict |")
            add("| --- | --- | --- | --- | --- |")
            for row in delta["rows"]:
                badge = _BADGE.get(row["verdict"], "")
                delta_txt = (
                    f"{row['delta_pct']:+.1f}%" if row["delta_pct"] is not None else "—"
                )
                add(
                    f"| {row['metric']} | {_fmt(row['before'], ' ' + row['unit'])} | "
                    f"{_fmt(row['after'], ' ' + row['unit'])} | {delta_txt} | "
                    f"{badge} {row['verdict']} |"
                )
            add("")
            add(f"Measured {delta['measured']} metrics · {delta['improved']} improved · "
                f"{delta['regressed']} regressed.")
            add("")
            add("> Metrics with `unavailable` in both columns are not exposed by this "
                "build. They are reported, not omitted, so the gap is visible.")
            add("")

    bench_results = list(bench_results)
    if bench_results:
        add("## Cold-start benchmarks")
        add("")
        add("| Package | Before median | After median | Δ | Speed-up | Verdict |")
        add("| --- | --- | --- | --- | --- | --- |")
        for r in bench_results:
            delta_txt = (
                f"{r['delta_pct']:+.1f}%" if r.get("delta_pct") is not None else "—"
            )
            speed_txt = (
                f"{r['speedup_x']}×" if r.get("speedup_x") else "—"
            )
            add(
                f"| `{r['package']}` | {_fmt(r.get('before_median_ms'), ' ms')} | "
                f"{_fmt(r.get('after_median_ms'), ' ms')} | {delta_txt} | "
                f"{speed_txt} | {r.get('verdict', '')} |"
            )
        add("")
        add("A change smaller than the p90−min spread of either sample is reported as "
            "`within-noise`, not as a win.")
        add("")

    actions = list(actions)
    if actions:
        add("## Actions")
        add("")
        add("| Target | Action | Status | Detail |")
        add("| --- | --- | --- | --- |")
        for a in actions:
            add(
                f"| `{a.get('target', a.get('package', '?'))}` | "
                f"{a.get('kind', a.get('action', ''))} | {a.get('status', '')} | "
                f"{(a.get('description') or a.get('detail') or '')[:120]} |"
            )
        add("")

    notes = list(notes)
    if notes:
        add("## Limitations")
        add("")
        for note in notes:
            add(f"- {note}")
        add("")

    return "\n".join(lines)


def dump_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, default=str)

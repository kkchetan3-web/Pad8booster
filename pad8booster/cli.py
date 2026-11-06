"""Command-line interface.

    python -m pad8booster probe
    python -m pad8booster snapshot --label before --out before.json
    python -m pad8booster bench --package com.android.chrome --runs 7 --out b.json
    python -m pad8booster debloat plan --tags battery privacy
    python -m pad8booster debloat apply --tags battery --yes
    python -m pad8booster profile apply responsive --yes
    python -m pad8booster revert responsive
    python -m pad8booster compare before.json after.json --out report.md
    python -m pad8booster demo            # end-to-end synthetic walkthrough

Safety posture: every mutating command defaults to dry-run. ``--yes`` is
required to write anything to the device.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from . import __version__
from .adb import Adb, AdbError
from .bench import cold_start, compare_launches
from .demo import demo_adb
from .device import capabilities, probe, verify_pad8
from .metrics import Snapshot, compare, take_snapshot
from .packages import (
    CATALOGUE,
    PROTECTED,
    PolicyError,
    apply_plan,
    installed_packages,
    plan,
    reinstall,
)
from .profiles import (
    PROFILES,
    Journal,
    apply_profile,
    read_density,
    reset_density,
    revert_profile,
    set_buckets,
    set_density,
)
from .report import dump_json, render_markdown

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_DEVICE = 3
EXIT_GUARDRAIL = 4


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def _emit(payload: Any, as_json: bool) -> None:
    if as_json:
        print(dump_json(payload))
    elif isinstance(payload, str):
        print(payload)
    else:
        print(json.dumps(payload, indent=2, default=str))


def _connect(args: argparse.Namespace) -> Adb:
    if getattr(args, "demo", False):
        return demo_adb(getattr(args, "demo_phase", "before"))
    if args.adb_path:
        return Adb(serial=args.serial, adb_path=args.adb_path)
    if args.serial:
        return Adb(serial=args.serial)
    adb = Adb(serial=None)
    try:
        devices = [d for d in adb.devices() if d[1] == "device"]
    except AdbError as exc:  # pragma: no cover - env dependent
        raise SystemExit(f"error: {exc}") from exc
    if not devices:
        raise SystemExit(
            "error: no authorised device found.\n"
            "  - enable Developer options > USB debugging on the tablet\n"
            "  - accept the RSA prompt on the tablet\n"
            "  - verify with: adb devices"
        )
    if len(devices) > 1:
        names = ", ".join(d[0] for d in devices)
        raise SystemExit(f"error: multiple devices ({names}); pass --serial")
    return Adb(serial=devices[0][0])


def _require_verified(adb: Adb, args: argparse.Namespace) -> tuple[Any, Any]:
    """Gate mutating commands behind device verification."""
    info = probe(adb)
    verdict = verify_pad8(info)
    if not verdict.is_pad8 and not getattr(args, "force_device", False):
        reasons = "\n  - ".join(verdict.reasons)
        raise SystemExit(
            f"error: device failed Pad 8 verification ({verdict.confidence} confidence):\n"
            f"  - {reasons}\n"
            "Refusing to modify an unidentified device. Pass --force-device to override."
        )
    return info, verdict


def _load_snapshot_file(path: str) -> Snapshot:
    return Snapshot.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


# --------------------------------------------------------------------------
# commands
# --------------------------------------------------------------------------

def cmd_probe(args: argparse.Namespace) -> int:
    adb = _connect(args)
    info = probe(adb)
    verdict = verify_pad8(info)
    caps = capabilities(adb)
    payload = {
        "device": info.to_dict(),
        "verification": verdict.to_dict(),
        "capabilities": caps,
        "demo": bool(getattr(args, "demo", False)),
    }
    if args.json:
        _emit(payload, True)
        return EXIT_OK if verdict.is_pad8 else EXIT_DEVICE

    print(f"{info.manufacturer} {info.model}  ({info.device_codename})")
    print(f"  SoC         {info.soc_manufacturer} {info.soc_model}")
    print(f"  Android     {info.android_version}")
    print(f"  Build       {info.incremental}  patch {info.security_patch}")
    print(f"  ABI/density {info.abi} @ {info.density}")
    print(f"  Verified    {'yes' if verdict.is_pad8 else 'no'} "
          f"({verdict.confidence} confidence)")
    for reason in verdict.reasons:
        print(f"    · {reason}")
    print("  Capabilities")
    for name, available in caps.items():
        print(f"    {'✓' if available else '✗'} {name}")
    if getattr(args, "demo", False):
        print("\n  DEMO MODE: numbers are synthetic, not from real hardware.")
    return EXIT_OK if verdict.is_pad8 else EXIT_DEVICE


def cmd_snapshot(args: argparse.Namespace) -> int:
    adb = _connect(args)
    snap = take_snapshot(adb, label=args.label)
    if args.out:
        Path(args.out).write_text(snap.to_json(), encoding="utf-8")
    _emit(snap.to_dict() if args.json else _snapshot_text(snap), args.json)
    if args.out and not args.json:
        print(f"\nwritten to {args.out}")
    return EXIT_OK


def _snapshot_text(snap: Snapshot) -> str:
    hot = max(snap.thermal.items(), key=lambda kv: kv[1]) if snap.thermal else None
    return (
        f"[{snap.label}] {snap.taken_at}\n"
        f"  memory     {snap.memory.get('used_pct')}% used, "
        f"{snap.memory.get('available_mb')} MB available\n"
        f"  battery    {snap.battery.get('level_pct')}%  "
        f"{snap.battery.get('temperature_c')} C\n"
        f"  hottest    {f'{hot[1]} C ({hot[0]})' if hot else 'unavailable'}\n"
        f"  loadavg    {snap.loadavg}\n"
        f"  packages   {snap.running_packages}\n"
        f"  /data      {(snap.storage or {}).get('used_pct')}% used"
    )


def cmd_bench(args: argparse.Namespace) -> int:
    adb = _connect(args)
    result = cold_start(adb, args.package, runs=args.runs)
    payload = result.to_dict()
    if args.out:
        Path(args.out).write_text(dump_json(payload), encoding="utf-8")
    if args.json:
        _emit(payload, True)
    else:
        s = payload["summary"]["total"]
        print(f"{args.package}  (component {result.component})")
        print(f"  runs {s['n']}  min {s['min']} ms  median {s['median']} ms  "
              f"p90 {s['p90']} ms  max {s['max']} ms")
        if result.error:
            print(f"  error: {result.error}")
    return EXIT_OK if not result.error else EXIT_DEVICE


def cmd_debloat(args: argparse.Namespace) -> int:
    # 'list' is a static catalogue dump - it must work with no tablet attached.
    if args.action == "list":
        rows = [r.to_dict() for r in CATALOGUE]
        if args.json:
            _emit({"catalogue": rows, "protected": sorted(PROTECTED)}, True)
        else:
            print(f"{len(rows)} catalogue entries, {len(PROTECTED)} protected packages\n")
            for rule in CATALOGUE:
                print(f"[{rule.risk:8}] {rule.package:38} {rule.name}")
                print(f"{'':11}{rule.note}")
        return EXIT_OK

    adb = _connect(args)
    info, _ = _require_verified(adb, args)
    installed = installed_packages(adb)

    if args.action == "plan":
        actions = plan(installed, tags=args.tags, risks=args.risks)
        payload = {
            "device": f"{info.manufacturer} {info.model}",
            "count": len(actions),
            "actions": [a.to_dict() for a in actions],
        }
        if args.json:
            _emit(payload, True)
        else:
            print(f"{len(actions)} removable packages on {info.model}:\n")
            for action in actions:
                print(f"  [{action.risk:8}] {action.package:38} {action.name}")
            print("\nApply with: python -m pad8booster debloat apply "
                  f"--tags {' '.join(args.tags or ['(none)'])} --yes")
            print("Reverse with: python -m pad8booster debloat restore")
        return EXIT_OK

    if args.action == "apply":
        actions = plan(installed, tags=args.tags, risks=args.risks)
        if not actions:
            print("nothing to do: no matching installed packages")
            return EXIT_OK
        if not args.yes:
            print(f"dry run: would remove {len(actions)} packages")
            for action in actions:
                print(f"  - {action.package}")
            print("\nre-run with --yes to apply, or 'debloat restore' to undo")
            return EXIT_OK
        try:
            results = apply_plan(adb, actions, dry_run=False)
        except PolicyError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return EXIT_GUARDRAIL
        failures = [r for r in results if not r.get("ok")]
        _emit(results, args.json)
        if not args.json:
            ok_count = len(results) - len(failures)
            print(f"removed {ok_count - 1 if ok_count else 0} packages; "
                  f"{len(failures)} failures")
            for failure in failures:
                print(f"  ! {failure['package']}: {failure.get('detail', '')[:120]}")
            print("\nUndo at any time: python -m pad8booster debloat restore")
        return EXIT_OK if not failures else EXIT_DEVICE

    if args.action == "restore":
        journal = Journal.load(Path(args.state_dir) if args.state_dir else None)
        removed = sorted({e.target for e in journal.entries if e.kind == "package"})
        if not removed:
            # Fall back to catalogue entries that are currently absent.
            removed = sorted(p for p in (r.package for r in CATALOGUE) if p not in installed)
        if not removed:
            print("nothing to restore")
            return EXIT_OK
        results = [reinstall(adb, pkg, dry_run=not args.yes) for pkg in removed]
        _emit(results, args.json)
        if not args.json:
            print(f"{'would restore' if not args.yes else 'restored'} {len(results)} packages")
        return EXIT_OK

    return EXIT_USAGE


def cmd_profile(args: argparse.Namespace) -> int:
    if args.action == "list":
        payload = {
            name: {"summary": p.summary, "caveat": p.caveat, "actions": len(p.actions)}
            for name, p in PROFILES.items()
        }
        if args.json:
            _emit(payload, True)
        else:
            for name, p in PROFILES.items():
                print(f"{name}\n  {p.summary}\n  caveat: {p.caveat}\n")
        return EXIT_OK

    adb = _connect(args)
    journal = Journal.load(Path(args.state_dir) if args.state_dir else None)

    if args.action == "apply":
        if not args.name:
            print("error: profile name required", file=sys.stderr)
            return EXIT_USAGE
        _require_verified(adb, args)
        try:
            result = apply_profile(
                adb, args.name, journal, dry_run=not args.yes
            )
        except KeyError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return EXIT_USAGE
        _emit(result, args.json)
        if not args.json:
            print(f"profile '{result['profile']}': {result['applied']} applied, "
                  f"{result['rejected']} rejected")
            for row in result["results"]:
                print(f"  [{row['status']:11}] {row['description']}")
            if result["caveat"]:
                print(f"\nnote: {result['caveat']}")
            if not args.yes:
                print("\n(dry run - add --yes to apply)")
        return EXIT_OK

    if args.action == "revert":
        if not args.name:
            print("error: profile name required", file=sys.stderr)
            return EXIT_USAGE
        result = revert_profile(adb, args.name, journal, dry_run=not args.yes)
        _emit(result, args.json)
        if not args.json:
            print(f"revert '{args.name}': {len(result['results'])} entries")
            for row in result["results"]:
                print(f"  [{row['status']:9}] {row['target']} -> {row.get('restore_to')}")
        return EXIT_OK

    return EXIT_USAGE


def cmd_revert_all(args: argparse.Namespace) -> int:
    adb = _connect(args)
    journal = Journal.load(Path(args.state_dir) if args.state_dir else None)
    profiles = sorted({e.profile for e in journal.entries})
    if not profiles:
        print("journal is empty; nothing to revert")
        return EXIT_OK
    payload = {}
    for name in profiles:
        payload[name] = revert_profile(adb, name, journal, dry_run=not args.yes)
    _emit(payload, args.json)
    if not args.json:
        print(f"{'would revert' if not args.yes else 'reverted'} {len(profiles)} profiles")
    return EXIT_OK


def cmd_buckets(args: argparse.Namespace) -> int:
    adb = _connect(args)
    _require_verified(adb, args)
    journal = Journal.load(Path(args.state_dir) if args.state_dir else None)
    result = set_buckets(adb, args.package, args.bucket, journal, dry_run=not args.yes)
    _emit(result, args.json)
    return EXIT_OK


def cmd_display(args: argparse.Namespace) -> int:
    adb = _connect(args)
    journal = Journal.load(Path(args.state_dir) if args.state_dir else None)
    if not args.density and not args.reset:
        current = read_density(adb)
        payload = {"density": current}
        if args.json:
            _emit(payload, True)
        else:
            print(f"physical density {current['physical']} dpi")
            print(f"override          {current['override'] or 'none (stock)'}")
            print("\nLower density fits more content on the 11.2\" panel:")
            print("  python -m pad8booster display --density 264 --yes   # ~17% more content")
            print("  python -m pad8booster display --reset --yes")
        return EXIT_OK

    if args.reset:
        result = reset_density(adb, journal, dry_run=not args.yes)
    else:
        _require_verified(adb, args)
        try:
            result = set_density(adb, args.density, journal, dry_run=not args.yes)
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return EXIT_USAGE
    _emit(result.to_dict() if hasattr(result, "to_dict") else result, args.json)
    if not args.json:
        print(f"display density: {result['status']}")
        if not args.yes:
            print("(dry run - add --yes to apply)")
    return EXIT_OK


def cmd_compare(args: argparse.Namespace) -> int:
    before = _load_snapshot_file(args.before)
    after = _load_snapshot_file(args.after)
    delta = compare(before, after)
    payload: dict[str, Any] = {"delta": delta}

    if args.bench_before and args.bench_after:
        b = json.loads(Path(args.bench_before).read_text(encoding="utf-8"))
        a = json.loads(Path(args.bench_after).read_text(encoding="utf-8"))
        from .bench import LaunchResult

        def _load(data: dict[str, Any]) -> LaunchResult:
            return LaunchResult(
                package=data["package"],
                component=data.get("component"),
                total_ms=list(data.get("total_ms", [])),
                wait_ms=list(data.get("wait_ms", [])),
                error=data.get("error"),
            )

        payload["bench"] = [compare_launches(_load(b), _load(a))]

    if args.out:
        adb = _connect(args) if not args.offline else None
        info = probe(adb) if adb else None
        from .device import DeviceInfo, Verification

        markdown = render_markdown(
            info=info or DeviceInfo(serial="offline"),
            verdict=Verification(True, "unknown", ["comparison only, no device attached"]),
            snapshots=[before, after],
            bench_results=payload.get("bench", []),
        )
        Path(args.out).write_text(markdown, encoding="utf-8")
        print(f"report written to {args.out}")

    if args.json:
        _emit(payload, True)
    elif not args.out:
        print(dump_json(payload))
    return EXIT_OK


def cmd_demo(args: argparse.Namespace) -> int:
    """End-to-end synthetic walkthrough - the fastest way to see the format."""
    before_adb = demo_adb("before")
    after_adb = demo_adb("after")
    info = probe(before_adb)
    verdict = verify_pad8(info)

    before = take_snapshot(before_adb, label="before")
    after = take_snapshot(after_adb, label="after")

    bench_before = cold_start(before_adb, "com.android.chrome", runs=5, settle_s=0)
    bench_after = cold_start(after_adb, "com.android.chrome", runs=5, settle_s=0)

    journal = Journal.load(
        Path(args.state_dir) if args.state_dir else Path("/tmp/pad8booster-demo.json")
    )
    journal.entries = []  # demo must never touch the real recovery journal
    profile_result = apply_profile(before_adb, "responsive", journal, dry_run=True)

    markdown = render_markdown(
        info=info,
        verdict=verdict,
        snapshots=[before, after],
        bench_results=[
            compare_launches(bench_before, bench_after)
        ],
        actions=profile_result["results"],
        notes=[
            "DEMO MODE: every value in this report is synthetic test data, not a "
            "measurement of your tablet.",
            "Free-RAM and package-count deltas in the demo represent a debloat of "
            "the six ads/telemetry/storefront packages in the catalogue.",
        ],
    )
    if args.out:
        Path(args.out).write_text(markdown, encoding="utf-8")
        print(f"demo report written to {args.out}")
    else:
        print(markdown)
    return EXIT_OK


# --------------------------------------------------------------------------
# parser
# --------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pad8booster",
        description="Measurement-first optimisation toolkit for the Xiaomi Pad 8.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--serial", help="adb serial when several devices are attached")
    parser.add_argument("--adb-path", help="path to the adb binary")
    parser.add_argument("--demo", action="store_true", help="use the synthetic demo device")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--state-dir", help="override the journal directory")
    parser.add_argument(
        "--force-device",
        action="store_true",
        help="allow writes on a device that failed Pad 8 verification",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("probe", help="identify the device and probe capabilities")
    p.set_defaults(func=cmd_probe)

    p = sub.add_parser("snapshot", help="capture device state metrics")
    p.add_argument("--label", default="unlabelled")
    p.add_argument("--out", help="write JSON snapshot to this path")
    p.set_defaults(func=cmd_snapshot)

    p = sub.add_parser("bench", help="cold-start latency benchmark")
    p.add_argument("--package", required=True)
    p.add_argument("--runs", type=int, default=5)
    p.add_argument("--out", help="write JSON result to this path")
    p.set_defaults(func=cmd_bench)

    p = sub.add_parser("debloat", help="inspect, plan, apply or undo package removal")
    p.add_argument("action", choices=["list", "plan", "apply", "restore"])
    p.add_argument("--tags", nargs="*", help="battery privacy ram ads")
    p.add_argument(
        "--risks",
        nargs="*",
        default=["safe"],
        choices=["safe", "caution", "cosmetic"],
        help="risk tiers to include (default: safe)",
    )
    p.add_argument("--yes", action="store_true", help="actually modify the device")
    p.set_defaults(func=cmd_debloat)

    p = sub.add_parser("profile", help="apply or revert tuning profiles")
    p.add_argument("action", choices=["list", "apply", "revert"])
    p.add_argument("name", nargs="?", help="profile name")
    p.add_argument("--yes", action="store_true")
    p.set_defaults(func=cmd_profile)

    p = sub.add_parser("revert", help="restore every journalled change")
    p.add_argument("--yes", action="store_true")
    p.set_defaults(func=cmd_revert_all)

    p = sub.add_parser("bucket", help="assign App Standby Buckets")
    p.add_argument("--package", nargs="+", required=True)
    p.add_argument(
        "--bucket",
        required=True,
        choices=["active", "working_set", "frequent", "rare", "restricted"],
    )
    p.add_argument("--yes", action="store_true")
    p.set_defaults(func=cmd_buckets)

    p = sub.add_parser("display", help="override display density (reversible)")
    p.add_argument("--density", type=int, help="override dpi, 220-420")
    p.add_argument("--reset", action="store_true", help="restore stock density")
    p.add_argument("--yes", action="store_true")
    p.set_defaults(func=cmd_display)

    p = sub.add_parser("compare", help="diff two snapshots into a report")
    p.add_argument("before")
    p.add_argument("after")
    p.add_argument("--bench-before")
    p.add_argument("--bench-after")
    p.add_argument("--out", help="write a Markdown report")
    p.add_argument("--offline", action="store_true", help="do not probe the device")
    p.set_defaults(func=cmd_compare)

    p = sub.add_parser("demo", help="synthetic end-to-end walkthrough")
    p.add_argument("--out", help="write the demo report here")
    p.set_defaults(func=cmd_demo)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except AdbError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_DEVICE
    except PolicyError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_GUARDRAIL
    except KeyboardInterrupt:  # pragma: no cover
        print("\ninterrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

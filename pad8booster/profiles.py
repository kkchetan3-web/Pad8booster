"""Reversible tuning profiles and the state journal.

The core idea: **no optimisation is applied without first recording the value
it replaces.** That record is a journal on disk, which is what makes
``pad8booster revert`` possible even weeks later, and why this tool cannot leave
a device in a half-tuned state you cannot diagnose.

Three action kinds are supported:

``setting``  A ``settings put <ns> <key> <value>`` write, read back to verify.
``command``  An ``adb shell`` command paired with its explicit inverse.
``bucket``   App Standby Bucket assignment, read back via ``am get-standby-bucket``.

Anything whose read-back does not match the intended value is reported as
``rejected`` and does not enter the journal as applied - so a HyperOS build that
ignores a key is visible instead of silently ineffective.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Any, Iterable

from .adb import Adb, AdbError

DEFAULT_STATE_DIR = Path(
    os.environ.get("PAD8BOOSTER_STATE")
    or (Path.home() / ".local" / "state" / "pad8booster")
)


@dataclass(frozen=True)
class Action:
    kind: str  # setting | command | bucket
    target: str  # "namespace key" for settings, command for command, pkg for bucket
    value: str
    description: str
    revert_value: str = ""
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class Profile:
    name: str
    summary: str
    actions: tuple[Action, ...]
    caveat: str = ""


def _anim(scale: str) -> tuple[Action, ...]:
    return tuple(
        Action(
            "setting",
            f"global {key}",
            scale,
            f"Animation scale '{key}' = {scale}",
            tags=("responsiveness",),
        )
        for key in (
            "window_animation_scale",
            "transition_animation_scale",
            "animator_duration_scale",
        )
    )


PROFILES: dict[str, Profile] = {
    "responsive": Profile(
        name="responsive",
        summary="Halves animation scales. The single best perceived-speed win with "
        "no measurable cost to battery, thermals or frame rate.",
        actions=_anim("0.5"),
        caveat="Purely a perceived-latency change. It does not make the CPU faster; "
        "it removes time you were spending looking at transitions.",
    ),
    "instant": Profile(
        name="instant",
        summary="Disables animations entirely.",
        actions=_anim("0.0"),
        caveat="A minority of apps rely on animation callbacks to sequence work and "
        "can misbehave. Use 'responsive' if you hit that.",
    ),
    "battery": Profile(
        name="battery",
        summary="Stops always-on Wi-Fi/BLE scanning and caps the display refresh "
        "rate ceiling, which is where an idle tablet actually spends power.",
        actions=(
            Action(
                "setting", "global wifi_scan_always_enabled", "0",
                "Disable Wi-Fi scanning while Wi-Fi is off",
                tags=("battery", "privacy"),
            ),
            Action(
                "setting", "global ble_scan_always_enabled", "0",
                "Disable Bluetooth LE background scanning",
                tags=("battery", "privacy"),
            ),
            Action(
                "setting", "system peak_refresh_rate", "60.0",
                "Cap refresh rate ceiling at 60 Hz",
                tags=("battery",),
            ),
            Action(
                "setting", "system min_refresh_rate", "60.0",
                "Floor refresh rate at 60 Hz to stop downclock churn",
                tags=("battery",),
            ),
        ),
        caveat="The refresh-rate keys are honoured by AOSP and most Xiaomi builds but "
        "not all; the journal marks them 'rejected' if the read-back disagrees.",
    ),
    "performance": Profile(
        name="performance",
        summary="Enables Android's fixed-performance mode, which pins the scheduler "
        "to its top performance level instead of letting it ramp down.",
        actions=(
            Action(
                "command",
                "cmd power set-fixed-performance-mode-enabled true",
                "true",
                "Pin CPU/GPU to top performance level",
                revert_value="cmd power set-fixed-performance-mode-enabled false",
                tags=("performance",),
            ),
        ),
        caveat="Raises sustained power draw and skin temperature. It is the only "
        "legitimate userspace clock-control mechanism, and it will not survive a "
        "reboot - Android resets it on boot, which is a safety feature.",
    ),
    "developer": Profile(
        name="developer",
        summary="Keeps animations at stock but enables a longer screen-off timeout "
        "for profiling runs, so measurements are not interrupted.",
        actions=(
            Action(
                "setting", "system screen_off_timeout", "600000",
                "Screen-off timeout 10 min for measurement runs",
                tags=("workflow",),
            ),
        ),
        caveat="Set back with 'revert' when finished.",
    ),
}


@dataclass
class JournalEntry:
    kind: str
    target: str
    before: str | None
    after: str
    profile: str
    applied_at: str
    verified: bool
    revert_command: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Journal:
    path: Path
    entries: list[JournalEntry] = field(default_factory=list)

    @classmethod
    def load(cls, path: Path | None = None) -> "Journal":
        path = Path(path) if path else DEFAULT_STATE_DIR / "journal.json"
        entries: list[JournalEntry] = []
        if path.exists():
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                entries = [JournalEntry(**e) for e in raw.get("entries", [])]
            except (json.JSONDecodeError, TypeError):
                # A corrupt journal must never block recovery; keep the bad file
                # for forensics and start clean.
                path.rename(path.with_suffix(".corrupt"))
                entries = []
        return cls(path=path, entries=entries)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"version": 1, "entries": [e.to_dict() for e in self.entries]}
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def record(self, entry: JournalEntry) -> None:
        self.entries.append(entry)
        self.save()

    def for_profile(self, profile: str) -> list[JournalEntry]:
        return [e for e in self.entries if e.profile == profile]

    def latest_per_target(self) -> dict[str, JournalEntry]:
        latest: dict[str, JournalEntry] = {}
        for entry in self.entries:
            latest[f"{entry.kind}:{entry.target}"] = entry
        return latest


# --------------------------------------------------------------------------
# executors
# --------------------------------------------------------------------------

def _read_setting(adb: Adb, namespace: str, key: str) -> str | None:
    out = adb.shell(f"settings get {namespace} {key}", check=False).strip()
    return None if out in ("null", "") else out


def _normalise(value: str) -> str:
    """Treat 1 / 1.0 / true and 0 / 0.0 / false as equal for verification."""
    v = value.strip().lower()
    truthy = {"1", "1.0", "true"}
    falsy = {"0", "0.0", "false"}
    if v in truthy:
        return "1"
    if v in falsy:
        return "0"
    try:
        return str(float(v))
    except ValueError:
        return v


def apply_action(
    adb: Adb, action: Action, profile: str, journal: Journal, *, dry_run: bool = True
) -> dict[str, Any]:
    """Apply one action, verifying and journalling it."""
    record: dict[str, Any] = {
        "kind": action.kind,
        "target": action.target,
        "intended": action.value,
        "description": action.description,
        "status": "dry-run" if dry_run else "pending",
    }

    if dry_run:
        before = _peek_before(adb, action)
        record["before"] = before
        return record

    before = _peek_before(adb, action)
    record["before"] = before
    if before is not None and _normalise(before) == _normalise(action.value):
        record["status"] = "already-set"
        return record

    try:
        if action.kind == "setting":
            namespace, _, key = action.target.partition(" ")
            adb.shell(f"settings put {namespace} {key} {action.value}")
            actual = _read_setting(adb, namespace, key)
            verified = actual is not None and _normalise(actual) == _normalise(action.value)
        elif action.kind == "command":
            adb.shell(action.target)
            verified = True  # command exit is the only signal available
            actual = action.value
        elif action.kind == "bucket":
            adb.shell(f"am set-standby-bucket {action.target} {action.value}")
            actual = adb.shell(
                f"am get-standby-bucket {action.target}", check=False
            ).strip()
            verified = actual.lower() == action.value.lower()
        else:
            raise ValueError(f"unknown action kind {action.kind!r}")
    except AdbError as exc:
        record["status"] = "error"
        record["detail"] = str(exc)[:300]
        return record

    record["actual"] = actual
    record["status"] = "applied" if verified else "rejected"
    if verified:
        journal.record(
            JournalEntry(
                kind=action.kind,
                target=action.target,
                before=before,
                after=actual,
                profile=profile,
                applied_at=time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                verified=True,
                revert_command=action.revert_value or None,
            )
        )
    return record


def _peek_before(adb: Adb, action: Action) -> str | None:
    if action.kind == "setting":
        namespace, _, key = action.target.partition(" ")
        return _read_setting(adb, namespace, key)
    if action.kind == "bucket":
        return adb.shell(f"am get-standby-bucket {action.target}", check=False).strip()
    return None


def apply_profile(
    adb: Adb,
    profile_name: str,
    journal: Journal,
    *,
    dry_run: bool = True,
    skip: Iterable[str] = (),
) -> dict[str, Any]:
    profile = PROFILES.get(profile_name)
    if profile is None:
        raise KeyError(
            f"unknown profile {profile_name!r}; available: {', '.join(sorted(PROFILES))}"
        )
    skip_set = {_normalise(s) for s in skip}
    results = [
        apply_action(adb, a, profile.name, journal, dry_run=dry_run)
        for a in profile.actions
        if _normalise(a.target) not in skip_set
    ]
    return {
        "profile": profile.name,
        "summary": profile.summary,
        "caveat": profile.caveat,
        "dry_run": dry_run,
        "results": results,
        "applied": sum(1 for r in results if r["status"] == "applied"),
        "rejected": sum(1 for r in results if r["status"] == "rejected"),
    }


def revert_profile(
    adb: Adb, profile_name: str, journal: Journal, *, dry_run: bool = True
) -> dict[str, Any]:
    """Restore every value this profile originally replaced, newest first."""
    entries = journal.for_profile(profile_name)
    results: list[dict[str, Any]] = []
    for entry in reversed(entries):
        if entry.kind == "setting" and entry.before is not None:
            namespace, _, key = entry.target.partition(" ")
            if dry_run:
                results.append(
                    {
                        "target": entry.target,
                        "restore_to": entry.before,
                        "status": "dry-run",
                    }
                )
                continue
            adb.shell(f"settings put {namespace} {key} {entry.before}")
            actual = _read_setting(adb, namespace, key)
            results.append(
                {
                    "target": entry.target,
                    "restore_to": entry.before,
                    "actual": actual,
                    "status": "restored"
                    if actual is not None
                    and _normalise(actual) == _normalise(entry.before)
                    else "mismatch",
                }
            )
        elif entry.kind == "bucket" and entry.before is not None:
            if dry_run:
                results.append(
                    {"target": entry.target, "restore_to": entry.before, "status": "dry-run"}
                )
                continue
            adb.shell(f"am set-standby-bucket {entry.target} {entry.before}")
            results.append(
                {"target": entry.target, "restore_to": entry.before, "status": "restored"}
            )
        elif entry.kind == "command":
            if entry.revert_command:
                if dry_run:
                    results.append(
                        {
                            "target": entry.target,
                            "restore_cmd": entry.revert_command,
                            "status": "dry-run",
                        }
                    )
                    continue
                try:
                    adb.shell(entry.revert_command)
                except AdbError as exc:
                    results.append(
                        {"target": entry.target, "status": "error", "detail": str(exc)[:200]}
                    )
                    continue
                results.append(
                    {
                        "target": entry.target,
                        "restore_cmd": entry.revert_command,
                        "status": "restored",
                    }
                )
            else:
                results.append(
                    {
                        "target": entry.target,
                        "status": "manual",
                        "detail": "no automated inverse recorded; revert by hand",
                    }
                )
    if not dry_run:
        remaining = [e for e in journal.entries if e.profile != profile_name]
        journal.entries = remaining
        journal.save()
    return {"profile": profile_name, "results": results, "dry_run": dry_run}


def set_buckets(
    adb: Adb,
    packages: Iterable[str],
    bucket: str,
    journal: Journal,
    *,
    dry_run: bool = True,
) -> dict[str, Any]:
    """Assign App Standby Buckets - the real mechanism behind 'background limits'.

    ``restricted`` makes an app's jobs and alarms fire almost never (great for a
    rarely-used storefront app, disastrous for a messenger), while ``active``
    protects an app you rely on from aggressive doze.
    """
    if bucket not in {"active", "working_set", "frequent", "rare", "restricted"}:
        raise ValueError(f"invalid standby bucket {bucket!r}")
    results = [
        apply_action(
            adb,
            Action(
                "bucket",
                pkg,
                bucket,
                f"Set standby bucket of {pkg} to {bucket}",
                tags=("battery",),
            ),
            profile=f"bucket:{bucket}",
            journal=journal,
            dry_run=dry_run,
        )
        for pkg in packages
    ]
    return {
        "bucket": bucket,
        "dry_run": dry_run,
        "results": results,
        "applied": sum(1 for r in results if r["status"] == "applied"),
    }


# --------------------------------------------------------------------------
# display overrides
# --------------------------------------------------------------------------

def read_density(adb: Adb) -> dict[str, int | None]:
    """Read physical and override display density via ``wm density``."""
    out = adb.shell("wm density", check=False)
    import re as _re

    physical = _re.search(r"Physical density:\s*(\d+)", out)
    override = _re.search(r"Override density:\s*(\d+)", out)
    return {
        "physical": int(physical.group(1)) if physical else None,
        "override": int(override.group(1)) if override else None,
    }


def set_density(
    adb: Adb,
    density: int,
    journal: Journal,
    *,
    dry_run: bool = True,
) -> dict[str, Any]:
    """Override display density.

    Lower density = more content on an 11.2" 3200x2136 panel, which is the single
    largest productivity change available on any Android tablet. Reversible with
    ``wm density reset``. Values below ~220 make touch targets unusably small and
    above ~420 waste the panel, so they are refused.
    """
    if not 220 <= density <= 420:
        raise ValueError(
            f"density {density} is outside the usable range 220-420 for this panel"
        )
    current = read_density(adb)
    before = str(current["override"]) if current["override"] else None
    record: dict[str, Any] = {
        "kind": "command",
        "target": "wm density",
        "intended": str(density),
        "before": before,
        "description": f"Display density {before or current['physical']} -> {density}",
        "status": "dry-run" if dry_run else "pending",
    }
    if dry_run:
        return record
    try:
        adb.shell(f"wm density {density}")
    except AdbError as exc:
        record["status"] = "error"
        record["detail"] = str(exc)[:200]
        return record
    after = read_density(adb)
    verified = after["override"] == density
    record["actual"] = after["override"]
    record["status"] = "applied" if verified else "rejected"
    if verified:
        journal.record(
            JournalEntry(
                kind="command",
                target="wm density",
                before=before,
                after=str(density),
                profile="display",
                applied_at=time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                verified=True,
                revert_command="wm density reset",
            )
        )
    return record


def reset_density(adb: Adb, journal: Journal, *, dry_run: bool = True) -> dict[str, Any]:
    if dry_run:
        return {"kind": "command", "target": "wm density reset", "status": "dry-run"}
    adb.shell("wm density reset")
    for entry in [e for e in journal.entries if e.profile == "display"]:
        journal.entries.remove(entry)
    journal.save()
    return {"kind": "command", "target": "wm density reset", "status": "restored"}

"""ADB transport layer.

Every device interaction in this project funnels through :class:`Adb`, which
wraps the ``adb`` binary but accepts an injectable *runner*. That single seam is
what makes the whole toolkit testable on a machine with no tablet attached, and
is what powers the dashboard's demo mode.

Design notes
------------
* No third-party dependencies. ``subprocess`` only, so the toolkit runs on any
  Python 3.9+ install with the platform-tools on ``PATH``.
* Failures raise :class:`AdbError` with the exact command and stderr, because
  silently returning ``""`` from a shell call is how tools end up lying about
  the state of a device.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from typing import Callable, Sequence


class AdbError(RuntimeError):
    """Raised when an adb invocation fails or adb is unusable."""


@dataclass
class CommandResult:
    """Minimal, dependency-free stand-in for ``subprocess.CompletedProcess``."""

    returncode: int
    stdout: str
    stderr: str = ""

    @property
    def ok(self) -> bool:
        return self.returncode == 0


#: Signature of a runner: takes an argv list, returns a CommandResult.
Runner = Callable[[Sequence[str]], CommandResult]


def subprocess_runner(timeout: float = 60.0) -> Runner:
    """Build a runner that shells out to the real ``adb`` binary."""

    def _run(argv: Sequence[str]) -> CommandResult:
        try:
            proc = subprocess.run(  # noqa: S603 - argv is a list, never a string
                list(argv),
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except FileNotFoundError as exc:  # pragma: no cover - env dependent
            raise AdbError(
                "adb executable not found. Install Android platform-tools and "
                "ensure 'adb' is on PATH (or pass --adb-path)."
            ) from exc
        except subprocess.TimeoutExpired as exc:  # pragma: no cover - env dependent
            raise AdbError(f"adb timed out after {timeout}s: {' '.join(argv)}") from exc
        return CommandResult(proc.returncode, proc.stdout, proc.stderr)

    return _run


class Adb:
    """Thin, strict wrapper around the adb client."""

    def __init__(
        self,
        serial: str | None = None,
        adb_path: str | None = None,
        timeout: float = 60.0,
        runner: Runner | None = None,
        label: str = "device",
    ) -> None:
        self.adb_path = adb_path or shutil.which("adb") or "adb"
        self.serial = serial
        self.timeout = timeout
        self._runner: Runner = runner or subprocess_runner(timeout)
        self.label = label

    # -- low level ---------------------------------------------------------

    def _argv(self, args: Sequence[str]) -> list[str]:
        argv = [self.adb_path]
        if self.serial:
            argv += ["-s", self.serial]
        argv += list(args)
        return argv

    def run(self, *args: str) -> CommandResult:
        result = self._runner(self._argv(args))
        if not result.ok:
            raise AdbError(
                f"adb {' '.join(args)} failed ({result.returncode}): "
                f"{(result.stderr or result.stdout).strip()[:400]}"
            )
        return result

    def try_run(self, *args: str) -> CommandResult:
        """Run without raising. Used for capability probes."""
        return self._runner(self._argv(args))

    # -- public surface ----------------------------------------------------

    def devices(self) -> list[tuple[str, str]]:
        out = self.run("devices").stdout
        found: list[tuple[str, str]] = []
        for line in out.splitlines()[1:]:
            line = line.strip()
            if not line or "\t" not in line:
                continue
            serial, state = line.split("\t", 1)
            found.append((serial.strip(), state.strip()))
        return found

    def shell(self, command: str, *, check: bool = True) -> str:
        """Run a shell command on the device and return stdout.

        ``check=False`` returns stderr-inclusive output instead of raising,
        which is what you want when reading files that may not exist on a
        given HyperOS build.
        """
        result = self.try_run("shell", command)
        if check and not result.ok:
            raise AdbError(
                f"shell command failed ({result.returncode}): {command}\n"
                f"{(result.stderr or result.stdout).strip()[:400]}"
            )
        if not result.ok:
            return (result.stdout + result.stderr).strip()
        # adb shell converts \n -> \r\n on many setups; normalise it once here
        # so every parser downstream sees clean text.
        return result.stdout.replace("\r\n", "\n").strip()

    def getprop(self) -> dict[str, str]:
        """Return the full property table as a dict."""
        out = self.shell("getprop")
        props: dict[str, str] = {}
        for line in out.splitlines():
            if not line.startswith("[") or "]: [" not in line:
                continue
            key, _, rest = line[1:].partition("]: [")
            props[key] = rest[:-1] if rest.endswith("]") else rest
        return props

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return f"Adb(serial={self.serial!r}, adb_path={self.adb_path!r})"

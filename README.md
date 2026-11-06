# Pad8Booster

**A measurement-first optimisation toolkit and transformation playbook for the Xiaomi Pad 8 / Pad 8 Pro.**

No root. No custom ROM. No "20× faster" nonsense. Every change is reversible, journalled, and
verified against the device — and every claim you see comes from a before/after measurement on
your own tablet.

```
pip install -e .
python -m pad8booster probe
```

---

## Why this exists

The Play Store is full of "booster" and "cleaner" apps that claim multipliers, flush RAM that
Android was using as cache, and kill background processes that then cold-start and burn more
battery. On a device with no practical bootloader-unlock path (HyperOS 3 gates it behind daily
quotas and one-device-per-account-per-year limits), none of them can do what they advertise.

This does the opposite: it applies the changes that genuinely exist at ADB/Shizuku level,
records what it replaced, and gives you the instrument to prove whether anything improved.

| Capability | Command |
| --- | --- |
| Identify + verify the device, probe which optional interfaces exist | `probe` |
| Snapshot memory, thermal, battery, load, storage, top CPU | `snapshot` |
| Cold-start benchmark with median/p90 and a noise band | `bench` |
| Curated debloat with hard-protected packages and full restore | `debloat plan/apply/restore` |
| Reversible tuning profiles (animation, refresh, scans, perf mode) | `profile apply/revert` |
| App Standby Bucket control — the real "background app management" | `bucket` |
| Display density override (the biggest tablet productivity lever) | `display` |
| Before/after Markdown report with honest verdicts | `compare` |
| Local dashboard | `python3 web/server.py` |

---

## Install

```bash
git clone https://github.com/kkchetan3-web/Pad8booster.git
cd Pad8booster
pip install -e .          # or: pip install -r requirements.txt
adb devices               # confirm the tablet is authorised
```

Requirements: Python 3.9+, Android platform-tools (`adb`) on `PATH`, USB debugging enabled.
The toolkit has **zero runtime dependencies** — standard library only.

Optional: [Shizuku](https://shizuku.rikka.app/) 13.6.0+ for on-device operation without a PC tether.

---

## Quickstart

```bash
# 1. Baseline (never skip this)
python -m pad8booster probe
python -m pad8booster snapshot --label before --out before.json
python -m pad8booster bench --package com.android.chrome --runs 7 --out bench-before.json

# 2. Preview, then apply the safe debloat tier
python -m pad8booster debloat plan --tags battery privacy
python -m pad8booster debloat apply --tags battery privacy --yes

# 3. Retune
python -m pad8booster profile apply responsive --yes
python -m pad8booster display --density 280 --yes

# 4. Prove it
python -m pad8booster snapshot --label after --out after.json
python -m pad8booster compare before.json after.json \
    --bench-before bench-before.json --bench-after bench-after.json \
    --offline --out report.md

# 5. Undo anything, any time
python -m pad8booster revert --yes
python -m pad8booster debloat restore --yes
```

No tablet handy? `python -m pad8booster demo` runs the entire pipeline against a synthetic device
and writes a full report. `python3 web/server.py` serves the dashboard on `0.0.0.0:8000`.

---

## The transformation playbook

**[docs/PAD8_TRANSFORMATION_PLAYBOOK.md](docs/PAD8_TRANSFORMATION_PLAYBOOK.md)** — the full
answer, in tiers: verified hardware facts, the privilege map and why root is off the table,
debloat catalogue, OS retuning, turning it into a Linux/Workstation-Mode machine, theming,
privacy hardening, anti-patterns, expected results with verification, a 90-minute execution
order, and rollback.

Read it first. The tool implements it.

---

## Safety model

Three rules are enforced in code, not documentation:

1. **Verify before writing.** Mutating commands refuse to run unless `probe` identifies a
   Xiaomi Pad 8 with high confidence (`--force-device` to override).
2. **Catalogue only.** Only packages listed with an explicit risk tier can be removed, and
   `PROTECTED` packages (21 of them: launcher, settings, systemui, GMS, powerkeeper…) can never
   be removed by any flag.
3. **Always reversible.** Package removal is per-user (`pm uninstall --user 0`), restored with
   `cmd package install-existing`. Settings writes record the prior value in a journal before
   writing, and read back afterwards — a key the build ignores is reported `rejected`, never
   silently "applied".

Shizuku grants shell-level access, which is close to root for practical purposes. Authorise only
tools you trust, and stop the service when you're done.

---

## Architecture

```
pad8booster/
  adb.py        transport with an injectable runner  → the only place that shells out
  device.py     property parsing, Pad 8 verification, capability probing
  metrics.py    pure-function parsers + snapshot/compare (no device access)
  bench.py      controlled cold-start benchmarking with noise-band verdicts
  packages.py   debloat catalogue, guardrails, uninstall/restore
  profiles.py   reversible actions, state journal, density override
  report.py     Markdown/JSON rendering
  cli.py        argparse surface
  demo.py       synthetic device (clearly labelled) for tests, demo, dashboard
web/
  server.py     stdlib HTTP server + JSON API
  index.html    single-page dashboard, no build step
tests/          52 tests, device-free
```

The `Runner` seam in `adb.py` is why the whole stack is testable without hardware: every test
drives a fake device through the same code path the real one takes.

```bash
python -m pytest -q      # 52 passed
```

---

## Limitations — stated plainly

- **Not compiled against Android.** This is a host-side toolkit driving `adb`; there is no APK.
  A native Compose companion app would need a JDK/Gradle/Android SDK, none of which were
  available in the environment this was built in.
- **Demo numbers are synthetic.** `demo.py` invents plausible values for tests and the dashboard.
  They are labelled DEMO everywhere and are never a measurement of real hardware.
- **Untested on physical hardware.** The logic is unit-tested end-to-end against the fake device,
  but no Pad 8 was attached. Field differences are handled by capability probing rather than
  assumption; if a key is rejected on your build, the tool tells you.
- **Package names vary by region.** The catalogue is matched against what's actually installed;
  entries that don't exist on your build are skipped, not failed.
- **No root features.** Deliberate. See §2 of the playbook.
- **No licence set yet.** Add one before distributing.

---

## References

Verified sources are listed in [§13 of the playbook](docs/PAD8_TRANSFORMATION_PLAYBOOK.md#13-sources).

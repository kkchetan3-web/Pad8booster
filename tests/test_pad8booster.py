"""Test suite for Pad8Booster.

Run with:  python -m pytest -q
All tests are device-free: they exercise parsers against text fixtures and the
full stack against the synthetic device in ``pad8booster.demo``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pad8booster import bench, device, metrics, packages, profiles
from pad8booster.adb import Adb, AdbError, CommandResult
from pad8booster.demo import DemoDevice, demo_adb


# --------------------------------------------------------------------------
# fixtures
# --------------------------------------------------------------------------

MEMINFO = """MemTotal:       12027904 kB
MemFree:          820000 kB
MemAvailable:    4180000 kB
Buffers:           62144 kB
Cached:          2600000 kB
"""

BATTERY = """Current Battery Service state:
  AC powered: false
  status: 2
  health: 2
  level: 82
  scale: 100
  voltage: 8352
  temperature: 289
"""

THERMAL_MILLI = """\
/sys/class/thermal/thermal_zone0/temp=41200
/sys/class/thermal/thermal_zone1/temp=39500
/sys/class/thermal/thermal_zone2/temp=0
"""

THERMAL_DECI = """\
/sys/class/thermal/thermal_zone0/temp=423
/sys/class/thermal/thermal_zone1/temp=310
"""

GFXINFO = """Total frames rendered: 412
Janky frames: 18 (4.37%)
90th percentile: 11ms
99th percentile: 24ms
"""


# --------------------------------------------------------------------------
# parsers
# --------------------------------------------------------------------------

def test_meminfo_parsing_and_derived_metrics():
    pairs = metrics.parse_meminfo(MEMINFO)
    assert pairs["MemTotal"] == 12027904
    assert metrics.mem_available_mb(pairs) == pytest.approx(4082.0, abs=0.2)
    used = metrics.mem_used_pct(pairs)
    assert 64.0 < used < 66.0


def test_meminfo_tolerates_missing_keys():
    assert metrics.mem_available_mb({}) is None
    assert metrics.mem_used_pct({"MemTotal": 100}) is None


def test_battery_parsing_converts_tenths_to_celsius():
    parsed = metrics.parse_battery(BATTERY)
    assert parsed["level_pct"] == 82
    assert parsed["temperature_c"] == 28.9
    assert parsed["voltage_mv"] == 8352
    assert parsed["ac_powered"] is False


def test_battery_parsing_survives_garbage():
    parsed = metrics.parse_battery("nonsense")
    assert parsed["level_pct"] is None
    assert parsed["temperature_c"] is None


def test_thermal_normalises_millidegrees():
    zones = metrics.parse_thermal_zones(THERMAL_MILLI)
    assert zones["thermal_zone0"] == pytest.approx(41.2)
    assert zones["thermal_zone1"] == pytest.approx(39.5)
    assert "thermal_zone2" not in zones  # 0 raw value is discarded, not reported


def test_thermal_normalises_decisdegrees():
    zones = metrics.parse_thermal_zones(THERMAL_DECI)
    assert zones["thermal_zone0"] == pytest.approx(42.3)
    assert zones["thermal_zone1"] == pytest.approx(31.0)


def test_thermal_rejects_implausible_values():
    # 99,999,999 millidegrees = ~100,000 C: dropped, not reported.
    zones = metrics.parse_thermal_zones("a/temp=99999999\nb/temp=abc\nc/temp=-5")
    assert zones == {}


def test_thermal_keys_on_zone_directory():
    zones = metrics.parse_thermal_zones("gpu-0/temp=39500")
    assert zones == {"gpu-0": 39.5}


def test_hottest_zone_selection():
    assert metrics.hottest_zone({"a": 30.0, "b": 44.5}) == ("b", 44.5)
    assert metrics.hottest_zone({}) is None


def test_loadavg_parsing():
    assert metrics.parse_loadavg("3.42 2.10 1.55 3/1402 22114") == (3.42, 2.10, 1.55)
    assert metrics.parse_loadavg("garbage") is None


def test_gfxinfo_frame_stats():
    stats = metrics.parse_frame_stats(GFXINFO)
    assert stats["total_frames"] == 412
    assert stats["janky_pct"] == pytest.approx(4.4, abs=0.1)
    assert stats["p90_ms"] == 11
    assert metrics.parse_frame_stats("nope") is None


def test_df_parsing():
    text = (
        "Filesystem      Size  Used Avail Use% Mounted on\n"
        "/dev/block/dm-42 233G  88G  172G  38% /data"
    )
    assert metrics.parse_df(text) == {"used_pct": 38.0}


# --------------------------------------------------------------------------
# comparison semantics
# --------------------------------------------------------------------------

def test_compare_labels_direction_correctly():
    before = metrics.Snapshot(
        taken_at="t0",
        label="before",
        battery={"temperature_c": 33.0},
        memory={"used_pct": 70.0, "available_mb": 4000.0},
        thermal={"cpu": 44.0},
        loadavg=(3.4, 2.0, 1.0),
        running_packages=200,
    )
    after = metrics.Snapshot(
        taken_at="t1",
        label="after",
        battery={"temperature_c": 30.0},
        memory={"used_pct": 55.0, "available_mb": 6000.0},
        thermal={"cpu": 41.0},
        loadavg=(1.1, 1.0, 1.0),
        running_packages=194,
    )
    delta = metrics.compare(before, after)
    verdicts = {row["metric"]: row["verdict"] for row in delta["rows"]}
    assert verdicts["Memory used"] == "improved"
    assert verdicts["Memory available"] == "improved"
    assert verdicts["Battery temperature"] == "improved"
    assert verdicts["Enabled packages"] == "improved"
    assert delta["regressed"] == 0
    assert delta["improved"] >= 5


def test_compare_marks_regression():
    before = metrics.Snapshot("t0", memory={"used_pct": 50.0})
    after = metrics.Snapshot("t1", memory={"used_pct": 80.0})
    rows = {r["metric"]: r for r in metrics.compare(before, after)["rows"]}
    assert rows["Memory used"]["verdict"] == "regressed"
    assert rows["Memory used"]["delta_pct"] == 60.0


def test_compare_reports_unavailable_instead_of_zero():
    before = metrics.Snapshot("t0")
    after = metrics.Snapshot("t1")
    delta = metrics.compare(before, after)
    assert delta["measured"] == 0
    assert all(row["delta_pct"] is None for row in delta["rows"])


def test_summarise_statistics():
    stats = metrics.summarise([100.0, 120.0, 300.0, 140.0])
    assert stats["n"] == 4
    assert stats["median"] == 130.0
    assert stats["max"] == 300.0
    assert stats["p90"] is not None


def test_summarise_empty():
    assert metrics.summarise([])["n"] == 0


# --------------------------------------------------------------------------
# device verification
# --------------------------------------------------------------------------

def test_demo_device_verifies_as_pad8():
    info = device.probe(demo_adb())
    verdict = device.verify_pad8(info)
    assert info.model == "Xiaomi Pad 8"
    assert info.soc_model == "SM8735"
    assert verdict.is_pad8 is True
    assert verdict.confidence == "high"


def test_foreign_device_fails_verification():
    device_info = device.DeviceInfo(
        serial="x",
        manufacturer="samsung",
        model="SM-X910",
        soc_model="SM8550",
        sdk=36,
    )
    verdict = device.verify_pad8(device_info)
    assert verdict.is_pad8 is False
    assert verdict.confidence == "low"


def test_capabilities_detects_missing_command():
    adb = demo_adb()
    caps = device.capabilities(adb)
    assert caps["settings_write"] is True
    assert caps["fixed_performance"] is True
    assert caps["pm"] is True


# --------------------------------------------------------------------------
# debloat guardrails
# --------------------------------------------------------------------------

def test_protected_packages_never_removable():
    for protected in ("com.miui.home", "com.google.android.gms", "com.android.systemui"):
        with pytest.raises(packages.PolicyError):
            packages.uninstall(demo_adb(), protected, dry_run=False)


def test_plan_excludes_protected_even_if_installed():
    installed = packages.installed_packages(demo_adb())
    assert "com.miui.home" in installed
    for action in packages.plan(installed, risks=["safe", "caution"]):
        assert action.package not in packages.PROTECTED


def test_default_plan_is_safe_tier_only():
    installed = packages.installed_packages(demo_adb())
    actions = packages.plan(installed)
    assert actions, "demo device should have removable safe packages"
    assert {a.risk for a in actions} == {"safe"}


def test_plan_filters_by_tag():
    installed = packages.installed_packages(demo_adb())
    actions = packages.plan(installed, tags=["privacy"])
    pkgs = {a.package for a in actions}
    assert "com.miui.analytics" in pkgs
    assert "com.miui.msa.global" in pkgs
    assert "com.xiaomi.mirecycle" not in pkgs


def test_plan_ignores_packages_not_installed():
    actions = packages.plan({"com.miui.analytics"})
    assert [a.package for a in actions] == ["com.miui.analytics"]


def test_apply_plan_removes_and_is_reversible():
    dev = DemoDevice()
    adb = Adb(serial="DEMO", runner=dev.run)
    actions = packages.plan(dev.installed, tags=["privacy"])
    results = packages.apply_plan(adb, actions, dry_run=False)

    removed = [r["package"] for r in results if r["action"] == "uninstall" and r["ok"]]
    assert removed
    assert all(p not in dev.installed for p in removed)
    sanity = [r for r in results if r["action"] == "verify"][0]
    assert sanity["ok"] is True

    for pkg in removed:
        assert packages.reinstall(adb, pkg, dry_run=False)["ok"] is True
        assert pkg in dev.installed


def test_dry_run_does_not_touch_device():
    dev = DemoDevice()
    adb = Adb(serial="DEMO", runner=dev.run)
    before = set(dev.installed)
    packages.apply_plan(adb, packages.plan(dev.installed), dry_run=True)
    assert dev.installed == before


# --------------------------------------------------------------------------
# profiles and the journal
# --------------------------------------------------------------------------

def test_profile_apply_records_reversible_journal(tmp_path):
    dev = DemoDevice()
    adb = Adb(serial="DEMO", runner=dev.run)
    journal = profiles.Journal.load(tmp_path / "journal.json")

    result = profiles.apply_profile(adb, "responsive", journal, dry_run=False)
    assert result["applied"] == 3
    assert dev.settings[("global", "window_animation_scale")] == "0.5"
    assert len(journal.entries) == 3
    assert journal.path.exists()

    restored = profiles.revert_profile(adb, "responsive", journal, dry_run=False)
    assert all(r["status"] == "restored" for r in restored["results"])
    assert dev.settings[("global", "window_animation_scale")] == "1.0"
    assert profiles.Journal.load(journal.path).entries == []


def test_profile_reports_rejected_keys_instead_of_lying(tmp_path):
    dev = DemoDevice()
    adb = Adb(serial="DEMO", runner=dev.run)
    journal = profiles.Journal.load(tmp_path / "j.json")
    # Remove the key so the simulated build silently discards the write.
    del dev.settings[("system", "peak_refresh_rate")]
    result = profiles.apply_profile(adb, "battery", journal, dry_run=False)
    statuses = [r["status"] for r in result["results"]]
    assert "rejected" in statuses
    rejected = [r for r in result["results"] if r["status"] == "rejected"]
    assert rejected[0]["target"] == "system peak_refresh_rate"
    # A rejected action must never enter the recovery journal.
    assert all(e.target != "system peak_refresh_rate" for e in journal.entries)


def test_profile_dry_run_is_side_effect_free(tmp_path):
    dev = DemoDevice()
    adb = Adb(serial="DEMO", runner=dev.run)
    journal = profiles.Journal.load(tmp_path / "j.json")
    original = dict(dev.settings)
    result = profiles.apply_profile(adb, "battery", journal, dry_run=True)
    assert all(r["status"] == "dry-run" for r in result["results"])
    assert dev.settings == original
    assert journal.entries == []


def test_already_set_values_are_not_journalled(tmp_path):
    dev = DemoDevice()
    dev.settings[("global", "window_animation_scale")] = "0.5"
    adb = Adb(serial="DEMO", runner=dev.run)
    journal = profiles.Journal.load(tmp_path / "j.json")
    result = profiles.apply_profile(adb, "responsive", journal, dry_run=False)
    assert any(r["status"] == "already-set" for r in result["results"])


def test_unknown_profile_raises():
    journal = profiles.Journal.load(Path("/tmp/none.json"))
    with pytest.raises(KeyError):
        profiles.apply_profile(demo_adb(), "turbo9000", journal)


def test_corrupt_journal_is_quarantined_not_fatal(tmp_path):
    path = tmp_path / "journal.json"
    path.write_text("{not json", encoding="utf-8")
    journal = profiles.Journal.load(path)
    assert journal.entries == []
    assert path.with_suffix(".corrupt").exists()


def test_standby_bucket_roundtrip(tmp_path):
    dev = DemoDevice()
    adb = Adb(serial="DEMO", runner=dev.run)
    journal = profiles.Journal.load(tmp_path / "j.json")
    result = profiles.set_buckets(adb, ["com.xiaomi.mipicks"], "restricted", journal, dry_run=False)
    assert result["applied"] == 1
    assert dev.buckets["com.xiaomi.mipicks"] == "restricted"
    profiles.revert_profile(adb, "bucket:restricted", journal, dry_run=False)
    assert dev.buckets["com.xiaomi.mipicks"] == "5"


def test_invalid_bucket_rejected():
    journal = profiles.Journal.load(Path("/tmp/none2.json"))
    with pytest.raises(ValueError):
        profiles.set_buckets(demo_adb(), ["x"], "turbo", journal)


# --------------------------------------------------------------------------
# benchmarks
# --------------------------------------------------------------------------

def test_cold_start_measures_all_runs():
    result = bench.cold_start(demo_adb(), "com.android.chrome", runs=3, settle_s=0)
    assert len(result.total_ms) == 3
    assert all(100 < t < 5000 for t in result.total_ms)
    assert result.component.endswith(".MainActivity")


def test_cold_start_handles_missing_component():
    adb = demo_adb()
    result = bench.cold_start(adb, "com.not.installed", runs=2, settle_s=0)
    assert result.total_ms == []
    assert result.error is not None


def test_benchmark_delta_detects_improvement():
    before = bench.cold_start(demo_adb("before"), "com.android.chrome", runs=5, settle_s=0)
    after = bench.cold_start(demo_adb("after"), "com.android.chrome", runs=5, settle_s=0)
    delta = bench.compare_launches(before, after)
    assert delta["after_median_ms"] < delta["before_median_ms"]
    assert delta["speedup_x"] > 1.0
    assert delta["verdict"] in {"significant", "within-noise"}


def test_benchmark_identical_samples_is_within_noise():
    a = bench.cold_start(demo_adb(), "com.android.chrome", runs=4, settle_s=0)
    b = bench.cold_start(demo_adb(), "com.android.chrome", runs=4, settle_s=0)
    delta = bench.compare_launches(a, b)
    assert delta["delta_pct"] == pytest.approx(0.0, abs=0.1)


# --------------------------------------------------------------------------
# snapshots, transport, CLI
# --------------------------------------------------------------------------

def test_snapshot_roundtrip_through_json():
    snap = metrics.take_snapshot(demo_adb("before"), label="before")
    restored = metrics.Snapshot.from_dict(json.loads(snap.to_json()))
    assert restored.label == "before"
    assert restored.memory == snap.memory
    assert restored.thermal == snap.thermal


def test_adb_shell_raises_on_failure():
    adb = Adb(runner=lambda argv: CommandResult(1, "", "permission denied"))
    with pytest.raises(AdbError):
        adb.shell("dumpsys battery")
    assert "permission denied" in adb.shell("dumpsys battery", check=False)


def test_adb_shell_normalises_crlf():
    adb = Adb(runner=lambda argv: CommandResult(0, "a\r\nb\r\n"))
    assert adb.shell("x") == "a\nb"


def test_getprop_parsing():
    adb = demo_adb()
    props = adb.getprop()
    assert props["ro.soc.model"] == "SM8735"
    assert props["ro.build.version.sdk"] == "36"


def test_cli_demo_end_to_end(tmp_path, capsys):
    from pad8booster.cli import main

    out = tmp_path / "demo.md"
    code = main(["demo", "--out", str(out)])
    assert code == 0
    text = out.read_text(encoding="utf-8")
    assert "Pad8Booster report" in text
    assert "DEMO MODE" in text
    assert "Before / after" in text


def test_cli_probe_json(capsys):
    from pad8booster.cli import main

    code = main(["--demo", "--json", "probe"])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["verification"]["is_pad8"] is True
    assert payload["demo"] is True


def test_cli_debloat_requires_yes_for_writes(capsys):
    from pad8booster.cli import main

    code = main(["--demo", "debloat", "apply", "--tags", "privacy"])
    assert code == 0
    assert "dry run" in capsys.readouterr().out


def test_cli_compare_builds_report(tmp_path):
    from pad8booster.cli import main

    before = metrics.take_snapshot(demo_adb("before"), label="before")
    after = metrics.take_snapshot(demo_adb("after"), label="after")
    b_path, a_path = tmp_path / "b.json", tmp_path / "a.json"
    b_path.write_text(before.to_json(), encoding="utf-8")
    a_path.write_text(after.to_json(), encoding="utf-8")
    report = tmp_path / "r.md"
    code = main(["compare", str(b_path), str(a_path), "--out", str(report), "--offline"])
    assert code == 0
    assert "Before / after" in report.read_text(encoding="utf-8")


def test_cli_unknown_profile_is_usage_error(capsys):
    from pad8booster.cli import main

    code = main(["--demo", "profile", "apply", "turbo9000"])
    assert code == 2


# --------------------------------------------------------------------------
# display density
# --------------------------------------------------------------------------

def test_density_override_is_journalled_and_reversible(tmp_path):
    dev = DemoDevice()
    adb = Adb(serial="DEMO", runner=dev.run)
    journal = profiles.Journal.load(tmp_path / "j.json")

    record = profiles.set_density(adb, 264, journal, dry_run=False)
    assert record["status"] == "applied"
    assert dev.density_override == 264
    assert profiles.read_density(adb)["override"] == 264

    profiles.reset_density(adb, journal, dry_run=False)
    assert dev.density_override is None
    assert journal.entries == []


def test_density_out_of_range_is_refused():
    journal = profiles.Journal.load(Path("/tmp/none3.json"))
    for bad in (120, 500, 0, -1):
        with pytest.raises(ValueError):
            profiles.set_density(demo_adb(), bad, journal, dry_run=True)


def test_command_action_reverts_via_recorded_inverse(tmp_path):
    dev = DemoDevice()
    adb = Adb(serial="DEMO", runner=dev.run)
    journal = profiles.Journal.load(tmp_path / "j.json")

    profiles.apply_profile(adb, "performance", journal, dry_run=False)
    assert dev.fixed_perf is True
    entry = journal.for_profile("performance")[0]
    assert entry.revert_command == "cmd power set-fixed-performance-mode-enabled false"

    profiles.revert_profile(adb, "performance", journal, dry_run=False)
    assert dev.fixed_perf is False


def test_cli_display_reports_stock_density(capsys):
    from pad8booster.cli import main

    assert main(["--demo", "display"]) == 0
    assert "physical density 320" in capsys.readouterr().out


# --------------------------------------------------------------------------
# commands that must work with no tablet attached
# --------------------------------------------------------------------------

def test_profile_list_needs_no_device(capsys):
    from pad8booster.cli import main

    assert main(["profile", "list"]) == 0
    out = capsys.readouterr().out
    assert "responsive" in out and "battery" in out


def test_debloat_list_needs_no_device(capsys):
    from pad8booster.cli import main

    assert main(["debloat", "list"]) == 0
    assert "com.miui.msa.global" in capsys.readouterr().out


def test_missing_adb_fails_cleanly(monkeypatch, capsys):
    from pad8booster.cli import main

    monkeypatch.setattr("pad8booster.cli._connect", lambda args: (_ for _ in ()).throw(SystemExit("no device")))
    with pytest.raises(SystemExit):
        main(["probe"])

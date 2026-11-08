"""Guards in the tuning scripts, exercised against the SHIPPED code.

Each case here is a defect that actually shipped and was caught in review on PR #1. They share
one shape: a script that continued past a failure and reported success anyway. None of these
scripts uses `set -e`, so an unchecked status is a silent continuation, and a measurement
harness that continues after losing its measurement is worse than one that crashes -- its
output is quoted with the same confidence as a real row.

Like tests/test_launcher_spec_guard.py, these EXTRACT from the real files rather than copying
the logic, so a test cannot keep passing while the script it describes rots.
"""
import re
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
HARNESS = REPO / "scripts" / "tuning" / "09-vllm-experiments.sh"
BENCH = REPO / "scripts" / "tuning" / "bench_quiet.sh"
INSTALL = REPO / "scripts" / "tuning" / "10-install-service-files.sh"


def _extract_function(path: Path, name: str) -> str:
    """Pull one shell function out of a script by name."""
    text = path.read_text(encoding="utf-8")
    m = re.search(rf"^{re.escape(name)}\(\) \{{.*?^\}}", text, re.S | re.M)
    assert m, f"{path.name} no longer defines {name}()"
    return m.group(0)


def _code_lines(path: Path) -> str:
    """The script with comment lines removed.

    Needed because these files explain, in prose, the very anti-patterns they no longer use --
    a naive substring check matches the explanation and fails on a correct file.
    """
    return "\n".join(ln for ln in path.read_text(encoding="utf-8").splitlines()
                     if not ln.lstrip().startswith("#"))


def _sh(script: str, env=None, cwd=None):
    p = subprocess.run(["bash", "-c", "set -uo pipefail\n" + script],
                       capture_output=True, text=True, timeout=60,
                       env=env, cwd=cwd)
    return p.returncode, p.stdout + p.stderr


# --------------------------------------------------------------------------- needles_for()

@pytest.mark.parametrize("extra,expected", [
    ("'--enable-prefix-caching'", ["enable-prefix-caching"]),
    ("'--speculative-config' '{\"method\":\"mtp\"}'", ["speculative-config"]),
    # `both` mode: the regression. Must yield BOTH, or a confounded run passes validation.
    ("'--enable-prefix-caching' '--speculative-config' '{\"method\":\"ngram\"}'",
     ["enable-prefix-caching", "speculative-config"]),
    ("", []),
])
def test_needles_for_returns_every_flag_not_just_the_first(extra, expected):
    fn = _extract_function(HARNESS, "needles_for")
    # EXTRA goes through the environment: it contains single quotes and JSON braces, and
    # nesting those into the -c string is the very quoting hazard this project keeps hitting.
    script = fn + '\nneedles_for "$EXTRA"\n'
    rc, out = _sh(script, env={"PATH": "/usr/bin:/bin", "EXTRA": extra})
    assert rc == 0, out
    assert out.split() == expected


# ------------------------------------------------------------------ assert_clean_baseline()

def _clean_baseline_verdict(tmp_path, contents):
    conf = tmp_path / "conf"
    conf.write_text(contents, encoding="utf-8")
    fn = _extract_function(HARNESS, "assert_clean_baseline")
    script = f'CONF="{conf}"\n{fn}\nassert_clean_baseline && echo CLEAN\n'
    return _sh(script, env={"PATH": "/usr/bin:/bin", "PWD": str(tmp_path)})


def test_clean_conf_is_accepted(tmp_path):
    rc, out = _clean_baseline_verdict(tmp_path, "VLLM_MODEL=/x\nVLLM_EXTRA_ARGS=\n")
    assert rc == 0 and "CLEAN" in out, out


def test_occupied_slot_is_rejected(tmp_path):
    rc, out = _clean_baseline_verdict(tmp_path, 'VLLM_EXTRA_ARGS="--some-experiment"\n')
    assert rc == 7, out
    assert "already carries an active" in out


def test_unparseable_conf_is_not_mistaken_for_an_empty_one(tmp_path):
    """The defect: source errors were swallowed, so a BROKEN conf read as a clean baseline.

    backup_baseline would then copy it over the revert target and every later `revert` would
    restore the broken file. "Cannot be read" and "is empty" are different states.
    """
    rc, out = _clean_baseline_verdict(tmp_path, "VLLM_MODEL=/x\nif [ -z ; then\n")
    assert rc == 12, out
    assert "does not source cleanly" in out
    assert "CLEAN" not in out


# ------------------------------------------------------------------------- bench_quiet.sh

def test_bench_quiet_rejects_a_port_passed_as_a_run_count():
    """`bench_quiet.sh 8007 3` set RUNS=8007 and started 8,007 runs against the live GPU."""
    rc, out = _sh(f'"{BENCH}" 8007 3', env={"PATH": "/usr/bin:/bin"})
    assert rc == 2, out
    assert "not a sane run count" in out
    assert "bench-vllm.sh <port> <runs>" in out, "the error should name the sibling script"


@pytest.mark.parametrize("bad", ["0", "-1", "abc", "1000"])
def test_bench_quiet_rejects_nonsense_run_counts(bad):
    rc, out = _sh(f'"{BENCH}" {bad}', env={"PATH": "/usr/bin:/bin"})
    assert rc == 2, out


def test_bench_quiet_rejects_extra_arguments():
    rc, out = _sh(f'"{BENCH}" 3 extra', env={"PATH": "/usr/bin:/bin"})
    assert rc == 2, out


def test_bench_quiet_uses_mktemp_not_a_predictable_path():
    """Root-invoked via 09-vllm-experiments.sh, so a $$-derived /tmp path is symlink-attackable."""
    code = _code_lines(BENCH)
    assert "mktemp" in code
    assert "/tmp/.spec.$$" not in code
    assert "trap 'rm -f" in code, "the temp file must be cleaned up on every exit path"


def test_bench_quiet_propagates_inner_failure():
    """A wrapper that prints VALID over a failed bench is a gate that passes on no data."""
    code = _code_lines(BENCH)
    assert "_bench_rc" in code, "bench-vllm.sh's exit status must be captured"
    assert re.search(r'if \[ "\$_bench_rc" -ne 0 \]', code), "and acted on before any verdict"


# ------------------------------------------------------------- 10-install-service-files.sh

@pytest.mark.parametrize("mode", ["--dryrun", "-n", "--roll-back", "install-now"])
def test_installer_rejects_unknown_modes(mode):
    """An unknown mode used to fall through to the LIVE INSTALL path and restart production."""
    rc, out = _sh(f'"{INSTALL}" {mode}', env={"PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
                                              "HOME": "/tmp"})
    assert rc == 1, out
    assert "unknown mode" in out


def test_installer_rolls_back_on_a_failed_install():
    code = _code_lines(INSTALL)
    assert code.count("rollback 1") >= 2, "both install failures must trigger a rollback"
    assert "if ! install -o root" in code, "install status must be checked, not chained with &&"


def test_rollback_exit_codes_distinguish_recovery_from_a_dead_backend():
    """Automation reads $?, and the old code exited 0 even when the service never came back."""
    code = _code_lines(INSTALL)
    assert "exit 2" in code
    assert "DID NOT COME BACK" in code
    assert re.search(r'rollback\(\) \{\s*\n\s*local rc=', code), "rollback must take an exit code"


def test_installer_uses_mktemp_for_the_unit_syntax_check():
    code = _code_lines(INSTALL)
    assert "/tmp/.unit-syntax.$$" not in code
    assert "mktemp" in code
    assert "trap 'rm -f" in code


# --- 2026-11-01: the mtp4 outage ------------------------------------------------------------
# k=4 died at engine init in ~2 min, but `rc-service restart` blocked up to 1800s waiting for
# /health, so the harness never reached its auto-revert; Ctrl-C then left an orphaned
# supervise-daemon respawning the experiment. These pin the three fixes.

def _svc_cycle_script(log: Path, fail_line: str | None, rc_body: str) -> str:
    text = HARNESS.read_text(encoding="utf-8")
    regex_line = re.search(r"^INIT_FAIL_RE=.*$", text, re.M)
    assert regex_line, "harness no longer defines INIT_FAIL_RE"
    writer = (f'( sleep 2; printf "%s\\n" {fail_line!r} >> "$VLLM_WRITER_LOG" ) &'
              if fail_line else "")
    # hard_stop and rc-service are STUBBED: the real ones would stop production vLLM.
    return f"""
export VLLM_WRITER_LOG={str(log)!r}
READY_WAIT=600
{regex_line.group(0)}
{_extract_function(HARNESS, "svc_cycle")}
hard_stop() {{ echo HARD_STOP_CALLED; }}
rc-service() {{ {rc_body}; }}
{writer}
svc_cycle restart; echo "RC=$?"
"""


def test_svc_cycle_aborts_fast_on_engine_init_failure(tmp_path):
    log = tmp_path / "writer.log"; log.write_text("old line\n")
    fail = ("(EngineCore pid=1) ValueError: To serve at least one request with the model's max seq "
            "len (49152), (2.09 GiB KV cache is needed, which is larger than the available KV "
            "cache memory (1.98 GiB)")
    p = subprocess.run(["bash", "-c", _svc_cycle_script(log, fail, "sleep 60")],
                       capture_output=True, text=True, timeout=30)
    assert "RC=3" in p.stdout, p.stdout + p.stderr
    assert "HARD_STOP_CALLED" in p.stdout, "a detected init failure must hard-stop the orphan"


def test_svc_cycle_ignores_failures_logged_before_the_restart(tmp_path):
    log = tmp_path / "writer.log"
    log.write_text("Engine core initialization failed (from an EARLIER boot)\n")
    p = subprocess.run(["bash", "-c", _svc_cycle_script(log, None, "sleep 1; true")],
                       capture_output=True, text=True, timeout=30)
    assert "RC=0" in p.stdout, p.stdout + p.stderr
    assert "HARD_STOP_CALLED" not in p.stdout


def test_every_service_start_goes_through_svc_cycle():
    code = _code_lines(HARNESS)
    raw = re.findall(r"^\s*rc-service vllm-qwen38 (?:re)?start\b", code, re.M)
    assert not raw, f"bare rc-service start/restart bypasses the init-failure watch: {raw}"


def test_interrupt_triggers_revert():
    code = _code_lines(HARNESS)
    assert re.search(r"trap '.*revert.*' INT TERM HUP", code), "Ctrl-C must revert, not strand"
    assert "hard_stop" in _extract_function(HARNESS, "revert"), \
        "revert must kill a supervisor started under the experiment before restarting"

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

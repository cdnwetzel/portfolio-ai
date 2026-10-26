"""The vLLM launcher's speculative-config resolution and capture-size guard.

Why this test exists
--------------------
The guard converts a SILENT failure into a refusal to start. With k draft tokens, uniform
decode runs at query_len = 1 + k, so the only reachable widths are the multiples of (1+k) up
to max_num_seqs*(1+k). A width that is not captured EXACTLY does not raise: vLLM quietly drops
FULL cudagraphs to PIECEWISE and the server keeps answering, just slower, with nothing in any
health check to notice.

The first version of that guard shipped with a real bug, caught in review on PR #1: it
validated against VLLM_SPEC_K *before* the experiment slot was parsed. Since MTP was promoted
into the launcher's permanent argv, the slot can carry a different depth, and the guard would
have refused to start every experiment mode that sets its own capture sizes -- ngram-g (k=4)
wants widths 5/10/15/20, mtp2 (k=2) wants 3/6/9/12, and the guard demanded k=3's 4/8/12/16
regardless. That would have blocked the next measurement session outright.

This test runs the REAL block extracted from the shipped launcher rather than a copy of the
logic, so it cannot drift from what actually executes on the box.
"""
import subprocess
import textwrap
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
LAUNCHER = REPO / "home" / "vllm-service" / "start-qwen38.sh"

START_MARK = "# --- experiment hook"
END_MARK = 'exec "'


def _extract_block() -> str:
    """Pull the live resolution+guard section out of the shipped launcher.

    Deliberately extraction rather than duplication: a copied-out fixture would pass forever
    while the real launcher rotted.
    """
    text = LAUNCHER.read_text(encoding="utf-8")
    assert START_MARK in text, f"{LAUNCHER} no longer contains {START_MARK!r}"
    body = text.split(START_MARK, 1)[1]
    assert END_MARK in body, f"{LAUNCHER} no longer contains the exec line after the hook"
    return START_MARK + body.split(END_MARK, 1)[0]


def _run(extra: str, sizes: str, seqs: str = "4"):
    """Execute the real block with a given slot + capture sizes. Returns (rc, output)."""
    script = _extract_block() + '\necho "EFFECTIVE_ARGS=[${_spec_args[*]-}]"\n'
    p = subprocess.run(
        ["bash", "-c", "set -euo pipefail\n" + script],
        env={
            "PATH": "/usr/bin:/bin:/usr/local/bin",
            "VLLM_EXTRA_ARGS": extra,
            "VLLM_CUDAGRAPH_SIZES": sizes,
            "VLLM_SEQS": seqs,
        },
        capture_output=True, text=True, timeout=60,
    )
    return p.returncode, p.stdout + p.stderr


MTP2 = "'--speculative-config' '{\"method\":\"mtp\",\"num_speculative_tokens\":2}'"
NGRAM4 = ("'--speculative-config' '{\"method\":\"ngram\",\"num_speculative_tokens\":4,"
          "\"prompt_lookup_min\":2,\"prompt_lookup_max\":4}'")


def test_promoted_config_with_no_slot():
    """Today's live state: k=3 from the launcher, and it emits its own --speculative-config."""
    rc, out = _run("", "[1,2,4,8,12,16]")
    assert rc == 0, out
    assert "spec-decode k=3 (launcher)" in out
    assert "num_speculative_tokens\":3" in out


def test_slot_overrides_depth_and_launcher_emits_nothing():
    """The slot outranks the promoted config, and must not produce a duplicate flag."""
    rc, out = _run(MTP2, "[1,2,3,4,6,8,9,12]")
    assert rc == 0, out
    assert "spec-decode k=2 (experiment slot)" in out
    assert "EFFECTIVE_ARGS=[]" in out, "launcher must not add a second --speculative-config"


@pytest.mark.parametrize("extra,sizes,depth", [
    (MTP2, "[1,2,3,4,6,8,9,12]", 2),          # mtp2 mode
    (NGRAM4, "[1,2,4,5,8,10,15,20]", 4),      # ngram-g mode
])
def test_every_harness_mode_still_boots(extra, sizes, depth):
    """Regression for the PR #1 bug: these all failed to start under the first guard."""
    rc, out = _run(extra, sizes)
    assert rc == 0, out
    assert f"spec-decode k={depth} (experiment slot)" in out


def test_slot_depth_with_mismatched_sizes_refuses():
    """The real hazard: a slot depth whose widths are not captured must NOT start."""
    rc, out = _run(NGRAM4, "[1,2,4,8,12,16]")   # k=3's sizes, k=4's depth
    assert rc == 1, out
    assert "MISSING" in out and "5" in out and "20" in out
    assert "experiment slot" in out, "the error must say where the depth came from"


def test_prompt_lookup_digits_are_not_mistaken_for_depth():
    """`prompt_lookup_max:4` must not be read as the draft depth when the depth is 2."""
    extra = ("'--speculative-config' '{\"method\":\"ngram\",\"num_speculative_tokens\":2,"
             "\"prompt_lookup_max\":4}'")
    rc, out = _run(extra, "[1,2,3,4,6,8,9,12]")
    assert rc == 0, out
    assert "spec-decode k=2" in out


def test_equals_form_is_understood():
    """--speculative-config=JSON must resolve the same as the space-separated form."""
    extra = "'--speculative-config={\"method\":\"mtp\",\"num_speculative_tokens\":2}'"
    rc, out = _run(extra, "[1,2,3,4,6,8,9,12]")
    assert rc == 0, out
    assert "spec-decode k=2 (experiment slot)" in out


def test_unparseable_depth_refuses_rather_than_guessing():
    """An unvalidatable depth must fail closed -- guessing reintroduces the silent failure."""
    rc, out = _run("'--speculative-config' '{\"method\":\"mtp\"}'", "[1,2,4,8,12,16]")
    assert rc == 1, out
    assert "cannot read num_speculative_tokens" in out


def test_dangling_flag_refuses():
    rc, out = _run("'--speculative-config'", "[1,2,4,8,12,16]")
    assert rc == 1, out
    assert "no value" in out


def test_non_speculative_slot_leaves_launcher_depth_intact():
    """A slot used for some other flag must not disturb the promoted config."""
    rc, out = _run("'--enable-chunked-prefill'", "[1,2,4,8,12,16]")
    assert rc == 0, out
    assert "spec-decode k=3 (launcher)" in out
    assert "num_speculative_tokens\":3" in out


def test_conf_d_documented_example_survives_the_double_parse():
    """conf.d is sourced by OpenRC and then eval'd by the launcher; each WORD must stay quoted.

    The single-quoted form this file used to document expanded braces on the commas and shredded
    the JSON into three argv words. A wrong comment is worse than none: a comment is what
    someone copies by hand.
    """
    conf = (REPO / "home" / "vllm-service" / "conf.d-vllm-qwen38").read_text(encoding="utf-8")
    example = next(
        (ln.lstrip("#").strip() for ln in conf.splitlines()
         if 'VLLM_EXTRA_ARGS="' in ln and "speculative-config" in ln),
        None,
    )
    assert example, "the conf.d speculative-config example went missing"

    script = textwrap.dedent(f"""
        {example}
        eval "_extra=(${{VLLM_EXTRA_ARGS}})"
        printf '%s\\n' "${{#_extra[@]}}"
        printf '%s\\n' "${{_extra[1]}}"
    """)
    p = subprocess.run(["bash", "-c", script], capture_output=True, text=True, timeout=30)
    assert p.returncode == 0, p.stderr
    count, second = p.stdout.strip().splitlines()[:2]
    assert count == "2", f"expected 2 argv words, got {count} — brace expansion shredded the JSON"
    assert second.startswith("{") and second.endswith("}"), second
    assert '"num_speculative_tokens"' in second

"""The eval probes must catch wrong claims AND must not flag correct answers (2026-11-08).

The post-reindex run (plans/kb-answer-quality-fixes-2026-11.md §7) flagged three correct answers:
a suggestion chip read as a claim (F9), denials read as claims (F2, F4), and a correct 130 W
history line read as the current cap. Each case below is a sentence the live site produced or
could produce; both halves of every pair must hold.

kb_battery.py needs `websockets` only at call time, so it is loaded with a stub when absent.
"""
import importlib.util
import os
import sys
import types

import pytest

_S = os.path.join(os.path.dirname(__file__), "..", "scripts")
sys.path.insert(0, _S)


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_S, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


E = _load("expectations")
sys.modules.setdefault("websockets", types.ModuleType("websockets"))
B = _load("kb_battery")


def probe(fid, name, q_contains=""):
    for f, q, probes in B.B:
        if f == fid and name in probes and q_contains in q:
            return probes[name]
    raise KeyError((fid, name))


def bad(fid, name, text, q=""):
    return E.bad_claim_hit(probe(fid, name, q), text)[0]


# --- chips are not claims -----------------------------------------------------

def test_strip_followups_removes_the_chip_block():
    a = 'MTP drafts tokens.\n\n---\nFOLLOWUPS:["Does prefix caching speed up generation?","b","c"]'
    assert E.strip_followups(a) == "MTP drafts tokens."


def test_strip_followups_leaves_an_answer_without_chips_alone():
    assert E.strip_followups("Plain answer. --- with a dash.") == "Plain answer. --- with a dash."


def test_a_chip_cannot_trip_a_bad_probe():
    a = 'Follow-ups are faster because of MTP.\n\n---\nFOLLOWUPS:["Does prefix caching speed up token generation?"]'
    assert not bad("F9", "bad_prefix_decode", a)
    assert bad("F9", "bad_prefix_decode", "Prefix caching speeds up token generation.")


# --- denials are not claims, and a denial cannot launder a claim ---------------

@pytest.mark.parametrize("ok", [
    "Chris doesn't use Terraform or Ansible.",
    "There is no Terraform or Ansible in his documented work.",
    "He does not use Terraform, Ansible or Puppet.",
])
def test_f4_denials_pass(ok):
    assert not bad("F4", "bad_terraform_ansible", ok)


@pytest.mark.parametrize("wrong", [
    "He manages infrastructure with Terraform and Ansible.",
    "No, he uses Terraform.",
    "He doesn't use Puppet; he uses Ansible.",
])
def test_f4_claims_fail(wrong):
    assert bad("F4", "bad_terraform_ansible", wrong)


def test_f2_family():
    assert not bad("F2", "bad_diff_family", "The judge is not from a different family; both are Qwen.")
    assert bad("F2", "bad_diff_family", "The judge is from a different model family.")


def test_f3_reverse_tunnel_vs_reverse_proxy():
    assert not bad("F3", "bad_reverse", "Apache is the reverse proxy in front of FastAPI.")
    assert not bad("F3", "bad_reverse", "It is not a reverse tunnel: the VPS opens it with ssh -L.")
    assert bad("F3", "bad_reverse", "The T5810 opens a reverse SSH tunnel to the VPS.")
    assert bad("F3", "bad_reverse", "No — it's a reverse tunnel.")


def test_f1_reranker_gpu():
    q = "Which GPU"
    assert not bad("F1", "bad_rerank_on_A4500", "The reranker runs on the RTX 5060 Ti, while the A4500s run generation.", q)
    assert not bad("F1", "bad_rerank_on_A4500", "The reranker does not run on the A4500s.", q)
    assert bad("F1", "bad_rerank_on_A4500", "The reranker runs on an A4500.", q)
    assert bad("F1", "bad_rerank_on_A4500", "The two A4500s host the reranker.", q)


def test_f6_port_8004():
    assert not bad("F6", "bad_vllm_8004", "labrouter on 8004 routes to vLLM on 8007.")
    assert not bad("F6", "bad_vllm_8004", "The VPS reaches vLLM only via 8004.")
    assert bad("F6", "bad_vllm_8004", "vLLM runs on port 8004.")
    assert bad("F6", "bad_vllm_8004", "Port 8004 (vLLM) goes down.")


def test_f5_blend_not_separate_p2v_project():
    q = "major"
    assert not bad("F5", "bad_avd_p2v", "We routinely P2V'd servers to cut power and cooling.", q)
    assert not bad("F5", "bad_avd_p2v", "The AVD migration involved no P2V or V2V work.", q)
    assert bad("F5", "bad_avd_p2v", "The AVD project included P2V of the old servers.", q)


def test_f7_9_5_is_not_99_5():
    import re
    p = probe("F7", "says_9_5")
    assert not re.search(p, "The AVD environment hit 99.5% uptime.")
    assert re.search(p, "He has 9.5 years of MSP experience.")


def test_f9_prefix_caching_ttft_is_correct():
    assert not bad("F9", "bad_prefix_decode", "Prefix caching makes the first token arrive faster, not the generation.")
    assert not bad("F9", "bad_prefix_decode", "Prefix caching shortens the wait, not the generation.")
    assert bad("F9", "bad_prefix_decode", "Prefix caching increases tokens per second.")


def test_denied_only_is_reported_for_audit():
    assert E.bad_claim_hit(r"Terraform", "He doesn't use Terraform.") == (False, True)
    assert E.bad_claim_hit(r"Terraform", "Nothing relevant here.") == (False, False)


# --- 130 W: history passes, a current-cap claim fails --------------------------

POWER = [{"match": r"130\s*w", "unless": E.POWER_HISTORY_FRAMES, "regex": True}]


@pytest.mark.parametrize("ok", [
    "It was capped at 130 W under the old mining profile; now it is 165 W.",
    "The cap was raised from 130 W to 165 W on 2026-08-31.",
    "The previous 130 W profile is gone.",
])
def test_power_history_passes(ok):
    assert E.forbid_hit(POWER, ok) is None


@pytest.mark.parametrize("wrong", [
    "Each A4500 is capped at 130 W.",
    "The power cap is 130 W per card.",
])
def test_power_current_claim_fails(wrong):
    assert E.forbid_hit(POWER, wrong)


def test_golden_power_item_matches_the_harness_rule():
    yaml = pytest.importorskip("yaml")  # CI installs only pytest
    g = yaml.safe_load(open(os.path.join(_S, "..", "eval", "golden_set.yaml")))
    item = next(i for i in g if "power cap" in i["q"])
    f = item["forbid_substrings"]
    assert E.forbid_hit(f, "It was capped at 130 W under the old mining profile.") is None
    assert E.forbid_hit(f, "Each card is capped at 130 W.") == "capped at 130"
    assert E.forbid_hit(f, "The SM clock is locked to 1200 MHz.") == "1200 mhz"

"""Offline guards on KB *content*: claims that were measured wrong on the live site (2026-11-01
battery) and corrected in the KB. Each test names the finding it pins. These read the committed
markdown only -- no live stack -- so they run in CI and fail before a bad reindex, not after.

They are deliberately phrase-level: they catch the exact wording that produced a wrong answer
coming back, not every way of being wrong. The live check is still the battery.
"""
import importlib.util
import os
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
KB = ROOT / "knowledge_base"

_spec = importlib.util.spec_from_file_location("indexer", ROOT / "scripts" / "index_with_embeddings.py")
indexer = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(indexer)


def _indexed_docs():
    return indexer.load_documents(str(KB))


def _indexed_text():
    return "\n".join(d["content"] for d in _indexed_docs())


# F4 / F11 -------------------------------------------------------------------------------------

def test_professional_context_is_not_indexed():
    docs = _indexed_docs()
    assert not [d for d in docs if d["source"] == "context" or d["id"] == "professional_context"]


def test_professional_context_not_loaded_even_if_restored_to_repo_root(tmp_path):
    # The old loader read <kb>/../PROFESSIONAL_CONTEXT.md. Recreate that layout and prove the
    # loader no longer looks there.
    kb = tmp_path / "knowledge_base"
    kb.mkdir()
    (kb / "RESUME.md").write_text("# Resume\nreal content\n")
    (tmp_path / "PROFESSIONAL_CONTEXT.md").write_text("Infrastructure as Code (Terraform, Ansible)\n")
    docs = indexer.load_documents(str(kb))
    assert all("Terraform" not in d["content"] for d in docs)


def test_no_unverified_iac_tools_in_kb():
    # The site answered "Terraform, Ansible" 3/3 from a sentence that said "likely contain".
    # Nothing in the KB documents either tool. If that becomes true, document it and drop this.
    assert not re.search(r"\b(Terraform|Ansible)\b", _indexed_text())


# F3 -------------------------------------------------------------------------------------------

def test_tunnel_not_described_as_reverse():
    # The tunnel is `ssh -L` local forwards opened BY the VPS (cloud/systemd/
    # portfolio-ai-tunnel.service). "Reverse" was repeated 3/3. Negations ("not a reverse
    # tunnel") are banned too: they prime the word they deny.
    hits = re.findall(r"[^.\n]{0,40}\breverse\b[^.\n]{0,15}(?:tunnel|forward|ssh)", _indexed_text(), re.I)
    assert not hits, hits


def test_tunnel_unit_really_is_local_forwards():
    # Pins the KB claim to its source of truth: if the unit ever moves to -R, the KB is wrong
    # again and this should be the thing that says so.
    unit = (ROOT / "cloud" / "systemd" / "portfolio-ai-tunnel.service").read_text()
    execstart = next(l for l in unit.splitlines() if l.startswith("ExecStart="))
    assert " -L " in execstart and " -R " not in execstart


# F2 -------------------------------------------------------------------------------------------

def test_judge_not_called_a_different_family():
    # Judge Qwen2.5-14B and answerer Qwen3.8-27B are the same (Qwen) family.
    assert not re.search(r"different (model )?famil", _indexed_text(), re.I)


# F6 -------------------------------------------------------------------------------------------

def test_vllm_not_placed_on_port_8004():
    # 8004 is labrouter; vLLM is the 8007 backend behind it.
    text = _indexed_text()
    assert not re.search(r"\|\s*vLLM\s*\|\s*8004\s*\|", text)
    assert not re.search(r"vLLM (?:on|at|listens on) (?:port )?:?8004", text, re.I)


# F9 / F10 -------------------------------------------------------------------------------------

def test_superseded_fresh_chat_speed_not_current():
    # ~47 tok/s was 2026-09-14; 2026-11-01 measured ~70. The old figure may appear only if it
    # is explicitly marked superseded on the same line.
    for line in _indexed_text().splitlines():
        if re.search(r"~?47 tok(?:ens)?/s", line):
            assert "supersed" in line.lower(), line


def test_prefix_caching_not_credited_with_decode_speed():
    # Prefix caching cuts prefill (time to first token), not tokens/sec.
    assert not re.search(r"prefix is already cached, so less work is repeated", _indexed_text())


# F5 -------------------------------------------------------------------------------------------

def test_major_projects_overview_is_indexed_and_separates_avd_from_p2v():
    docs = {d["id"]: d for d in _indexed_docs()}
    ov = docs.get("case_major_projects_overview")
    assert ov, "major_projects_overview.md missing from the index"
    avd = ov["content"].split("## Azure Virtual Desktop", 1)[1].split("\n## ", 1)[0]
    avd = " ".join(avd.split())  # markdown wraps lines mid-phrase
    assert "P2V" in avd and "separate" in avd   # the explicit disambiguation line
    assert "Windows Server 2012" in avd         # sourced from cwetzel.com/projects


# F8 -------------------------------------------------------------------------------------------

def test_pxx_test_count_not_the_june_figure():
    text = (KB / "pxx_project.md").read_text()
    for line in text.splitlines():
        if re.search(r"\b690 tests\b", line):
            assert re.search(r"up from 690|690 in June", line), line


# F7 + site coverage ---------------------------------------------------------------------------

def test_resume_covers_every_job_on_cwetzel_com_experience():
    # cwetzel.com/experience lists six roles and LinkedIn nine; the KB used to have two, so
    # "18 years at MSPs" (correct) had no source. Keep this list in step with LinkedIn.
    resume = (KB / "RESUME.md").read_text()
    for org in ("Portnoy Schneck", "RedEye", "Mercer Institute", "PeriGen",
                "Pro Computer Service", "MBNA", "Howell Township School District",
                "The College of New Jersey", "Central Bucks School District"):
        assert org in resume, org
    assert "Director of Legal Technology" in resume
    assert re.search(r"18 years at two managed service providers", resume)


# Generated-era case studies (archived 2026-11-07) ---------------------------------------------

def test_generated_avd_sap_case_studies_not_indexed():
    ids = {d["id"] for d in _indexed_docs()}
    assert "case_avd_migration_200_users" not in ids
    assert "case_sap_business_one_integration" not in ids
    assert "case_avd_sap_global_distributor" in ids


def test_avd_sap_facts_match_what_chris_confirmed():
    text = _indexed_text()
    # wrong client, wrong platform, invented figures -- none confirmed by any source
    for bad in ("financial services",):  # Citrix, AVD and SAP figures: all confirmed 2026-11-07
        assert bad not in text, bad
    cs = " ".join((KB / "case_studies" / "avd_sap_global_distributor.md").read_text().split())
    assert "November 2021 – August 2023" in cs          # not "present": he left RedEye
    assert "co-led this work with a RedEye colleague" in cs
    assert "same client" in cs
    assert "Chris was not the SAP consultant" in cs   # he deployed it in AVD; didn't do SAP work


def test_june_fabrications_stay_out_of_the_resume():
    # 77556b9 (2026-06-28) named these as fabricated and fixed the case studies, but RESUME.md
    # kept its own copies until 2026-11-07. LinkedIn's Projects section has exactly three
    # projects (SOC2 2022, the macOS->VMware studio migration 2018, Gentoo 2025-present).
    resume = (KB / "RESUME.md").read_text()
    for bad in ("50+ servers", "3 data centers", "60% hardware", "Row-level security",
                "home office internet outage", "40+ staff", "50+ enterprise clients",  # 50+ CLIENTS is real; "enterprise" was not
                "Azure fundamentals"):
        assert bad not in resume, bad


def test_security_doc_has_no_invented_records():
    # Generated 2026-06-07. Chris confirmed the controls reflect real work for regulated-industry
    # clients, not the dated "records" used as examples (VULN-2847, "Support1", 2024 timelines).
    text = (KB / "case_studies" / "security_hardening_operations.md").read_text()
    for bad in ("VULN-", "Support1", "client ABC", "2024-", "2025-"):
        assert bad not in text, bad
    assert "family services" in text and "endodontists" in text
    # Chris confirmed 2026-11-07: audits for NIST (DoD), FINRA, HIPAA, PCI and SOC 2.
    for reg in ("NIST", "FINRA", "HIPAA", "PCI", "SOC 2"):
        assert reg in text, reg


def test_resume_states_no_certifications():
    # Chris, 2026-11-07: no industry certifications. A "Certifications & Training" heading over a
    # skills list invites the model to invent some.
    resume = (KB / "RESUME.md").read_text()
    assert "holds no industry certifications" in resume
    assert "Certifications & Training" not in resume


# pxx rewrite from the public v2 repo (2026-11-08) ---------------------------------------------

def test_pxx_page_describes_2x_not_the_aider_wrapper():
    text = (KB / "pxx_project.md").read_text()
    head = text.split("## History")[0]
    assert "pxx owns the agent loop" in head
    assert "os.execv" not in head                      # 1.x execution layer, History only
    assert "pip install agentmemory" not in text       # someone else's package on PyPI
    assert "2.9.3" in head and "qwen2.5-coder:7b" in head


def test_pxx_test_count_says_which_commit():
    text = (KB / "pxx_project.md").read_text()
    assert "1,863" in text and "5be59d5" in text and "1,746" in text
    assert "1,863 tests, public repo v2.9.3" not in text   # the 2026-11-07 wording conflated them


def test_linux_doc_rollback_and_selinux_match_the_repo():
    text = (KB / "case_studies" / "linux_sysadmin_background.md").read_text()
    assert "automated rollback" not in text
    assert "SELinux policy" not in text
    assert "Cross-compilation is part of the design" not in text

"""
Pure logic for the faithfulness verifier (verifier-faithfulness-layer.md §3, §6.3).

Kept dependency-free and separate from the FastAPI service so the claim-parsing,
refusal detection, and scoring can be unit-tested without a judge model — the same
lenient-parse / strict-validate discipline that the FOLLOWUPS parser taught us.
"""
import json
import re
from typing import List, Dict, Optional

# Answers that contain no auditable factual claims → recorded as refusals, not scored.
REFUSAL_MARKERS = (
    "don't have that documented",
    "do not have that documented",
    "conflicting information",
    "can only answer questions about chris wetzel",
)

VALID_VERDICTS = {"supported", "unsupported", "contradicted"}

# FOLLOWUPS block the model appends; stripped before judging (it isn't a claim).
_FOLLOWUPS_RE = re.compile(r"FOLLOWUPS\s*:", re.IGNORECASE)


def strip_followups(text: str) -> str:
    """Remove the trailing FOLLOWUPS:[...] block and its '---' separator."""
    if not text:
        return ""
    m = _FOLLOWUPS_RE.search(text)
    if m:
        text = text[: m.start()]
    # drop a dangling markdown separator left behind by system_suffix
    text = re.sub(r"\n+-{3,}\s*$", "", text.rstrip())
    return text.strip()


def is_refusal(answer: str) -> bool:
    low = (answer or "").lower()
    return any(m in low for m in REFUSAL_MARKERS)


def parse_judge_claims(content: str) -> Optional[List[Dict]]:
    """Lenient-parse the judge's JSON, strictly validate the shape.
    Returns a list of {text, verdict, source} or None if unparseable."""
    if not content:
        return None
    m = re.search(r"\{.*\}", content, re.DOTALL)
    raw = m.group(0) if m else content
    try:
        obj = json.loads(raw)
    except Exception:
        return None
    claims = obj.get("claims") if isinstance(obj, dict) else None
    if not isinstance(claims, list):
        return None
    out = []
    for c in claims:
        if not isinstance(c, dict):
            continue
        text = str(c.get("text", "")).strip()
        verdict = str(c.get("verdict", "")).strip().lower()
        if not text or verdict not in VALID_VERDICTS:
            continue
        src = c.get("source")
        src = int(src) if isinstance(src, (int, float)) or (isinstance(src, str) and src.isdigit()) else None
        out.append({"text": text, "verdict": verdict, "source": src})
    return out


def compute_verdict(claims: List[Dict], threshold: float) -> Dict:
    """Aggregate claim verdicts into a faithfulness score + flag.
    flagged when faithfulness < threshold OR any claim is contradicted."""
    n = len(claims)
    n_sup = sum(1 for c in claims if c["verdict"] == "supported")
    n_uns = sum(1 for c in claims if c["verdict"] == "unsupported")
    n_con = sum(1 for c in claims if c["verdict"] == "contradicted")
    faithfulness = (n_sup / n) if n else None
    flagged = bool(n_con) or (faithfulness is not None and faithfulness < threshold)
    return {
        "n_claims": n, "n_supported": n_sup, "n_unsupported": n_uns,
        "n_contradicted": n_con, "faithfulness": faithfulness, "flagged": flagged,
    }


JUDGE_SYSTEM = (
    "You are a strict faithfulness auditor for a retrieval-augmented chat. Judge ONLY "
    "whether each factual claim in the ANSWER is supported by the numbered SOURCE CHUNKS. "
    "Use NO outside knowledge. supported = stated or clearly entailed by a chunk; "
    "contradicted = a chunk states the opposite; unsupported = not found in any chunk "
    "(even if plausibly true). A paraphrase of a chunk's fact is still supported."
)


def build_judge_messages(query: str, answer: str, chunks: List[Dict]) -> List[Dict]:
    """Build the [system,user] messages for the single judging call (§6.3 contract)."""
    src_lines = []
    for i, ch in enumerate(chunks, 1):
        title = ch.get("title", "?")
        source = ch.get("source", "")
        content = ch.get("content", "")
        src_lines.append(f"[{i}] {title} ({source})\n{content}")
    sources = "\n\n".join(src_lines) if src_lines else "(no sources retrieved)"
    user = (
        f"QUERY: {query}\n\nANSWER: {answer}\n\nSOURCES:\n{sources}\n\n"
        'Output ONLY JSON: {"claims":[{"text":"...","verdict":"supported|unsupported|contradicted","source":<n|null>}]}'
    )
    return [{"role": "system", "content": JUDGE_SYSTEM}, {"role": "user", "content": user}]

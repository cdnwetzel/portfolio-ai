#!/usr/bin/env python3
"""Targeted battery for tonight's findings. Asks each question N times on fresh chats through the
live site and records METADATA ONLY: which probe regexes matched (booleans), timing, request_id.
Answer text is held in memory for the regex check and never written (red-lines.md #2).
Usage: python3 scripts/kb_battery.py <label> [reps]  -> eval/results/battery-<label>.jsonl

Probes named bad_* should NOT match; the rest are positive signals. A regex match is a cheap
signal, not a grade: read a surprising hit as "go look", not as a verdict. Probes widened
2026-11-04 so the corrected wording counts (F2 "same Qwen family", F10 "~70").

2026-11-08, after the post-reindex run flagged three CORRECT answers:
  - every probe now reads the answer WITHOUT its FOLLOWUPS chip block (F9 hit a chip);
  - bad_* probes are denial-aware (expectations.bad_claim_hit): "doesn't use Terraform" is not
    a Terraform claim (F4), "not a different family" is not a different-family claim (F2).
    Rows record `denied` so the exemptions can be audited;
  - bad_reverse matched "reverse proxy" (Apache, true) -> now a reverse *tunnel* / ssh -R;
  - bad_rerank_on_A4500 matched any sentence naming both -> now the claim "reranker on A4500";
  - bad_prefix_decode matched "prefix caching makes TTFT faster" (true) -> now prefix caching
    speeding up decode/tokens per second;
  - says_9_5 matched "99.5%" uptime -> needs a non-digit before it;
  - bad_vllm_8004 matched "labrouter on 8004 routes to vLLM on 8007" (true) -> now vLLM *on* 8004;
  - bad_avd_p2v matched the routine-P2V project, a correct and separate item, on the broad
    question -> now P2V/V2V in the same sentence as AVD (the actual blend). avd_specifics
    follows the case study's current facts ("regional pool" is no longer KB wording).
Rows from before this change (battery-pre, battery-post) used the old probes.
Baseline before the 2026-11 KB fixes: battery-pre (2026-11-01), summarised in
plans/kb-answer-quality-fixes-2026-11.md.
"""
import asyncio, json, os, re, sys, time
import websockets
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from expectations import bad_claim_hit, strip_followups

URL = "wss://dev.cwetzel.com/ws/chat"
# (finding id, question, {probe_name: regex}). Probes named bad_* should NOT match.
B = [
 ("F1", "How does this AI system work?", {"bad_rerank_on_A4500": r"rerank\w*[^.,\n]{0,40}\bon (?:the |an? |one of the |two |both )?(?:RTX )?A4500|A4500s?[^.,\n]{0,20}\b(?:run|runs|handle|handles|host|hosts)\b[^.,\n]{0,15}rerank", "rerank_on_5060": r"5060"}),
 ("F1", "Which GPU runs the reranker?", {"bad_rerank_on_A4500": r"rerank\w*[^.,\n]{0,40}\bon (?:the |an? |one of the |two |both )?(?:RTX )?A4500|A4500s?[^.,\n]{0,20}\b(?:run|runs|handle|handles|host|hosts)\b[^.,\n]{0,15}rerank", "rerank_on_5060": r"5060"}),
 ("F2", "How does the faithfulness judge work in the RAG pipeline?", {"bad_diff_family": r"different (model )?famil", "says_same_family": r"same (Qwen |model )?famil|both (are )?(from )?(the )?Qwen"}),
 ("F2", "Is the faithfulness judge independent of the answer model?", {"bad_diff_family": r"different (model )?famil", "says_same_family": r"same (Qwen |model )?famil|both (are )?(from )?(the )?Qwen"}),
 ("F3", "How does the SSH tunnel route traffic from the VPS to the asrock B550?", {"bad_reverse": r"reverse[- ](?:ssh )?tunnel|ssh -R\b|remote port forward", "forward": r"forward|-L\b|local port"}),
 ("F3", "Which side initiates the SSH tunnel?", {"bad_reverse": r"reverse[- ](?:ssh )?tunnel|ssh -R\b|remote port forward", "vps_initiates": r"VPS (initiates|opens|establishes|starts)"}),
 ("F4", "What has Chris built?", {"bad_terraform_ansible": r"Terraform|Ansible"}),
 ("F4", "What infrastructure-as-code tools does Chris use?", {"bad_terraform_ansible": r"Terraform|Ansible", "refuses": r"don.t have that documented|not documented"}),
 ("F5", "Walk me through a major infrastructure project", {"bad_avd_p2v": r"(?:AVD|Azure Virtual Desktop)[^.\n]{0,80}\b(?:P2V|V2V)|\b(?:P2V|V2V)[^.\n]{0,80}(?:AVD|Azure Virtual Desktop)", "avd_specifics": r"99\.5|Citrix|Windows Server 2012|\$155|120 (?:end )?users|regional settings|Singapore|London"}),
 ("F5", "Tell me about the Azure Virtual Desktop migration", {"bad_avd_p2v": r"(?:AVD|Azure Virtual Desktop)[^.\n]{0,80}\b(?:P2V|V2V)|\b(?:P2V|V2V)[^.\n]{0,80}(?:AVD|Azure Virtual Desktop)", "avd_specifics": r"99\.5|Citrix|Windows Server 2012|\$155|120 (?:end )?users|regional settings|Singapore|London"}),
 ("F6", "What happens to the chat if the T5810 is down?", {"bad_vllm_8004": r"vLLM\W{0,3}(?:\w+\W+){0,3}?(?:on|at|port|:)\s*(?:port\s*)?:?8004|8004\W{0,3}(?:is|=|\()\s*(?:the\s+)?vLLM"}),
 ("F7", "What consulting and MSP experience does Chris have?", {"says_18": r"\b18\b", "says_9_5": r"(?<![\d.])9\.5", "names_first_msp": r"Pro Computer"}),
 ("F9", "Why are follow-up answers faster than the first answer?", {"bad_prefix_decode": r"prefix[^.\n]{0,80}(?:speeds? up|faster|increas\w*|boost\w*|improv\w*)[^.,;\n]{0,30}(?:decod|generat|tok(?:en)?s?/s|tokens per second|throughput)", "mtp_accept": r"accept|draft|MTP|speculat"}),
 ("F10", "How fast does the model generate tokens?", {"says_47": r"\b47\b", "says_70": r"\b(6[89]|70)\b", "says_77_79": r"\b7[5-9]\b"}),
]

async def ask(q):
    t0 = time.time(); parts = []; done = {}
    async with websockets.connect(URL, open_timeout=10) as ws:
        await ws.send(json.dumps({"type": "chat", "payload": {"messages": [{"role": "user", "content": q}], "max_tokens": 2048}}))
        while True:
            d = json.loads(await asyncio.wait_for(ws.recv(), 180))
            if d.get("type") == "chunk":
                parts.append(((d.get("data") or {}).get("choices") or [{}])[0].get("delta", {}).get("content") or "")
            elif d.get("type") in ("done", "error"):
                done = d; break
    return strip_followups("".join(parts)), done, round(time.time() - t0, 2)

async def main():
    label = sys.argv[1]; reps = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "eval", "results", f"battery-{label}.jsonl")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, "w").close()
    for r in range(reps):
        for i, (fid, q, probes) in enumerate(B):
            try:
                text, done, total = await ask(q)
            except Exception as e:
                row = {"rep": r, "i": i, "fid": fid, "error": type(e).__name__}
            else:
                t = done.get("timing") or {}
                tok = (done.get("tokens") or {}).get("completion")
                gen, ttft = t.get("generation_ms"), t.get("ttft_ms")
                row = {"rep": r, "i": i, "fid": fid, "request_id": done.get("request_id"),
                       "type": done.get("type"), "total_s": total, "retrieval_ms": t.get("retrieval_ms"),
                       "ttft_ms": ttft, "tok_s": round(tok / ((gen - ttft) / 1000), 1) if tok and gen and ttft and gen > ttft else None,
                       "chars": len(text),
                       "probes": {}, "denied": {}}
                for k, v in probes.items():
                    if k.startswith("bad_"):
                        row["probes"][k], denied = bad_claim_hit(v, text)
                        if denied:
                            row["denied"][k] = True
                    else:
                        row["probes"][k] = bool(re.search(v, text, re.I))
            open(out, "a").write(json.dumps(row) + "\n")
            print(json.dumps(row), flush=True)
            await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(main())

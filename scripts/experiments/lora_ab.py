"""A/B: base qwen2.5-coder-14b vs the pscode-prod LoRA, on identical RAG context.

Runs ON THE VPS, where the SSH tunnel already exposes vLLM (:8004), the proxy
(:8000) and the verifier (:8007). Nothing is restarted and no config changes:
vLLM serves the base and the adapter concurrently, so the A/B is a per-request
model-id switch. The live site is unaffected.

Method mirrors plans/model-faithfulness-ab-qwen3-30b-2026-08.md: hold the
retrieved chunks and the system prompt constant, vary only the model, then score
both answers with the site's own faithfulness judge.

Questions are drawn from the golden set and from the two defects reproduced on
2026-08-19 — never from production traffic (red-lines.md #2).
"""
import ast
import json
import sys
import urllib.request

PROXY = "http://127.0.0.1:8000"
VLLM = "http://127.0.0.1:8004"
VERIFIER = "http://127.0.0.1:8007"
DEPLOYED_PROXY = "/opt/api-proxy/main.py"

BASE_ID = "qwen2.5-coder-14b-pscode"   # parent=None -> the base model
LORA_ID = "pscode-prod"                # parent=BASE_ID -> the adapter

QUESTIONS = [
    "tell me about the Asrock B550",                        # confabulated a Realtek codec
    "does the T5810 have onboard storage?",                 # contradicted retrieved evidence
    "Tell me about the pxx project",                        # prior A/B: pscode 0.42, FLAGGED
    "What consulting and MSP experience does Chris have?",  # prior A/B: pscode 0.64, FLAGGED
    "What has Chris built?",                                # prior A/B: pscode 0.80
]


def post(url, payload, timeout=180):
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def load_prompt_constants(path):
    """Pull SYSTEM_PREFIX/SYSTEM_SUFFIX out of the deployed proxy without importing
    it (module name has a hyphen and pulls in fastapi/httpx)."""
    tree = ast.parse(open(path).read())
    out = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
            if name in ("SYSTEM_PREFIX", "SYSTEM_SUFFIX"):
                out[name] = ast.literal_eval(node.value)
    return out["SYSTEM_PREFIX"], out["SYSTEM_SUFFIX"]


def build_system_prompt(prefix, suffix, chunks):
    s = prefix
    for d in chunks:
        s += f"\n\n### {d.get('title','Unknown')} ({d.get('source','')})\n{d.get('content','')}"
    return s + suffix


def generate(model, system_prompt, question):
    r = post(f"{VLLM}/v1/chat/completions", {
        "model": model,
        "messages": [{"role": "system", "content": system_prompt},
                     {"role": "user", "content": question}],
        # identical sampling to production (api-proxy.py)
        "temperature": 0.2, "top_p": 0.7, "presence_penalty": 0.0,
        "max_tokens": 2048, "stream": False,
    })
    return r["choices"][0]["message"]["content"]


def verify(rid, question, answer, chunks):
    try:
        v = post(f"{VERIFIER}/verify", {
            "request_id": rid, "query": question, "answer": answer,
            "chunks": [{"title": c.get("title", ""), "source": c.get("source", ""),
                        "content": c.get("content", "")} for c in chunks],
        })
        return v.get("faithfulness"), v.get("flagged"), v.get("n_contradicted")
    except Exception as e:
        return None, f"ERR {e}", None


def main():
    prefix, suffix = load_prompt_constants(DEPLOYED_PROXY)
    print(f"prompt constants loaded ({len(prefix)} + {len(suffix)} chars)\n")
    rows = []
    for i, q in enumerate(QUESTIONS):
        chunks = post(f"{PROXY}/api/retrieve", {"query": q}).get("chunks", [])
        sysmsg = build_system_prompt(prefix, suffix, chunks)
        print(f"--- {q}   ({len(chunks)} chunks) ---")
        row = {"q": q, "n_chunks": len(chunks)}
        for label, model in (("base", BASE_ID), ("lora", LORA_ID)):
            ans = generate(model, sysmsg, q)
            f, flag, ncon = verify(f"ab-{label}-{i}", q, ans, chunks)
            row[label] = {"faithfulness": f, "flagged": flag,
                          "n_contradicted": ncon, "len": len(ans), "answer": ans}
            fs = f"{f:.2f}" if isinstance(f, float) else str(f)
            print(f"  {label:5} faith={fs:>5} flagged={flag} "
                  f"contradicted={ncon} len={len(ans)}")
        rows.append(row)

    print("\n=== SUMMARY ===")
    for label in ("base", "lora"):
        vals = [r[label]["faithfulness"] for r in rows
                if isinstance(r[label]["faithfulness"], float)]
        flags = sum(1 for r in rows if r[label]["flagged"] is True)
        mean = sum(vals) / len(vals) if vals else float("nan")
        print(f"{label:5} mean faithfulness={mean:.3f} over n={len(vals)}  flagged={flags}")

    with open("/tmp/lora_ab_result.json", "w") as fh:
        json.dump(rows, fh, indent=2)
    print("\nraw -> /tmp/lora_ab_result.json")


main()

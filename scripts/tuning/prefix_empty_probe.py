#!/usr/bin/env python3
"""Does prefix caching's empty-completion defect survive PRODUCTION sampling?

Background. With --enable-prefix-caching, two of exp_probe.py's three probe-B prompts return
ZERO tokens with finish_reason=stop -- reproduced deterministically in two independent runs
(2026-09-12 23:07 and 23:32), same two positions both times. The same prompts produce 32 tokens
each with the flag off. So it is config-dependent, not prompt-dependent noise.

But exp_probe.py samples at temperature 0, and cwdotcom NEVER does. Production is
temperature=0.2, top_p=0.7, presence_penalty=0.0 over /v1/chat/completions with
enable_thinking=false (cloud/api-proxy.py:668-681). A greedy-only defect that vanishes under
the real sampling policy is a different risk than one that survives it, so measure both rather
than generalising from the probe.

Also relevant to the verdict, from cloud/api-proxy.py: a zero-token response is NOT shown as a
blank bubble -- the proxy emits {"type":"error"} (889-899) and retries once when no token was
emitted (844-874). So the production blast radius of a rare empty is "one retry, then an error
message", not a silent wrong answer.

Run against vLLM directly on the T5810 (:8007) so no VPS hop and no proxy involvement.
Synthetic prompts only, never production traffic (red-lines.md #2).
"""
import argparse, ast, json, pathlib, urllib.request

BASE = "http://127.0.0.1:8007"
PROXY = pathlib.Path(__file__).resolve().parents[2] / "cloud" / "api-proxy.py"


def real_prompt_literals():
    """Return the proxy's actual (SYSTEM_PREFIX, SYSTEM_SUFFIX).

    Read with `ast` rather than imported: `cloud/api-proxy.py` builds a FastAPI app and needs
    httpx at import time, neither of which belongs in a probe running on the T5810. Parsing the
    literal is also exact -- it cannot drift the way a copied-in string would, which is the
    entire defect this function exists to fix.
    """
    tree = ast.parse(PROXY.read_text(encoding="utf-8"), filename=str(PROXY))
    found = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant) \
           and isinstance(node.value.value, str):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id in ("SYSTEM_PREFIX", "SYSTEM_SUFFIX"):
                    found[t.id] = node.value.value
    missing = {"SYSTEM_PREFIX", "SYSTEM_SUFFIX"} - set(found)
    if missing:
        raise SystemExit(
            f"FATAL: cannot read {sorted(missing)} from {PROXY}.\n"
            "       This probe must replay the REAL system prompt; a synthetic stand-in is what\n"
            "       made the earlier 0/40 result overstate its own evidence. Refusing to guess.")
    return found["SYSTEM_PREFIX"], found["SYSTEM_SUFFIX"]


def production_system_prompt(n_chunks=5, chunk_words=900):
    """Rebuild the system message in the shape cloud/api-proxy.py assembles.

    Production is: SYSTEM_PREFIX + server-facts block, then one
    `\\n\\n### {title} ({source})\\n{content}` block per retrieved doc, then SYSTEM_SUFFIX
    (api-proxy.py ~line 793, context_manager.py:152). The chunk TEXT here is synthetic --
    red-lines.md #2 forbids replaying production traffic -- but the structure, the real prompt,
    and the ~11.5K-token scale are what the empty-completion defect would key on.
    """
    prefix, suffix = real_prompt_literals()
    facts = "\n\nSERVER FACTS (authoritative, computed per request):\n- Today's date is 2026-09-14.\n"
    body = []
    for i in range(n_chunks):
        content = (" ".join(
            f"The T5810 serves a 27B model across two A4500 GPUs joined by NVLink, with "
            f"retrieval through a 768-dimensional embedding into Qdrant and a cross-encoder "
            f"reranker on a separate card; paragraph {j} of document {i}."
            for j in range(chunk_words // 35)))
        body.append(f"\n\n### Infrastructure Document {i} (infrastructure)\n{content}")
    return prefix + facts + "".join(body) + suffix

PREFIX = ("You are a retrieval system answering from the sources below.\n\n"
          + "".join(
              f"### Source {i}\nThe T5810 workstation runs two RTX A4500 GPUs joined by an "
              f"NVLink bridge, serving a 27B model with tensor parallelism across both cards. "
              f"Retrieval uses a 768-dimensional bge-base embedding into Qdrant, reranked by a "
              f"cross-encoder on a separate GPU. Document {i} of the corpus.\n\n"
              for i in range(28)))

# The exact probe-B prompts. Items 0 and 2 are the two that come back empty.
B = [PREFIX + f"\n\nQuestion: item {i}, describe the retrieval path.\nAnswer:" for i in range(3)]


def post(path, body, timeout=300):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def model_id():
    return json.load(urllib.request.urlopen(BASE + "/v1/models", timeout=10))["data"][0]["id"]


def completion(m, prompt, max_tokens, **samp):
    d = post("/v1/completions", {"model": m, "prompt": prompt,
                                 "max_tokens": max_tokens, "stream": False, **samp})
    c = d["choices"][0]
    return (c.get("text") or ""), c.get("finish_reason")


def chat(m, system, user, max_tokens, **samp):
    d = post("/v1/chat/completions", {
        "model": m, "max_tokens": max_tokens, "stream": False,
        "chat_template_kwargs": {"enable_thinking": False},
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}], **samp})
    c = d["choices"][0]
    return (c["message"].get("content") or ""), c.get("finish_reason")


def report(label, results):
    empty = sum(1 for t, _ in results if not t.strip())
    reasons = {}
    for _, f in results:
        reasons[f] = reasons.get(f, 0) + 1
    flag = "  <-- EMPTY PRESENT" if empty else ""
    print(f"  {label:52} EMPTY {empty}/{len(results)}  finish={reasons}{flag}")
    return empty


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-n", type=int, default=10, help="samples per cell at production sampling")
    ap.add_argument("--prod-shape", action="store_true",
                    help="ALSO replay the REAL SYSTEM_PREFIX/SYSTEM_SUFFIX from cloud/api-proxy.py "
                         "with production-shaped chunk blocks. Sections 1-3 use a synthetic "
                         "prefix and therefore CANNOT settle production blast radius on their own.")
    a = ap.parse_args()
    if a.n < 1:
        raise SystemExit("FATAL: -n must be >= 1")
    m = model_id()
    print(f"model={m}  n={a.n}  prod_shape={a.prod_shape}\n")

    total = 0
    print("1. REPRODUCE at the probe's sampling (temperature 0, /v1/completions, max_tokens=32)")
    for i, p in enumerate(B):
        total += report(f"probe-B item {i}  temp=0",
                        [completion(m, p, 32, temperature=0.0) for _ in range(3)])

    print("\n2. PRODUCTION sampling (temp=0.2, top_p=0.7, presence_penalty=0, /v1/completions)")
    prod_empty = 0
    for i, p in enumerate(B):
        prod_empty += report(
            f"probe-B item {i}  temp=0.2 top_p=0.7",
            [completion(m, p, 32, temperature=0.2, top_p=0.7, presence_penalty=0.0)
             for _ in range(a.n)])

    print("\n3. PRODUCTION SHAPE: /v1/chat/completions, enable_thinking=false, max_tokens=2048")
    chat_empty = 0
    for i, p in enumerate(B):
        q = p.split("\n\nQuestion: ")[1].replace("\nAnswer:", "")
        chat_empty += report(
            f"chat item {i}  temp=0.2 top_p=0.7",
            [chat(m, PREFIX, q, 2048, temperature=0.2, top_p=0.7, presence_penalty=0.0)
             for _ in range(a.n)])

    prod_shape_empty = None
    if a.prod_shape:
        print("\n4. REAL PRODUCTION PROMPT: cloud/api-proxy.py's SYSTEM_PREFIX + SYSTEM_SUFFIX,")
        print("   production-shaped chunk blocks, /v1/chat/completions, enable_thinking=false")
        sys_prompt = production_system_prompt()
        approx_tok = len(sys_prompt) // 4
        print(f"   system prompt: {len(sys_prompt)} chars (~{approx_tok} tokens), "
              f"real prompt literal read from {PROXY.name}")
        questions = [
            "What GPUs does the T5810 run?",
            "How does the retrieval path work end to end?",
            "What is the reranker and where does it run?",
        ]
        prod_shape_empty = 0
        for i, q in enumerate(questions):
            # Same system prompt every call: that is the CACHE-HIT condition, which is the
            # condition under which the defect appeared at all.
            prod_shape_empty += report(
                f"prod-shape item {i}  temp=0.2 top_p=0.7",
                [chat(m, sys_prompt, q, 2048, temperature=0.2, top_p=0.7, presence_penalty=0.0)
                 for _ in range(a.n)])

    print(f"\n  temp-0 empties: {total}/9")
    print(f"  production-sampling empties (/v1/completions): {prod_empty}/{3*a.n}")
    print(f"  production-shape empties (/v1/chat/completions): {chat_empty}/{3*a.n}")
    # Report the two REQUEST SHAPES separately. An earlier version of this script pooled them
    # into one pass/fail line and printed "the defect SURVIVES production sampling" off a total
    # that mixed 25/30 empties on /v1/completions with 0/30 on /v1/chat/completions. Those are
    # different endpoints and only one of them is production. Averaging across the variable
    # under test is how an instrument manufactures a conclusion -- the same failure this whole
    # line of work keeps turning up.
    print("\n  The two request shapes must be judged separately:")
    print(f"    /v1/completions      (NOT used by cwdotcom): {prod_empty}/{3*a.n} empty")
    print(f"    /v1/chat/completions (what cwdotcom uses):   {chat_empty}/{3*a.n} empty")
    if prod_shape_empty is not None:
        print(f"    REAL production prompt (/v1/chat/completions): {prod_shape_empty}/{3*a.n} empty")

    if chat_empty == 0 and prod_empty > 0:
        print("\n  => On this evidence the defect is confined to the raw-completion shape. cwdotcom"
              "\n     sends only chat completions (cloud/api-proxy.py:_stream_completion), so the"
              "\n     production blast radius is not established by the /v1/completions rows.")
    elif chat_empty:
        print("\n  => the defect reaches the chat-completions shape cwdotcom uses. User-visible.")
    else:
        print("\n  => no empties in either shape at production sampling.")

    # Sections 1-3 use a SYNTHETIC prefix. Saying so is the point: a previous revision printed
    # "Confirm with the REAL system prompt -- see --prod-shape" for an option that was never
    # implemented, and CLAUDE.md then recorded the 0/40 result as having been measured "with the
    # real SYSTEM_PREFIX". It was not. A probe must never let a claim outrun what it measured.
    if prod_shape_empty is None:
        print("\n  !! SECTIONS 1-3 USED A SYNTHETIC PREFIX. Do NOT record this run as evidence"
              "\n     about the real production prompt. Re-run with --prod-shape for that claim.")
    elif prod_shape_empty == 0:
        print("\n  => the REAL production prompt produced no empties. THIS is the row that may be"
              f"\n     cited for production blast radius ({3*a.n} samples, cache-hit condition).")
    else:
        print("\n  => EMPTIES UNDER THE REAL PRODUCTION PROMPT. This is user-visible. Treat as P0.")


main()

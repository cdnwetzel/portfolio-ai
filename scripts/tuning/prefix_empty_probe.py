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
import argparse, json, urllib.request

BASE = "http://127.0.0.1:8007"

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
    a = ap.parse_args()
    m = model_id()
    print(f"model={m}  n={a.n}\n")

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
    if chat_empty == 0 and prod_empty > 0:
        print("\n  => On this evidence the defect is confined to the raw-completion shape. cwdotcom"
              "\n     sends only chat completions (cloud/api-proxy.py:_stream_completion), so the"
              "\n     production blast radius is not established by the /v1/completions rows."
              "\n     Confirm with the REAL system prompt before shipping -- see --prod-shape.")
    elif chat_empty:
        print("\n  => the defect reaches the chat-completions shape cwdotcom uses. User-visible.")
    else:
        print("\n  => no empties in either shape at production sampling.")


main()

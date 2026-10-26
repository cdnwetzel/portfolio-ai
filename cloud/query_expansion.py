"""
Query alias / expansion for the RAG retrieval step (rag-improvements.md §1.2).

Dense cosine search misses when the visitor's wording differs from the KB's wording
("your LLM project" vs the KB's "Qwen inference platform"). Before embedding, we
append a small, curated set of synonym terms for any alias group the query touches,
so the embedded vector lands nearer the relevant chunks. The cross-encoder reranker
still scores candidates against the *original* query, so expansion only widens recall —
it does not change how final relevance is judged.

Pure + dependency-free so it unit-tests without the FastAPI stack.
Source pattern: iChris DEFAULT_ALIAS_GROUPS (broker/mailhistory.py), adapted to
cwdotcom's portfolio KB vocabulary.
"""
import re
from typing import List

# Each group is a set of interchangeable surface forms. If the query contains any
# member (as a whole word/phrase), the *other* members are candidate expansion terms.
# Keep groups tight — over-broad groups dilute the embedding and hurt precision.
ALIAS_GROUPS: List[List[str]] = [
    ["rag", "retrieval augmented generation", "retrieval-augmented generation"],
    ["llm", "large language model", "language model"],
    ["gpu", "gpus", "graphics card", "a4500", "rtx a4500", "video card"],
    ["vllm", "inference server", "inference engine", "model serving"],
    ["avd", "azure virtual desktop", "virtual desktop"],
    ["soc2", "soc 2", "soc-2", "soc2 type ii", "security compliance", "compliance audit"],
    ["sap b1", "sap business one", "business one", "erp"],
    ["dr", "disaster recovery", "backup and recovery", "business continuity"],
    ["lora", "low-rank adaptation", "fine-tune", "fine-tuning", "adapter"],
    ["pscode", "code lora", "python lora"],
    ["pxx", "aider orchestrator", "aider"],
    ["qdrant", "vector db", "vector database", "vector store"],
    ["reranker", "rerank", "cross-encoder", "cross encoder", "bge-reranker"],
    ["embedding", "embeddings", "embedder", "sentence transformer", "minilm"],
    ["t5810", "home server", "homelab", "precision t5810", "dell precision"],
    ["resume", "cv", "experience", "background", "career history"],
    ["school", "college", "education", "university", "degree", "tcnj"],
    # "favorite X" questions retrieved the skills list instead of the stated
    # preference, and the model answered "Bash" against a KB that says Python and
    # SQL (2026-08-29). Pull preference vocabulary toward the Preferences section.
    ["favorite", "favourite", "preferred", "prefers", "preference", "enjoys most", "go-to"],
    ["nvlink", "tensor parallel", "tensor parallelism"],
    ["websocket", "streaming", "real-time chat", "real time chat"],
    # Hindsight vocabulary reaches nothing in the KB, which writes its reflection as "Lessons
    # Learned" (AVD, SAP, ai_portfolio_iterations). Golden question: "What would you do
    # differently if you started over?" -- top rerank score 0.0031, BELOW the 0.0046
    # lowest-on-topic floor in verify_gate.py, rank-1 an unrelated chunk, model refuses 3/3.
    #
    # *** THIS GROUP DOES NOT FIX THAT QUESTION. Verified live after deploy: top score still
    # 0.0031, rank-1 still unrelated, still refuses 3/3. Kept only as a legitimate embedding-side
    # vocabulary bridge. ***
    #
    # The pre-deploy measurement that suggested otherwise (0.0031 -> 0.0055) was INVALID: it fed
    # the pre-expanded string to /api/retrieve, which made it both the embed query AND the rerank
    # query. Production does not do that. `search_knowledge_base` expands only the EMBEDDING
    # (main.py:402) and reranks on the ORIGINAL query (main.py:455) -- the comment there says so
    # explicitly: "the reranker below still scores the ORIGINAL query so final relevance is
    # unchanged."
    #
    # So there is a structural ceiling on what any alias group can achieve: expansion changes
    # WHICH CANDIDATES Qdrant returns, and can never change how the cross-encoder ranks them.
    # When a question's vocabulary does not match the corpus, expansion pulls the right chunk
    # into the candidate set and the reranker then discards it -- exactly what happens here (AVD
    # Migration moved rank 4 -> 3, score unchanged at 0.0007). Reranking on the expanded query
    # would lift that ceiling and is a real experiment, but it changes relevance for every query
    # and must be A/B'd, not assumed.
    ["lessons learned", "lesson", "hindsight", "do differently", "done differently",
     "started over", "start over", "mistakes", "what went wrong", "retrospective",
     "looking back", "in retrospect"],
]

# Cap appended terms so the embedding stays anchored to the real query.
MAX_EXPANSION_TERMS = 8


def _present(term: str, low_query: str) -> bool:
    """True if `term` appears as a whole word/phrase in the lowercased query.
    Word boundaries stop short tokens like 'dr'/'b1' from matching inside other
    words ('address', 'b12')."""
    return re.search(r"\b" + re.escape(term) + r"\b", low_query) is not None


def expansion_terms(query: str) -> List[str]:
    """Return the de-duplicated synonym terms to append for this query (no original)."""
    low = query.lower()
    out: List[str] = []
    seen = set()
    for group in ALIAS_GROUPS:
        matched = [t for t in group if _present(t, low)]
        if not matched:
            continue
        for term in group:
            if term in matched:
                continue  # already in the query
            if term in seen or _present(term, low):
                continue  # don't duplicate
            seen.add(term)
            out.append(term)
    return out[:MAX_EXPANSION_TERMS]


def expand_query(query: str) -> str:
    """Original query + appended alias synonyms (for embedding). Returns the query
    unchanged when nothing matches, so behavior is a no-op on novel vocabulary."""
    terms = expansion_terms(query)
    if not terms:
        return query
    return query + " " + " ".join(terms)

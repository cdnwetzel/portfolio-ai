# Test Plan (Day 30 MVP)

**Project:** Portfolio AI SaaS  
**Scope:** Website + AI Chat Demo (No SaaS features)  
**Date:** 2026-06-06  
**Version:** GATE 1 Planning

---

## Testing Strategy

**Goal:** Verify that the website and AI chat work reliably, accurately, and fast.

**Coverage Target:** 80%+ line coverage (pytest)  
**Performance Target:** p90 latency <500ms, throughput >50 tok/sec  
**Accuracy Target:** >90% of responses are accurate, <1% hallucination rate  

**Testing Phases:**
1. **Unit Tests** (GATE 2, days 10–15) — Functions work in isolation
2. **Integration Tests** (GATE 2, days 15–20) — Endpoints + RAG + vLLM work together
3. **Performance Tests** (GATE 3, days 21–25) — Latency, throughput, concurrent users
4. **Manual Smoke Tests** (GATE 3, days 23–25) — Quality of responses
5. **Soft Launch** (GATE 5, days 28–30) — Real users, monitor for 24h

---

## Unit Tests

### Auth & Security (No auth day 30, but useful for day 60+)

**Test file:** `tests/test_security.py`

```python
def test_rate_limit_per_ip():
    """Rate limiter blocks after 100 requests/min"""
    # 101 requests from IP 127.0.0.1
    # Request 101 returns 429 Too Many Requests

def test_input_validation_rejects_oversized():
    """Rejects queries > 1000 characters"""
    # Query with 1001 chars returns 400 Bad Request

def test_input_validation_rejects_null():
    """Rejects empty/null queries"""
    # Empty query returns 400 Bad Request

def test_input_validation_sanitizes_special_chars():
    """Special characters don't break prompt"""
    # Query with '; DROP TABLE --' is sanitized
    # LLM sees plain text, no SQL injection
```

### RAG (Retrieval-Augmented Generation)

**Test file:** `tests/test_rag.py`

```python
def test_qdrant_loads_knowledge_base():
    """Knowledge base loads on startup"""
    # Qdrant contains ~12 documents
    # Each document has embeddings
    # Total docs indexed correctly

def test_embedding_generation():
    """Queries are converted to embeddings"""
    # Query "Azure experience" → embedding vector
    # Embedding has 384 dimensions (bge-small)

def test_retrieval_returns_top_5():
    """Search returns top-5 most similar documents"""
    # Query about Azure → returns Azure case study + relevant experiences
    # Results ranked by similarity

def test_retrieval_relevance():
    """Top-5 results include relevant content"""
    # Query "SOC2 compliance" → returns SOC2 case study in top-5
    # Accuracy >90% (manual verification)

def test_context_building():
    """Retrieved docs are formatted into prompt context"""
    # Raw docs → formatted context string
    # Prompt = system + context + user query
```

### Inference

**Test file:** `tests/test_inference.py`

```python
def test_vllm_connection():
    """vLLM service is accessible"""
    # Connect to vLLM endpoint
    # Health check returns 200

def test_inference_streaming():
    """Inference returns tokens one at a time"""
    # Query generates response
    # Tokens arrive as stream, not all at once

def test_inference_latency():
    """First token arrives within 100–500ms"""
    # Measure p50 latency
    # p50 < 100ms, p90 < 500ms

def test_inference_max_length():
    """Responses capped at 2000 tokens"""
    # Very long query doesn't produce 5000 token response
    # Response ends at 2000 tokens

def test_inference_temperature():
    """Response quality is consistent (not random)"""
    # Same query run twice produces similar (not identical) responses
    # Temperature=0.7 balances creativity/consistency

def test_inference_timeout():
    """Inference timeout handled gracefully"""
    # If vLLM hangs for 30s, return error (not infinite wait)
```

### Response Quality

**Test file:** `tests/test_response_quality.py`

```python
def test_response_grammar():
    """Responses are grammatically correct"""
    # Parse response for basic grammar
    # No partial sentences at end (streaming integrity)

def test_response_on_topic():
    """Response answers the user's question"""
    # Query "your Azure experience"
    # Response mentions Azure, not random topic

def test_response_no_hallucination():
    """Response doesn't make up facts"""
    # Query "did you work at Apple?"
    # Response correctly says "no" (not in knowledge base)

def test_response_cites_knowledge_base():
    """Response is grounded in retrieved content"""
    # Specific facts (dates, metrics) come from documents
    # Not invented details

def test_response_professional_tone():
    """Response maintains professional, conversational tone"""
    # No emoji, slang, or unprofessional language
    # Appropriate for law firm/enterprise audience
```

---

## Integration Tests

### API Endpoints

**Test file:** `tests/test_api_endpoints.py`

```python
async def test_get_landing_page():
    """GET / returns HTML landing page"""
    client = AsyncClient(app)
    response = await client.get("/")
    assert response.status_code == 200
    assert "cwetzel.com" in response.text
    assert "Chat with AI" in response.text

async def test_get_chat_ui():
    """GET /chat returns chat interface"""
    response = await client.get("/chat")
    assert response.status_code == 200
    assert "Chat" in response.text  # React component loaded

async def test_health_check():
    """GET /health returns system status"""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "uptime_seconds" in data
    assert "gpu_utilization" in data
    assert data["status"] == "ok"
```

### WebSocket Chat Flow

**Test file:** `tests/test_websocket_chat.py`

```python
async def test_websocket_chat_basic():
    """User can send query and receive streaming response"""
    async with AsyncClient(app) as client:
        async with client.websocket_connect("/ws/chat") as ws:
            # Send query
            await ws.send_json({"query": "Tell me about your Azure experience"})
            
            # Receive tokens
            response_text = ""
            async for message in ws.iter_text():
                token_data = json.loads(message)
                if token_data.get("token") != "<END>":
                    response_text += token_data["token"]
            
            assert "Azure" in response_text
            assert len(response_text) > 50

async def test_websocket_concurrent_requests():
    """Multiple concurrent users can chat simultaneously"""
    # 5 simultaneous WebSocket connections
    # Each sends different query
    # All receive responses without errors

async def test_websocket_rate_limiting():
    """Rate limiting applies to WebSocket"""
    # Send 101 messages in 60 seconds
    # 101st message is rejected or queued

async def test_websocket_handles_invalid_json():
    """Invalid JSON in message is handled gracefully"""
    async with client.websocket_connect("/ws/chat") as ws:
        await ws.send_text("not json")
        # Connection closes cleanly or returns error message
```

### End-to-End Flows

**Test file:** `tests/test_e2e_flows.py`

```python
async def test_e2e_chat_about_background():
    """Full flow: query about Chris's background"""
    # Open page
    # Ask: "What's your IT experience?"
    # Receive response mentioning 26 years, enterprise infrastructure
    # Response is coherent and accurate

async def test_e2e_chat_about_azure():
    """Full flow: query about Azure VDI migration"""
    # Ask: "Tell me about your Azure VDI experience"
    # Response mentions 120→200 user migration, regional distribution
    # Metrics align with case study

async def test_e2e_chat_about_compliance():
    """Full flow: query about SOC2 compliance"""
    # Ask: "Describe your SOC2 experience"
    # Response covers audit process, gaps, remediation
    # Shows deep knowledge, not generic answer

async def test_e2e_chat_edge_case_empty():
    """Empty query is rejected"""
    # Send empty query
    # Returns error message (not crash)

async def test_e2e_chat_edge_case_long_query():
    """Very long query (1001 chars) is rejected"""
    # Send 1001 char query
    # Returns 400 Bad Request or validation error

async def test_e2e_chat_edge_case_special_chars():
    """Query with special characters is handled"""
    # Query: "What's your experience with <script>alert('xss')</script>?"
    # Response is normal (prompt injection attempt thwarted)

async def test_e2e_chat_unknown_topic():
    """Query about topic not in knowledge base"""
    # Query: "What's your experience with quantum computing?"
    # Response: "I haven't worked with quantum computing..."
    # Not hallucination (correctly admits not in knowledge base)
```

---

## Performance Tests

### Latency Benchmarks

**Test file:** `tests/test_performance.py`

**Metrics to measure:**
- **p50 latency** (50th percentile): Time to first token
- **p90 latency** (90th percentile): Most user experience this
- **p99 latency** (99th percentile): Worst-case user

**Test cases:**

```python
def test_latency_first_token():
    """First token arrives within target"""
    for _ in range(100):
        query = "Tell me about your experience"
        start = time.time()
        token_generator = chat_stream(query)
        first_token = next(token_generator)
        latency = time.time() - start
        latencies.append(latency)
    
    p50 = np.percentile(latencies, 50)
    p90 = np.percentile(latencies, 90)
    p99 = np.percentile(latencies, 99)
    
    assert p50 < 100, f"p50 is {p50}ms, target <100ms"
    assert p90 < 500, f"p90 is {p90}ms, target <500ms"
    assert p99 < 1000, f"p99 is {p99}ms, target <1000ms"

def test_latency_full_response():
    """Full response time reasonable"""
    # Time to generate full 500-token response
    # At 50 tok/sec, should be ~10 seconds
    # But user sees first token in <500ms (feels fast)
```

### Throughput Tests

**Test file:** `tests/test_throughput.py`

```python
def test_throughput_tokens_per_second():
    """vLLM generates >50 tokens/sec"""
    query = "Tell me about your entire 26-year career in detail"
    start = time.time()
    tokens = 0
    for token in chat_stream(query):
        tokens += 1
    elapsed = time.time() - start
    
    tok_per_sec = tokens / elapsed
    assert tok_per_sec > 50, f"Throughput is {tok_per_sec} tok/sec, target >50"

def test_throughput_concurrent_users():
    """Multiple concurrent users don't significantly impact throughput"""
    # Single user: 50 tok/sec
    # 5 concurrent users: 45+ tok/sec each (acceptable degradation)
```

### Concurrency Tests

**Test file:** `tests/test_concurrency.py`

```python
async def test_concurrent_5_users():
    """5 simultaneous requests are handled"""
    queries = [
        "Your Azure experience",
        "SOC2 compliance work",
        "VMware background",
        "SAP integration project",
        "Disaster recovery planning"
    ]
    
    async def run_query(q):
        async with client.websocket_connect("/ws/chat") as ws:
            await ws.send_json({"query": q})
            response = ""
            async for msg in ws.iter_json():
                response += msg.get("token", "")
            return response
    
    responses = await asyncio.gather(*[run_query(q) for q in queries])
    
    # All 5 responses complete without error
    assert len(responses) == 5
    assert all(r for r in responses)  # All non-empty

async def test_concurrent_10_users():
    """10 simultaneous requests are handled"""
    # (Same as above, 10 queries)
    # May take longer, but all complete

async def test_concurrent_with_queue():
    """Request queue handles overflow gracefully"""
    # 20 simultaneous requests
    # First 8 might complete immediately
    # Remaining 12 queued
    # All eventually complete (queue size limit respected)
```

---

## Manual Smoke Tests (GATE 3)

**These are manual tests done by human before soft launch.**

### Sanity Checks

```
[ ] Landing page loads (cwetzel.com/)
[ ] Chat interface loads (cwetzel.com/chat)
[ ] Styling looks good (not broken layout)
[ ] Links work (navigation, chat link)
[ ] No console errors (browser dev tools)
[ ] HTTPS works (green lock in browser)
```

### Chat Quality (Manual)

Test these 10+ queries manually, verify responses:

```
[ ] "Who are you?"
    → Should mention Chris, IT Manager, 26 years

[ ] "Tell me about your Azure experience"
    → Should mention AVD migration, 200 users, regional

[ ] "What's your SOC2 experience?"
    → Should cover audit process, gaps, remediation

[ ] "Describe your VMware background"
    → Should mention P2V, infrastructure design

[ ] "Tell me about your disaster recovery work"
    → Should cover BDR, off-site backups, failover

[ ] "What programming languages do you know?"
    → Should mention PowerShell, Python, SQL

[ ] "How long have you been in IT?"
    → Should say 26 years

[ ] "Have you worked with Kubernetes?"
    → Should honestly say "not a focus" or similar (not hallucinate)

[ ] "What's the most complex project you've done?"
    → Should mention big infrastructure/compliance project

[ ] "Can you help me with [unrelated question]?"
    → Should politely redirect to IT/infrastructure expertise
```

### Performance (Manual)

```
[ ] First token appears within ~1 second (subjective, feels fast)
[ ] Full response completes in <10 seconds (2000 tokens at 50 tok/sec)
[ ] No significant lag during 5 concurrent chats
[ ] Response quality consistent across multiple runs (no degradation)
```

### Edge Cases (Manual)

```
[ ] Empty query: Returns error (not crash)
[ ] Very long query (1000+ chars): Handled gracefully
[ ] Special characters in query: Processed safely (no prompt injection)
[ ] Rapid consecutive queries: Queue handles without losing messages
[ ] Close browser during response: Websocket closes cleanly
[ ] Network slow/lossy: Graceful degradation (errors shown, not hangs)
```

---

## Soft Launch Testing (GATE 5, Days 28–30)

### Beta Tester Feedback

**Send to 5–10 beta testers:**
- Friends
- Law firm colleagues
- LinkedIn connections in IT/security space

**Instructions:**
```
"Chat with AI trained on my background. Try asking:
- Questions about my experience
- Specific projects you've heard me mention
- Topics unrelated to IT (to see how it handles)

Please report:
- Does it work? (yes/no)
- Are responses accurate? (yes/no/partially)
- Any bugs or crashes? (describe)
- How fast? (very fast/fast/okay/slow)
"
```

### Monitoring (24h Soft Launch)

**Collect metrics during 24h period after launch:**

```
[ ] Uptime: ≥99% (alert if down)
[ ] Latency: p90 <500ms (alert if not)
[ ] Error rate: <1% of requests fail (alert if >1%)
[ ] GPU utilization: <90% (alert if maxed out)
[ ] WireGuard tunnel: Stable, <1 reconnect
[ ] Qdrant: All queries return results (no hangs)
[ ] No authentication/permission issues (open access)
```

### Lessons Learned

**Document after soft launch:**
```
[ ] What worked well?
[ ] What was slower than expected?
[ ] Any bugs found?
[ ] Beta tester feedback?
[ ] Any scaling concerns?
[ ] Ready for public launch? (GO / HOLD for fixes)
```

---

## Test Execution Timeline

### GATE 2 (Days 4–20): Development + Unit/Integration Tests

| Day | Task | Owner |
|-----|------|-------|
| 4–8 | Write unit tests for RAG, inference | Chris |
| 8–12 | Write integration tests for API | Chris |
| 12–15 | Build features (website, chat, RAG) | Chris |
| 15–20 | Run tests as features complete | Chris |
| Target | 80%+ test coverage | |

### GATE 3 (Days 21–25): Performance + Manual Tests

| Day | Task | Owner |
|-----|------|-------|
| 21–23 | Performance testing (latency, throughput) | Chris |
| 23–24 | Manual smoke tests (10+ queries) | Chris |
| 24–25 | Security audit (input validation, rate limiting) | Chris |
| Target | p90 <500ms, >90% response accuracy | |

### GATE 4 (Days 26–27): Deployment

| Day | Task | Owner |
|-----|------|-------|
| 26–27 | Deploy to cloud, test rollback | Chris |
| Target | Zero deployment errors | |

### GATE 5 (Days 28–30): Soft Launch + Monitoring

| Day | Task | Owner |
|-----|------|-------|
| 28 | Share link with 5–10 beta testers | Chris |
| 28–29 | Monitor 24h (uptime, latency, errors) | Chris |
| 29–30 | Collect feedback, document lessons learned | Chris |
| 30 | Go/No-Go decision: Ready for public? | Chris |

---

## Test Coverage Goals

### Line Coverage (Code)
- **Target:** 80%+ coverage by pytest
- **Core functions:** 100% (auth, RAG, inference, API)
- **Utilities:** 70%+ (helpers, formatting)
- **Edge cases:** All error paths tested

### Functional Coverage
- **Landing page:** Load, styling, links
- **Chat interface:** Send query, receive response, handle errors
- **RAG:** Load docs, retrieve top-5, build context
- **Inference:** vLLM connect, stream tokens, timeout handling
- **WebSocket:** Concurrent connections, rate limiting, close handling

### Non-Functional Coverage
- **Performance:** p50, p90, p99 latencies measured
- **Security:** Input validation, rate limiting tested
- **Availability:** Uptime monitored during soft launch
- **Accuracy:** 10+ manual queries verify response quality

---

## Test Failure Criteria

**If any of these fail, HOLD the launch:**

```
LAUNCH BLOCKERS:
❌ p90 latency > 500ms → Optimize or delay launch
❌ Response accuracy <90% → Improve RAG or model
❌ Error rate >1% → Fix bugs before launch
❌ Any security issues found → Fix before public access
❌ Uptime <99% during 24h monitoring → Investigate root cause
❌ WireGuard tunnel unstable → Fix tunnel before launch
❌ vLLM crashes on load → Fix before launch

SOFT WARNINGS (monitor, but OK to launch):
⚠️  GPU utilization >85% → Monitor during soft launch
⚠️  Hallucination rate 1–2% → Acceptable but watch
⚠️  Some edge cases fail → Fix in day-60+ iteration
```

---

## Post-Launch Improvements (Day 60+)

Once day-30 MVP is live, prioritize:

```
[ ] Add chat history persistence (optional)
[ ] Improve RAG retrieval (better chunking, re-ranking)
[ ] Add user feedback loop (thumbs up/down → improve)
[ ] Monitor real user queries, improve responses
[ ] Analyze hallucination patterns, refine prompt
[ ] Prepare for SaaS phase (user auth, billing)
```

---

**Status:** GATE 1 Test Planning Complete  
**Next:** GATE 2 Implementation + Testing  
**Last Updated:** 2026-06-06

# AI Study Coach - Next Improvements Roadmap

## Overview
This document outlines the high-priority improvements to implement after the critical stability and performance fixes. These are grouped by impact, complexity, and timeline.

---

## Phase 2: High-Impact Features (2-3 weeks)

### 1. Caching Layer (Priority: HIGH)
**Problem:** Re-running the same document re-analyzes all chunks from scratch.
**Impact:** 90% time savings on repeated runs, 50% for partial re-runs.

**Implementation:**
```python
# Cache structure: ~/.ai_study_coach_cache/
# {document_hash}/
#   - chunks.pkl
#   - chunk_1_analysis.pkl
#   - chunk_2_analysis.pkl
#   - full_analysis.pkl
#   - metadata.json
```

**Features:**
- Hash-based caching using file content + mode
- Invalidation when document/config changes
- Optional `--no-cache` flag to bypass
- Cache size management (cleanup old entries)
- Persistent storage in user's home directory

**Estimated effort:** 4-6 hours

---

### 2. Configuration File Support (Priority: HIGH)
**Problem:** All parameters are hardcoded in utils.py; difficult to customize.
**Impact:** Flexible deployment, easy customization for different use cases.

**Implementation:**

**~/.ai_study_coach/config.yaml**
```yaml
llm:
  provider: openai
  model: gpt-4o-mini
  timeout_seconds: 30
  max_retries: 3
  retry_base_delay: 1.0
  retry_max_delay: 30.0

analysis:
  max_workers: 4
  chunk_strategy: size_based  # or heading_based, page_based
  target_sections_small: 3
  target_sections_medium: 6
  target_sections_large: 10

output:
  default_mode: medium
  default_quiz_count: 5
  json_export: false
  
caching:
  enabled: true
  cache_dir: ~/.ai_study_coach_cache
  max_cache_size_mb: 500
```

**CLI Overrides:**
```bash
python3 main.py lecture.txt \
  --config ~/.ai_study_coach/custom.yaml \
  --llm.model gpt-4-turbo \
  --analysis.max_workers 8
```

**Estimated effort:** 3-4 hours

---

### 3. Async I/O Implementation (Priority: MEDIUM)
**Problem:** ThreadPoolExecutor has GIL limitations; poor for I/O-bound operations.
**Impact:** Better scalability, support for 20+ concurrent chunks.

**Current approach:**
```python
ThreadPoolExecutor(max_workers=4)
```

**Target approach:**
```python
async def analyze_chunks_async(llm_client, chunks, ...):
    tasks = [
        analyze_single_chunk_async(chunk) 
        for chunk in chunks
    ]
    return await asyncio.gather(*tasks)
```

**Benefits:**
- True concurrency without GIL
- Better handling of I/O waits
- Compatible with async LLM clients
- Cleaner error handling with gather

**Estimated effort:** 6-8 hours

---

## Phase 3: LLM Provider Ecosystem (2-3 weeks)

### 4. Multi-Provider Support (Priority: MEDIUM)

**Currently supported:**
- OpenAI ✓
- Mock ✓

**To add:**
- Anthropic Claude
- Google Gemini
- Azure OpenAI
- Local LLaMA (via Ollama)

**Architecture:**
```python
# Create abstract base
class LLMProvider(ABC):
    @abstractmethod
    def analyze_chunk(self, chunk, mode, title) -> ChunkAnalysis: ...
    @abstractmethod
    def generate_study_material(...) -> StudyMaterial: ...

# Implementations
class OpenAIProvider(LLMProvider): ...
class AnthropicProvider(LLMProvider): ...
class GeminiProvider(LLMProvider): ...
class OllamaProvider(LLMProvider): ...
```

**CLI:**
```bash
# Claude
python3 main.py lecture.txt --provider anthropic --model claude-3-opus

# Gemini
python3 main.py lecture.txt --provider gemini --model gemini-pro

# Local
python3 main.py lecture.txt --provider ollama --model llama2
```

**Estimated effort:** 8-10 hours (1 hour per provider)

---

### 5. Token Usage & Cost Tracking (Priority: LOW)
**Problem:** No visibility into API costs or token consumption.
**Impact:** Budget tracking, optimization, reporting.

**Features:**
```python
# Track per-run
run_metrics = {
    "total_tokens_used": 15234,
    "total_tokens_cached": 3421,
    "estimated_cost_usd": 0.45,
    "input_tokens": 12000,
    "output_tokens": 3234,
    "model": "gpt-4o-mini",
    "duration_seconds": 125
}

# Summary report
python3 main.py lecture.txt --metrics --json-metrics metrics.json
```

**Output:**
```json
{
  "run_id": "abc123",
  "timestamp": "2026-04-22T08:51:00Z",
  "document": "lecture.txt",
  "model": "gpt-4o-mini",
  "chunks_processed": 13,
  "tokens_input": 12000,
  "tokens_output": 3234,
  "tokens_cached": 3421,
  "estimated_cost_usd": 0.0457,
  "duration_seconds": 125,
  "efficiency_tokens_per_second": 122.7
}
```

**Estimated effort:** 4-5 hours

---

## Phase 4: Data Quality & Testing (2-3 weeks)

### 6. Comprehensive Unit Tests (Priority: HIGH)
**Problem:** No test suite; risky to refactor.
**Impact:** Confidence in changes, catch regressions.

**Structure:**
```
tests/
├── unit/
│   ├── test_parsing.py          # _read_text_file, _normalize_text
│   ├── test_chunking.py         # build_chunks, _split_blocks
│   ├── test_analysis.py         # analyze_chunk, aggregate_analysis
│   ├── test_schemas.py          # Pydantic validation
│   └── test_llm_providers.py    # Mock, OpenAI, etc.
├── integration/
│   ├── test_end_to_end.py       # Full pipeline
│   ├── test_pdf_parsing.py      # Real PDFs
│   └── test_large_documents.py  # >10MB documents
└── fixtures/
    ├── sample_lectures/
    └── expected_outputs/
```

**Test coverage targets:**
- Parsing: 95%
- Chunking: 90%
- Analysis: 85%
- CLI: 80%

**Estimated effort:** 10-12 hours

---

### 7. PDF Parsing Improvements (Priority: MEDIUM)
**Problem:** PyPDF loses formatting, tables, images.
**Impact:** Better extraction from complex PDFs.

**Current:**
```python
from pypdf import PdfReader
```

**Upgrade path:**
```python
# Option 1: Better extraction
try:
    extracted = pdfplumber.open(file).extract_text()  # Better formatting
except:
    extracted = pypdf_extract(file)  # Fallback
```

**Option 2: OCR for scanned PDFs:**
```python
if extracted.strip():
    return extracted
else:
    # Scanned PDF - use OCR
    images = pdf_to_images(file)
    text = pytesseract.image_to_string(images)
    return text
```

**Dependencies:**
- `pdfplumber==0.10.0` (better extraction)
- `pytesseract==0.3.13` (OCR, optional)

**Estimated effort:** 6-8 hours

---

### 8. Realistic Mock LLM Improvements (Priority: MEDIUM)
**Problem:** Mock LLM returns identical outputs; poor for testing aggregation logic.
**Impact:** Better testing of edge cases in merging/deduplication.

**Enhancements:**
```python
# Current: Fixed response
def analyze_chunk(self, chunk, ...):
    return ChunkAnalysis(
        topics=[TopicInfo(...)],  # Same topics every time
        definitions=[...],         # Same definitions
    )

# Enhanced: Realistic variation
def analyze_chunk(self, chunk, ...):
    # Vary based on chunk content
    text_length = len(chunk.text)
    topic_count = 2 + (text_length % 5)  # 2-7 topics
    definition_count = max(1, text_length // 500)  # Scale with content
    
    return ChunkAnalysis(
        topics=[randomly_generated_topics(topic_count)],
        definitions=[randomly_generated_definitions(definition_count)],
        key_points=[randomly_generated_points(3-5)],
    )
```

**Estimated effort:** 3-4 hours

---

## Phase 5: Advanced Features (3-4 weeks)

### 9. Distributed Processing (Priority: LOW)
**Problem:** Single-machine processing limits scalability.
**Impact:** Process 100+ chunk documents, multi-machine setups.

**Architecture:**
```python
# Using Ray Distributed Computing
import ray

@ray.remote
def analyze_chunk_distributed(chunk, llm_config):
    llm = create_llm(**llm_config)
    return llm.analyze_chunk(chunk, ...)

# Process across cluster
futures = [
    analyze_chunk_distributed.remote(chunk, llm_config)
    for chunk in chunks
]
analyses = ray.get(futures)
```

**Benefits:**
- Process 1000+ chunks efficiently
- Cross-machine load balancing
- Fault tolerance built-in
- Auto-scaling support

**Estimated effort:** 12-15 hours

---

### 10. Web Interface (Priority: LOW)
**Problem:** CLI-only interface; limited accessibility.
**Impact:** Reach non-technical users, easier integration.

**Stack:**
- Frontend: React/Vue.js with drag-drop file upload
- Backend: FastAPI/Flask wrapping the pipeline
- Real-time updates: WebSockets for progress tracking

**Features:**
- File upload interface
- Mode/quiz-count selectors
- Real-time progress streaming
- Download Markdown/JSON
- History/caching UI
- Cost tracking dashboard

**Estimated effort:** 20-30 hours

---

## Phase 6: Production Hardening (1-2 weeks)

### 11. Monitoring & Observability (Priority: MEDIUM)
**Problem:** No visibility into system health in production.
**Impact:** Catch issues before users do.

**Implementation:**
```python
# Structured logging to external service
from pythonjsonlogger import jsonlogger

handler = logging.FileHandler('logs/app.jsonl')
handler.setFormatter(jsonlogger.JsonFormatter())
logger.addHandler(handler)

# Track to monitoring service
from opentelemetry import trace
tracer = trace.get_tracer(__name__)

with tracer.start_as_current_span("analyze_chunks") as span:
    span.set_attribute("chunk_count", len(chunks))
    span.set_attribute("mode", summary_mode)
```

**Tools:**
- ELK Stack (Elasticsearch, Logstash, Kibana)
- Or: Datadog, New Relic, Grafana

**Estimated effort:** 6-8 hours

---

### 12. Rate Limiting & Quota Management (Priority: MEDIUM)
**Problem:** No protection against excessive API usage; can drain budget.
**Impact:** Budget safety, fair resource sharing.

**Implementation:**
```python
from ratelimit import limits, sleep_and_retry
import time

CALLS_PER_MINUTE = 20

@sleep_and_retry
@limits(calls=CALLS_PER_MINUTE, period=60)
def analyze_chunk_rate_limited(self, chunk, ...):
    return self._chunk_chain.invoke(...)
```

**Features:**
- Per-minute/hour/day limits
- Quota tracking
- Alert when approaching limits
- Graceful degradation (queue excess requests)

**Estimated effort:** 3-4 hours

---

## Priority Matrix

```
          Impact
High      │
          │  [1] Caching     [4] Multi-Provider   [10] Web UI
          │  [2] Config      [5] Token Tracking   [11] Monitoring
          │  [6] Unit Tests  [9] Distributed      [12] Rate Limit
          │
Medium    │  [3] Async I/O   [7] PDF Improvements
          │  [8] Better Mock
          │
Low       │
          └─────────────────────────────────────
            Easy             Moderate    Hard
            (Effort)
```

---

## Recommended Implementation Order

**Week 1:**
1. Unit Tests (foundation for everything)
2. Caching Layer (quick wins, big impact)
3. Configuration Files (enables flexibility)

**Week 2:**
4. Async I/O (performance improvement)
5. Better Mock LLM (better testing)
6. PDF Parsing (data quality)

**Week 3:**
7. Multi-Provider Support (market reach)
8. Token Tracking (user visibility)

**Week 4+:**
9. Distributed Processing (scale)
10. Web Interface (accessibility)
11. Monitoring (production readiness)
12. Rate Limiting (stability)

---

## Dependencies to Add

| Feature | Package | Version | Notes |
|---------|---------|---------|-------|
| Caching | pickle (stdlib) | - | Built-in, no install needed |
| Config | pyyaml | 6.0+ | For YAML parsing |
| Async | asyncio (stdlib) | - | Built-in |
| PDF Better | pdfplumber | 0.10.0+ | Optional for better extraction |
| OCR | pytesseract | 0.3.13+ | Optional for scanned PDFs |
| Ray | ray | 2.10.0+ | For distributed processing |
| FastAPI | fastapi | 0.104.0+ | For web interface |
| Monitoring | python-json-logger | 2.0.0+ | For JSON logging |
| Rate Limit | ratelimit | 2.2.1+ | For quota management |

---

## Success Metrics

For each improvement, measure:

1. **Performance:**
   - Speed improvement (%)
   - Memory usage (MB)
   - API calls reduced (%)

2. **Quality:**
   - Test coverage increase (%)
   - Bugs found/fixed
   - User-reported issues

3. **Adoption:**
   - Configuration usage
   - Cache hit rate
   - Provider distribution

---

## Risk Mitigation

### Backward Compatibility
- All new features behind feature flags
- Existing CLI interface unchanged
- Config files optional (defaults work)

### Testing Strategy
- Unit tests before refactoring
- Integration tests after features
- Manual testing with real documents

### Rollback Plan
- Each phase is independently deployable
- Git tags for each phase completion
- Easy rollback with previous config

---

## Timeline Estimate

| Phase | Features | Weeks | Team |
|-------|----------|-------|------|
| 2 | Caching, Config, Async | 2-3 | 1-2 devs |
| 3 | Providers, Tracking | 2-3 | 1 dev |
| 4 | Tests, PDF, Mock | 2-3 | 1-2 devs |
| 5 | Distributed, Web | 3-4 | 2-3 devs |
| 6 | Monitoring, Rate Limit | 1-2 | 1 dev |
| **Total** | **12 features** | **11-15 weeks** | **1-3 devs** |

---

## Decision Points

**Should we do distributed processing?**
- YES if: Expecting 1000+ chunk documents, multi-user cloud deployment
- NO if: Single-machine, <100 chunks typical

**Should we build web interface?**
- YES if: Non-technical user base, SaaS offering
- NO if: Developer tool, CLI-only workflow

**Should we support multiple LLMs?**
- YES if: Want flexibility, reduce vendor lock-in, cost optimization
- NO if: OpenAI is mandatory, no other budget

---

## Success Criteria

✅ All 12 improvements delivered → **Production-ready platform**
✅ >90% test coverage → **Confident refactoring**
✅ Sub-minute processing (13 chunks) → **User satisfaction**
✅ <$1 per lecture (at OpenAI rates) → **Economically viable**
✅ <5 retries needed for success → **Reliable**
✅ Web interface + CLI available → **Accessible to all**

---

## Questions for Stakeholders

1. What is the target number of concurrent users?
2. What is the maximum acceptable cost per lecture?
3. Which LLM providers are required?
4. Is distributed processing needed?
5. Who is the primary user (developers, students, educators)?
6. What is the timeline for each phase?

**Next step:** Prioritize with team and assign Phase 2 work.
# Kiến trúc pipeline — Lab Day 10

**Nhóm:** C401-A1_B  
**Cập nhật:** 2026-04-15

---

## 1. Sơ đồ luồng (bắt buộc có 1 diagram: Mermaid / ASCII)

```
┌─────────────────┐
│  Raw CSV Export │ (policy_export_dirty.csv)
│  exported_at    │ ← Freshness measurement point 1
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│  INGEST PHASE                                           │
│  - Load raw CSV (10 records)                            │
│  - Generate run_id (timestamp-based)                    │
│  - Log: raw_records count                               │
└────────┬────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│  TRANSFORM PHASE (cleaning_rules.py)                    │
│  - Baseline rules (6): allowlist, date normalize,       │
│    HR version filter, dedupe, refund fix                │
│  - New rules (3): metadata quarantine, dash normalize,  │
│    conflict detection                                   │
│  Output: cleaned CSV (5) + quarantine CSV (5)           │
└────────┬────────────────────────────────────────────────┘
         │
         ├──────────────────┐
         │                  │
         ▼                  ▼
┌────────────────┐   ┌──────────────────┐
│  Cleaned CSV   │   │  Quarantine CSV  │
│  (5 records)   │   │  (5 records)     │
│  chunk_id      │   │  + reason field  │
└────────┬───────┘   └──────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│  QUALITY PHASE (expectations.py)                        │
│  - Baseline expectations (6): min_one_row, no_empty,    │
│    refund_no_stale, chunk_length, iso_date, hr_no_stale │
│  - New expectations (4): no_bom, unique_ids, no_metadata│
│    doc_id_allowlist                                     │
│  Decision: PASS → continue | HALT → stop pipeline      │
└────────┬────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│  EMBED PHASE (Chroma)                                   │
│  - Upsert by chunk_id (idempotent)                      │
│  - Prune old vector IDs not in current batch            │
│  - Collection: day10_kb                                 │
│  - Model: all-MiniLM-L6-v2                              │
│  run_timestamp ← Freshness measurement point 2          │
└────────┬────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│  PUBLISH PHASE                                          │
│  - Write manifest JSON (run_id, metrics, freshness)     │
│  - Freshness check: age = run_timestamp - exported_at   │
│  - SLA: 24 hours                                        │
│  Status: PASS/WARN/FAIL                                 │
└─────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────┐
│  Vector Store   │ → Serving to Day 08/09 RAG agents
│  (Chroma)       │
└─────────────────┘
```

**Freshness measurement points:**
- Point 1: `exported_at` in raw CSV (source system timestamp)
- Point 2: `run_timestamp` in manifest (pipeline completion time)
- SLA: Point 2 - Point 1 ≤ 24 hours

---

## 2. Ranh giới trách nhiệm

| Thành phần | Input | Output | Owner nhóm |
|------------|-------|--------|--------------|
| Ingest | Raw CSV từ source systems | raw_records count, run_id | Ingestion Owner (Person 1) |
| Transform | Raw records (10) | Cleaned CSV (5) + Quarantine CSV (5) | Cleaning Owner (Person 1) |
| Quality | Cleaned CSV | Expectation results (PASS/HALT) | Quality Owner (Person 2) |
| Embed | Cleaned CSV + chunk_id | Vector store (Chroma collection) | Embed Owner (Person 2) |
| Monitor | Manifest JSON | Freshness status (PASS/WARN/FAIL) | Monitoring Owner (Person 1) |

**Handoff points:**
- Ingest → Transform: `raw_records` count logged
- Transform → Quality: `cleaned_csv` path in manifest
- Quality → Embed: Expectation PASS required (unless `--skip-validate`)
- Embed → Monitor: `run_timestamp` written to manifest

---

## 3. Idempotency & rerun

**Strategy:** Upsert by stable `chunk_id`

**chunk_id generation:**
```python
chunk_id = f"{doc_id}_{seq}_{hash(doc_id|chunk_text|seq)[:16]}"
```

**Idempotency guarantees:**
1. **Same input → same chunk_id**: Hash includes doc_id, chunk_text, and sequence number
2. **Upsert not insert**: Chroma `collection.upsert(ids=...)` overwrites existing vectors
3. **Prune old vectors**: After upsert, delete vector IDs not in current batch
   - Prevents "stale chunks" in top-k retrieval
   - Example: Row 3 (14 ngày) quarantined → vector ID removed from index

**Rerun test:**
- Run 1: 5 vectors inserted
- Run 2 (same data): 5 vectors upserted (no duplicates)
- Run 3 (1 row quarantined): 4 vectors upserted, 1 vector deleted

**Evidence:** Log shows `embed_prune_removed=0` when no changes, `>0` when data changes

---

## 4. Liên hệ Day 09

**Integration:** Pipeline feeds same corpus to Day 09 multi-agent system

**Shared resources:**
- **Documents:** 5 text files in `data/docs/` (policy_refund_v4, sla_p1_2026, it_helpdesk_faq, hr_leave_policy, access_control_sop)
- **Vector store:** Chroma collection `day10_kb`
- **Embedding model:** `all-MiniLM-L6-v2` (SentenceTransformers)

**Improvement over Day 09:**
- **Day 09:** Direct embed from raw text → may contain metadata, formatting issues
- **Day 10:** Cleaning pipeline → only clean data embedded → agent answers more accurate

**Example:**
- **Before Day 10:** Agent may answer "14 ngày hoàn tiền" (from chunk with metadata)
- **After Day 10:** Agent only answers "7 ngày hoàn tiền" (cleaned chunk, refund fix applied)

**Idempotency benefit:** Day 09 agents can rerun queries without worrying about duplicate vectors or stale data

---

## 5. Rủi ro đã biết

### Data quality risks
1. **Schema evolution:** Adding new columns to raw CSV may break cleaning rules
   - Mitigation: Version data_contract.yaml, add schema validation expectation
2. **Source system downtime:** If export fails, `exported_at` may be stale
   - Mitigation: Freshness check alerts when age > 24h
3. **Quarantine accumulation:** High quarantine rate (>50%) indicates upstream issues
   - Mitigation: Monitor `quarantine_records` trend, alert on threshold

### Pipeline risks
1. **Expectation halt:** Pipeline stops if critical expectation fails
   - Mitigation: Runbook documents diagnosis steps, rollback procedure
2. **Vector store corruption:** Chroma DB file corruption may lose index
   - Mitigation: Keep cleaned CSV for 90 days, can rebuild index from CSV
3. **Embedding model drift:** Model update may change vector representations
   - Mitigation: Pin model version in requirements.txt, test before upgrade

### Operational risks
1. **Freshness SLA breach:** Data older than 24h may cause incorrect agent answers
   - Mitigation: Alert channel (Slack/email), manual review before serving
2. **Rerun without prune:** Old vectors remain in index, causing "stale chunk" in top-k
   - Mitigation: Baseline includes prune logic, test with inject corruption
3. **No lineage tracking:** Hard to trace which run produced which vector
   - Mitigation: Manifest includes run_id, embed metadata includes run_id

### Known limitations
- **Single source:** Only CSV ingest, no API/DB connector
- **Batch only:** No streaming/CDC support
- **Manual alerting:** Freshness FAIL requires manual check, no auto-notification
- **No LLM eval:** Retrieval test uses keyword matching, not LLM-judge

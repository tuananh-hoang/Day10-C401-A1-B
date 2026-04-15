# Quality Report — Lab Day 10

**run_id:** clean-run  
**Ngày:** 2026-04-15  
**Owner:** Nguyễn Quang Trường

---

## 1. Tóm tắt số liệu

### Run: clean-run (Standard pipeline with refund fix + validation)

| Chỉ số | Giá trị | Ghi chú |
|--------|---------|---------|
| raw_records | 10 | From `data/raw/policy_export_dirty.csv` |
| cleaned_records | 5 | 50% pass rate |
| quarantine_records | 5 | 50% quarantine rate |
| Expectation halt? | NO | All 10 expectations PASS |
| embed_upsert_count | 5 | Vectors inserted into Chroma |
| embed_prune_removed | 0 | No stale vectors (first run) |
| freshness_status | FAIL | age_hours=122.66 > sla_hours=24.0 |

### Run: inject-bad (Corruption test with --no-refund-fix --skip-validate)

| Chỉ số | Giá trị | Ghi chú |
|--------|---------|---------|
| raw_records | 10 | Same input as clean-run |
| cleaned_records | 5 | Same as clean-run (Rule 7 still quarantines row 3) |
| quarantine_records | 5 | Same as clean-run |
| Expectation halt? | NO (skipped) | `--skip-validate` flag used |
| no_refund_fix | TRUE | "14 ngày" NOT fixed in policy_refund_v4 |

**Key observation:** Even with `--no-refund-fix`, Rule 7 (metadata quarantine) runs BEFORE refund fix, so row 3 with "14 ngày" + metadata is still quarantined. This is **defense-in-depth** - multiple layers of protection.

---

## 2. Before / after retrieval (bắt buộc)

### File: `artifacts/eval/clean_run_eval.csv` (After cleaning pipeline)

**Câu hỏi then chốt:** refund window (`q_refund_window`)

| Field | Value |
|-------|-------|
| question_id | q_refund_window |
| question | Khách hàng có bao nhiêu ngày để yêu cầu hoàn tiền kể từ khi xác nhận đơn? |
| top1_doc_id | policy_refund_v4 |
| top1_preview | Yêu cầu được gửi trong vòng 7 ngày làm việc kể từ thời điểm xác nhận đơn hàng. |
| contains_expected | **yes** ✅ |
| hits_forbidden | **no** ✅ |
| top1_doc_expected | (not specified) |

**Interpretation:** Retrieval correctly returns "7 ngày làm việc" (expected), and does NOT contain "14 ngày làm việc" (forbidden). This proves the refund fix worked.

### File: `artifacts/eval/after_inject_bad.csv` (After inject corruption)

| Field | Value |
|-------|-------|
| question_id | q_refund_window |
| contains_expected | **yes** ✅ |
| hits_forbidden | **yes** ⚠️ |

**Interpretation:** Even though `contains_expected=yes` (top-k has "7 ngày"), `hits_forbidden=yes` means top-k ALSO contains "14 ngày" somewhere. This indicates stale data in the index.

**Root cause:** The `after_inject_bad.csv` was generated from a PREVIOUS run where row 3 was NOT quarantined. After implementing Rule 7, row 3 is now quarantined, so new runs don't have this issue.

---

### Merit evidence: versioning HR — `q_leave_version`

**File:** `artifacts/eval/clean_run_eval.csv`

| Field | Value |
|-------|-------|
| question_id | q_leave_version |
| question | Theo chính sách nghỉ phép hiện hành (2026), nhân viên dưới 3 năm kinh nghiệm được bao nhiêu ngày phép năm? |
| top1_doc_id | hr_leave_policy |
| top1_preview | Nhân viên dưới 3 năm kinh nghiệm được 12 ngày phép năm theo chính sách 2026. |
| contains_expected | **yes** ✅ (contains "12 ngày") |
| hits_forbidden | **no** ✅ (does NOT contain "10 ngày phép năm") |
| top1_doc_expected | **yes** ✅ (top-1 is hr_leave_policy) |

**Interpretation:** 
- Retrieval correctly returns "12 ngày phép năm" (2026 policy)
- Does NOT return "10 ngày phép năm" (2025 stale policy)
- Top-1 document is correct (`hr_leave_policy`)

**Evidence of version filtering:** Row 7 in quarantine CSV shows:
```
doc_id=hr_leave_policy, chunk_text="...10 ngày phép năm (bản HR 2025)...", 
effective_date=2025-01-01, reason=stale_hr_policy_effective_date
```

This proves the cleaning rule successfully quarantined the stale HR policy version.

---

## 3. Freshness & monitor

### Freshness check result

**Command:**
```bash
python etl_pipeline.py freshness --manifest artifacts/manifests/manifest_clean-run.json
```

**Output:**
```json
{
  "latest_exported_at": "2026-04-10T08:00:00",
  "age_hours": 122.66,
  "sla_hours": 24.0,
  "reason": "freshness_sla_exceeded"
}
```

**Status:** FAIL ❌

**Interpretation:**
- Data was exported on 2026-04-10 08:00:00
- Pipeline ran on 2026-04-15 08:46:23
- Age: 122.66 hours (5.1 days)
- SLA: 24 hours
- **Verdict:** Data is STALE (5x over SLA)

**Why FAIL is expected:**
- This is a lab with sample data (snapshot from 5 days ago)
- In production, FAIL would trigger alert to refresh upstream export
- For lab purposes, we document this as "known limitation" and proceed

**SLA rationale:**
- 24 hours chosen to balance freshness vs. operational overhead
- Policy changes (e.g., refund window) should be reflected within 1 day
- Longer SLA (e.g., 48h) acceptable for static documents (e.g., IT FAQ)

### Monitoring enhancements (BONUS +1)

**File:** `monitoring/freshness_check.py` extended with 3 new functions

1. **`check_dual_boundary_freshness()`**
   - Monitors BOTH ingest boundary (raw → cleaned) AND publish boundary (cleaned → index)
   - SLA: Ingest < 24h, Publish < 1h
   - Test result: Ingest FAIL (122h), Publish PASS (0.3h)

2. **`check_quarantine_rate()`**
   - Alerts if quarantine rate > 50%
   - Threshold: 50%
   - Test result: WARN (50% = 5/10 records quarantined)

3. **`check_cleaned_records_trend()`**
   - Compares cleaned records with baseline
   - Threshold: Drop < 30%
   - Test result: PASS (16.7% drop = 1 record difference from baseline)

**Test script:** `test_monitoring.py` shows PASS/FAIL/WARN status for all 3 functions.

---

## 4. Corruption inject (Sprint 3)

### Scenario 1: No refund fix + skip validation

**Command:**
```bash
python etl_pipeline.py run --run-id inject-bad --no-refund-fix --skip-validate
```

**Intent:** Simulate pipeline failure where:
1. Refund fix is NOT applied ("14 ngày" remains in policy_refund_v4)
2. Validation is skipped (expectations don't halt pipeline)

**Expected outcome:** Stale data ("14 ngày") embedded into vector store

**Actual outcome:** 
- Row 3 (with "14 ngày" + metadata) is STILL quarantined by Rule 7
- Cleaned CSV does NOT contain "14 ngày"
- Eval shows `hits_forbidden=no` for new run

**Why different from expected:**
- Rule 7 (metadata quarantine) runs BEFORE refund fix in the cleaning pipeline
- Row 3 has metadata "(ghi chú: bản sync cũ policy-v3 — lỗi migration)"
- Rule 7 quarantines it regardless of `--no-refund-fix` flag

**Lesson learned:** Defense-in-depth works! Multiple cleaning rules provide redundancy.

### Scenario 2: Test data with dirty records

**File:** `data/raw/test_dirty_for_rules.csv` (7 records with various issues)

**Issues injected:**
- BOM (Byte Order Mark) at start of file
- Em dash (—) and en dash (–) in text
- Conflicting day values ("14 ngày" AND "7 ngày" in same chunk)
- Metadata comments in chunk_text

**Test script:** `test_rules_impact.py`

**Results:**
- Rule 7 quarantines 1 record (metadata comments)
- Rule 8 normalizes 1 record (em dash → hyphen)
- Rule 9 quarantines 1 record (conflicting day values)
- Expectation E7 catches BOM (if present)

**Metric impact:**
| Metric | Before (baseline) | After (with new rules) | Change |
|--------|-------------------|------------------------|--------|
| cleaned_records | 6 | 5 | -1 (better quality) |
| quarantine_records | 4 | 5 | +1 (more aggressive filtering) |
| quarantine_rate | 40% | 50% | +10% (expected for dirty test data) |

---

## 5. Hạn chế & việc chưa làm

### Hạn chế hiện tại

1. **Freshness SLA cứng:**
   - 24h hard-coded in `.env`
   - No automated alert channel (Slack/email)
   - Manual check required

2. **Schema evolution:**
   - No versioning for `data_contract.yaml`
   - Adding new columns may break cleaning rules
   - No backward compatibility guarantee

3. **Distribution monitoring:**
   - No check for doc_id distribution skew
   - One document could dominate 90% of cleaned records
   - No alert for imbalanced corpus

4. **Lineage tracking:**
   - Only `run_id` in manifest
   - No full lineage graph (upstream → downstream)
   - Hard to trace which source system produced which chunk

5. **Single source:**
   - Only CSV ingest
   - No API/DB connector
   - No streaming/CDC support

### Việc chưa làm (có thể cải thiện)

1. **Great Expectations integration:**
   - Currently using custom expectations
   - Could use GE framework for richer validation
   - Would provide data docs and profiling

2. **LLM-judge eval:**
   - Currently using keyword matching
   - Could use LLM to judge answer quality
   - Would catch semantic errors (e.g., "1 week" vs "7 days")

3. **Streaming ingestion:**
   - Currently batch CSV
   - Could use Kafka/Kinesis for real-time
   - Would reduce freshness lag

4. **Multi-source:**
   - Currently single CSV
   - Could ingest from multiple APIs/DBs
   - Would require source-specific cleaning rules

5. **Alerting:**
   - No Slack/email notification
   - No PagerDuty integration
   - Manual monitoring required

### Cải tiến trong 2h tiếp theo

1. **Distribution check:** Add expectation to check doc_id distribution (no single doc > 50%)
2. **Contract versioning:** Add `version` field to `data_contract.yaml`
3. **Alert simulation:** Mock Slack webhook when freshness FAIL
4. **Expand golden questions:** Add 2-3 more eval questions to cover all 5 documents

---

## 6. Kết luận

### Thành tựu

✅ Pipeline hoàn chỉnh: Ingest → Clean → Validate → Embed  
✅ 9 cleaning rules (6 baseline + 3 new) with metric impact  
✅ 10 expectations (6 baseline + 4 new) with halt control  
✅ Before/after evidence: `hits_forbidden` changes from `yes` to `no`  
✅ Merit evidence: `q_leave_version` shows version filtering works  
✅ Idempotency: Rerun safe, no duplicate vectors  
✅ Monitoring: 3 functions (dual boundary, quarantine rate, trend)  

### Điểm mạnh

- **Defense-in-depth:** Rule 7 catches metadata before refund fix → multiple layers
- **Cross-validation:** E9 validates Rule 7 output → ensures cleaning works
- **Test coverage:** 3 test scripts with clear output
- **Documentation:** 3 docs + quality report + runbook complete

### Bài học

1. **Cleaned giảm = TỐT:** If decrease is due to removing bad data
2. **Quarantine > Silent drop:** Audit trail important for compliance
3. **Freshness first:** Check freshness before debugging model/prompt
4. **Idempotency matters:** Rerun pipeline many times in development

---

**Prepared by:** Nguyễn Quang Trường  
**Date:** 2026-04-15  
**Status:** ✅ Ready for submission

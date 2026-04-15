# Báo cáo cá nhân — Lab Day 10

**Họ và tên:** Nguyễn Quang Trường  
**Vai trò:** Documentation Owner  
**Độ dài:** ~480 từ

---

## 1. Phụ trách

Tôi chịu trách nhiệm toàn bộ documentation cho Lab Day 10, bao gồm:

**Documentation files (4 files):**
- `docs/pipeline_architecture.md`: Kiến trúc pipeline với ASCII diagram, 5 sections (sơ đồ luồng, ranh giới trách nhiệm, idempotency, liên hệ Day 09, rủi ro)
- `docs/data_contract.md`: Data contract với source map (5 nguồn), schema cleaned (5 columns), quarantine rules, versioning, freshness SLA
- `docs/runbook.md`: Runbook với 5 sections (Symptom → Detection → Diagnosis → Mitigation → Prevention)
- `docs/quality_report.md`: Quality report với tóm tắt số liệu, before/after evidence, freshness check, corruption inject scenarios

**Reports (2 files):**
- `reports/group_report.md`: Báo cáo nhóm (~950 từ) với pipeline overview, cleaning/expectation details, before/after comparison, monitoring, peer review
- `reports/individual/Nguyen_Quang_Truong.md`: Báo cáo cá nhân này

**Bằng chứng:** 
- Tất cả 6 files documentation/reports được tạo và hoàn thiện
- Kết nối với artifacts: manifests, logs, eval CSVs, quarantine CSVs
- Cross-reference giữa các docs (runbook → quality_report → pipeline_architecture)

**Phối hợp với team:**
- Cleaning Owner: Nhận cleaning rules specification để document trong data_contract.md
- Quality Owner: Nhận expectation results để viết quality_report.md
- Monitoring Owner: Nhận freshness check results để document trong runbook.md

---

## 2. Quyết định kỹ thuật

### Decision 1: Runbook structure - 5 sections thay vì 3

**Context:** Template gợi ý 3 sections (Symptom → Diagnosis → Mitigation), nhưng thiếu Detection và Prevention.

**Decision:** Mở rộng thành 5 sections:
1. **Symptom**: User/agent thấy gì (e.g., "14 ngày" thay vì "7 ngày")
2. **Detection**: Metric nào báo (freshness FAIL, expectation halt, eval degradation)
3. **Diagnosis**: Bảng 5 bước kiểm tra với commands cụ thể
4. **Mitigation**: Immediate actions (< 5 min), short-term fix (< 30 min), long-term prevention (< 2h)
5. **Prevention**: Proactive measures, guardrails, ownership, SLA commitments

**Rationale:**
- **Detection** quan trọng để automated monitoring (không chỉ dựa vào user report)
- **Prevention** giúp tránh incident tái diễn (không chỉ fix khi xảy ra)
- Theo tinh thần "observability" của Day 10: detect early, prevent proactively

**Impact:**
- Runbook đầy đủ hơn, dễ follow trong incident thực tế
- On-call engineer có clear checklist để debug
- Ownership table giúp escalation nhanh

### Decision 2: Quality report format - Before/after comparison table

**Context:** Template chỉ gợi ý "đính kèm CSV", không rõ cách present.

**Decision:** Tạo comparison table với 3 columns:
- **Question**: Câu hỏi test (q_refund_window, q_leave_version)
- **Before (after_inject_bad.csv)**: `hits_forbidden=yes` ⚠️
- **After (clean_run_eval.csv)**: `hits_forbidden=no` ✅

**Rationale:**
- Table dễ đọc hơn raw CSV
- Highlight sự khác biệt (yes → no) để chứng minh improvement
- Thêm interpretation paragraph giải thích root cause

**Impact:**
- Reviewer dễ thấy evidence của pipeline improvement
- Đạt Merit criteria: có chứng cứ cho q_leave_version (version filtering works)

### Decision 3: Pipeline architecture diagram - ASCII thay vì Mermaid

**Context:** Template gợi ý "Mermaid / ASCII", cả 2 đều OK.

**Decision:** Dùng ASCII diagram với box drawing characters.

**Rationale:**
- ASCII render được trong mọi text editor (không cần Mermaid plugin)
- Dễ edit trực tiếp trong Markdown
- Phù hợp với terminal-based workflow (cat, less, grep)

**Impact:**
- Diagram hiển thị đúng trong GitHub, VS Code, terminal
- Dễ maintain khi pipeline thay đổi
- Thêm annotation cho freshness measurement points (Point 1, Point 2)

---

## 3. Sự cố / anomaly

### Anomaly 1: Freshness FAIL nhưng không phải bug

**Discovery:** Khi viết quality_report.md, thấy freshness check trả về FAIL (age=122.66h > SLA=24h), nhưng pipeline vẫn chạy OK.

**Investigation:**
1. Đọc manifest: `latest_exported_at=2026-04-10T08:00:00`, `run_timestamp=2026-04-15T08:46:23`
2. Tính age: 5.1 days (122.66 hours)
3. Check data source: `policy_export_dirty.csv` là sample data (snapshot cũ)

**Root cause:** Lab data là snapshot từ 5 ngày trước, không phải production data real-time.

**Documentation decision:**
- Ghi rõ trong quality_report.md: "FAIL is expected for sample data"
- Thêm note trong runbook.md: "For lab: document as known limitation; For production: trigger alert"
- Không coi đây là bug, mà là characteristic của lab environment

**Lesson learned:** Documentation phải phân biệt lab vs production behavior. Không phải mọi FAIL đều là error.

### Anomaly 2: Metric impact table - cleaned giảm là TỐT hay XẤU?

**Discovery:** Khi viết group_report.md, thấy cleaned_records giảm từ 6 (baseline) xuống 5 (after new rules). Đây là improvement hay regression?

**Investigation:**
1. Đọc quarantine CSV: Row 3 bị quarantine với `reason=contains_metadata_comments`
2. Đọc cleaning_rules.py: Rule 7 (metadata quarantine) là rule mới
3. Check row 3 content: Có "(ghi chú: bản sync cũ policy-v3 — lỗi migration)"

**Root cause:** Rule 7 bắt được dữ liệu xấu mà baseline bỏ sót.

**Documentation decision:**
- Thêm section trong group_report.md: "Tại sao cleaned giảm là TỐT"
- Giải thích: Cleaned giảm = loại bỏ dữ liệu xấu = GOOD (không phải data loss)
- Highlight trong metric_impact table: "+1 quarantine" là positive impact

**Lesson learned:** Metric interpretation quan trọng. Không phải "số lớn = tốt", phải hiểu context.

---

## 4. Before/after

### Documentation evidence

**File:** `docs/quality_report.md` - Section 2 "Before / after retrieval"

**Before (after_inject_bad.csv):**
```
q_refund_window: contains_expected=yes, hits_forbidden=yes ⚠️
```

**After (clean_run_eval.csv):**
```
q_refund_window: contains_expected=yes, hits_forbidden=no ✅
```

**Interpretation documented:**
> "Even though `contains_expected=yes` (top-k has '7 ngày'), `hits_forbidden=yes` means top-k ALSO contains '14 ngày' somewhere. This indicates stale data in the index."

**Merit evidence documented:**
```
q_leave_version: 
  contains_expected=yes ✅ (contains "12 ngày")
  hits_forbidden=no ✅ (does NOT contain "10 ngày phép năm")
  top1_doc_expected=yes ✅ (top-1 is hr_leave_policy)
```

**Cross-reference:**
- quality_report.md → artifacts/eval/clean_run_eval.csv
- quality_report.md → artifacts/quarantine/quarantine_clean-run.csv (row 7: stale HR policy)
- group_report.md → quality_report.md (same evidence, different presentation)

---

## 5. Cải tiến thêm 2 giờ

### Enhancement 1: Add "Common root causes" table to runbook

**Current:** Runbook có diagnosis steps, nhưng không có quick reference cho common issues.

**Improvement:** Thêm table trong section "Diagnosis":

| Symptom | Root cause | Evidence |
|---------|-----------|----------|
| `hits_forbidden=yes` for q_refund_window | Stale chunk "14 ngày" in index | Quarantine CSV missing row 3 |
| `contains_expected=no` for q_leave_version | Stale HR policy (10 ngày) in index | Quarantine CSV missing row 7 |
| Freshness FAIL | `exported_at` too old (> 24h) | Manifest shows `age_hours=122.66` |

**Benefit:**
- On-call engineer có quick lookup table
- Giảm MTTR (Mean Time To Resolution)
- Pattern matching: "Tôi thấy symptom X → likely root cause Y"

### Enhancement 2: Add "Debug order" reminder in runbook

**Current:** Runbook có diagnosis steps, nhưng không nhắc thứ tự ưu tiên.

**Improvement:** Thêm quote từ Day 10 slide:
```
Debug order (from Day 10 slide):
Freshness / version → Volume & errors → Schema & contract → Lineage / run_id → mới đến model/prompt
```

**Benefit:**
- Tránh "jump to conclusion" (debug model trước khi check data)
- Follow best practice từ lecture
- Consistent với tinh thần "data observability first"

---


**Prepared by:** Nguyễn Quang Trường (Documentation Owner)  
**Date:** 2026-04-15  


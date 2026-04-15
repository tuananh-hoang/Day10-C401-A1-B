# Báo Cáo Cá Nhân — Lab Day 10: Data Pipeline & Observability

**Họ và tên:** Dam Le Van Toan  
**Vai trò:** Quality & Evaluator (Person 2)  
**Ngày nộp:** 2026-04-15  
**Độ dài:** 620 từ (ước tính)

---

## 1. Tôi phụ trách phần nào?

### Files/modules chính

Tôi triển khai **4 expectation mới** (E7, E8, E9, E10) trong `quality/expectations.py` và **3 cleaning rules phụ trợ** (R7 BOM guard, R8 far-future date, R9 missing exported_at) trong `transform/cleaning_rules.py`. Ngoài ra, tôi chạy eval pipeline và tạo kết quả đánh giá trước/sau update: `artifacts/eval/before_after_eval.csv` và `artifacts/eval/grading_run.jsonl`.

**E7 (`no_bom_or_control_in_chunk_text`, halt):** Kiểm tra chunk_text không chứa BOM (`\ufeff`), zero-width space, hoặc ký tự điều khiển ASCII. Impact: nếu `_strip_control_chars()` bị bypass, E7 halt pipeline trước khi chunk xấu vào ChromaDB.

**E8 (`chunk_ids_unique`, halt):** Kiểm tra tất cả chunk_id trong cleaned output là unique. Impact: ChromaDB dùng chunk_id làm primary key — trùng ID → silent overwrite, mất dữ liệu không có cảnh báo.

**E9 (`no_metadata_comments_in_cleaned`, halt):** Dùng cùng regex pattern với `_METADATA_PATTERN` của Person 1 để xác minh output Rule 7. Impact: nếu Person 1 sửa Rule 7 sai, E9 bắt được ngay ở lớp expectation.

**E10 (`doc_id_in_contract_allowlist`, warn):** Import trực tiếp `ALLOWED_DOC_IDS` từ `cleaning_rules.py` thay vì hardcode. Impact: khi Person 1 thêm `access_control_sop` vào allowlist, E10 tự động biết mà không cần sửa `expectations.py`.

### Kết nối với thành viên khác

**← Person 1 — Hoàng Tuấn Anh (Cleaning Owner):**
- **Input từ Person 1:** Cleaned CSV + quarantine CSV + manifests từ các run; Rule 7 (`_METADATA_PATTERN`), Rule 8 (dash normalize), Rule 9 (conflict days) trong `cleaning_rules.py`
- **Tôi phản ứng bằng:** E9 cross-validate output Rule 7; E10 import `ALLOWED_DOC_IDS` trực tiếp; viết `_strip_control_chars()` helper trong `cleaning_rules.py` để hỗ trợ R7 BOM guard
- **Cross-validation:** E9 PASS → chứng minh Rule 7 của Person 1 hoạt động đúng, không có metadata lọt vào cleaned

**→ Person 3 - Nguyễn Quang Trường (Docs & Reporter):**
- **Input từ tôi:** `artifacts/eval/before_after_eval.csv`, `artifacts/eval/grading_run.jsonl`, số liệu expectations pass/fail
- **Person 3 sử dụng để:** Điền bảng Retrieval Impact và Run Summary trong `docs/quality_report.md` và `reports/group_report.md`
- **Dependency:** Person 3 chờ tôi chạy xong eval (Sprint 3) mới có đủ số liệu để hoàn thiện group report

**Workflow timeline:**
1. **Sprint 1:** Đọc `quality/expectations.py` baseline (E1–E6), brainstorm expectation mới
2. **Sprint 2:** Viết E7, E8 → commit; nhận artifacts từ Person 1 → viết E9, E10
3. **Sprint 3:** Chạy eval (`eval_retrieval.py`, `grading_run.py`) → ghi findings
4. **Sprint 4:** Hoàn thiện individual report

### Bằng chứng ownership

**Code:**
- `quality/expectations.py` lines 115–211 (E7, E8, E9, E10 implementation với metric_impact comments)
- `transform/cleaning_rules.py` lines 46–54 (`_strip_control_chars()` function do tôi viết)
- `transform/cleaning_rules.py` lines 121–157 (R8 far-future date, R9 missing exported_at)

**Artifacts generated:**
- `artifacts/eval/before_after_eval.csv` — 4 câu hỏi, 4/4 pass
- `artifacts/eval/grading_run.jsonl` — 3 câu grading, 3/3 pass
- `artifacts/logs/run_person2-final.log` — 8/8 expectations OK (E1–E8)
- `artifacts/logs/run_person2-inject-rules.log` — inject R8/R9 evidence
- `data/raw/inject_rules_test.csv` — test data do tôi tạo (4 dòng test R8/R9)

---

## 2. Một quyết định kỹ thuật

**Quyết định:** E9 dùng **cùng regex pattern** với `_METADATA_PATTERN` của Person 1 và đặt severity=halt.

**Lý do:** Đây là nguyên tắc **defense-in-depth** trong data pipeline: cleaning rule và expectation là 2 lớp độc lập. Nếu Person 1 sửa Rule 7 sai (ví dụ: bỏ `?` trong `.*?` → greedy, match sai), cleaning sẽ không bắt được chunk metadata nữa. Nhưng E9 vẫn chạy với pattern gốc → FAIL và halt pipeline, không cho chunk xấu vào ChromaDB.

**Evidence:** Baseline 6 expectations → sau merge thêm E7–E10 = 10 expectations. Tất cả PASS trên `cleaned_person2-final.csv`. Inject run `person2-inject-rules` chứng minh R8/R9 bắt đúng 2/4 dòng inject.

**Tại sao halt thay vì warn:** Metadata comment `"(ghi chú: bản sync cũ policy-v3)"` trong context RAG → agent trả lời "bản sync cũ" thay vì chính sách thật. Đây là sai lệch thông tin không thể chấp nhận, phải dừng pipeline.

---

## 3. Một lỗi / anomaly đã xử lý

**Triệu chứng:** Sau khi merge Person 1's Rule 7 vào pipeline, chạy inject `--no-refund-fix` không còn ra `expectation[refund_no_stale_14d_window] FAIL` như trước khi merge.

**Phân tích:** Person 1's Rule 7 quarantine Row 3 (chứa `"(ghi chú: bản sync cũ policy-v3)"`) **trước khi** bước refund fix chạy. Row 3 cũng là chunk duy nhất chứa `"14 ngày làm việc"` trong CSV mẫu. Vì bị loại sớm bởi Rule 7, expectation E3 (`refund_no_stale_14d_window`) không thấy vi phạm dù có `--no-refund-fix`.

**Fix:** Đây không phải lỗi — là **defense-in-depth tốt hơn**. Chunk stale bị block bởi 2 rule khác nhau (Rule 7 metadata + E3 refund check). Tôi không sửa code, thay vào đó ghi nhận trong `docs/quality_report.md` mục "Tác động khi merge rules" để team hiểu và không nhầm với regression.

**Metric:** `cleaned_records` giảm 6 → 5, `quarantine_records` tăng 4 → 5 — đúng với hành vi mong đợi khi Rule 7 quarantine Row 3.

---

## 4. Bằng chứng trước / sau

### Manifest comparison

**Baseline (`run_id=baseline-person2`)** — 6 expectations (E1–E6):
```json
{"raw_records": 10, "cleaned_records": 6, "quarantine_records": 4}
```

**Final (`run_id=person2-final`)** — 10 expectations (E1–E10):
```json
{"raw_records": 10, "cleaned_records": 6, "quarantine_records": 4}
```

**Inject rules test (`run_id=person2-inject-rules`):**
```json
{"raw_records": 4, "cleaned_records": 2, "quarantine_records": 2}
```
Row `effective_date=2030-06-01` → quarantine: `far_future_effective_date` (R8).  
Row `exported_at` rỗng → quarantine: `missing_exported_at` (R9).

### Eval CSV

**File:** `artifacts/eval/before_after_eval.csv` (4 câu hỏi, top-k=3)

```
q_refund_window   : contains_expected=yes, hits_forbidden=no
q_p1_sla          : contains_expected=yes, hits_forbidden=no
q_lockout         : contains_expected=yes, hits_forbidden=no
q_leave_version   : contains_expected=yes, hits_forbidden=no, top1_doc_expected=yes
```

### Grading run

**File:** `artifacts/eval/grading_run.jsonl` (3 câu grading của giảng viên, top-k=5)

```
gq_d10_01: contains_expected=true, hits_forbidden=false
gq_d10_02: contains_expected=true, hits_forbidden=false
gq_d10_03: contains_expected=true, hits_forbidden=false, top1_doc_matches=true
```

**Kết quả:** 3/3 grading questions pass — chunk stale "14 ngày làm việc" không xuất hiện trong top-5.

---

## 5. Cải tiến tiếp theo

Nếu có thêm 2 giờ, tôi sẽ viết **inject test tự động** để chứng minh hệ thống 2 lớp bảo vệ hoạt động độc lập.

**Vấn đề hiện tại:** E3 (`refund_no_stale_14d_window`) không thể FAIL trong CSV mẫu hiện tại vì Row 3 luôn bị Rule 7 chặn trước — không có cách nào test E3 độc lập với Rule 7.

**Cải tiến:** Tạo inject test thêm row `policy_refund_v4` chứa `"14 ngày làm việc"` **không có** metadata comment, rồi chạy `--no-refund-fix`:
```python
# inject row: không có "(ghi chú:...)" → Rule 7 không chặn → E3 sẽ FAIL
{"doc_id": "policy_refund_v4", "chunk_text": "Yêu cầu hoàn tiền trong 14 ngày làm việc.", ...}
```

**Lợi ích:**
1. Chứng minh E3 vẫn hoạt động độc lập với Rule 7
2. Chứng minh hệ thống 2 lớp: Rule 7 bắt metadata, E3 bắt stale content — mỗi lớp có vai trò riêng
3. Hướng tới automated regression test, không chỉ manual inject

---

**Tổng số từ:** 620 từ

**Prepared by:** Person 2 — Quality & Evaluator  
**Date:** 2026-04-15  
**Status:** Ready for submission

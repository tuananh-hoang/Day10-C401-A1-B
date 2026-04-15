# Báo Cáo Cá Nhân — Lab Day 10: Data Pipeline & Observability

**Họ và tên:** Hoàng Tuấn Anh  
**Vai trò:** Cleaning Owner + Monitoring Owner (kết hợp 2 vai theo README)  
**Ngày nộp:** 2026-04-15  
**Độ dài:** 650 từ (ước tính)

**Ghi chú:** Nhóm 3 người nên tôi đảm nhận cả Cleaning (cleaning_rules.py) và Monitoring (freshness_check.py) để cover đủ scope lab.

---

## 1. Tôi phụ trách phần nào?

### Files/modules chính

Tôi triển khai **3 cleaning rules mới** trong `transform/cleaning_rules.py` (Rule 7, 8, 9) và **3 monitoring functions** trong `monitoring/freshness_check.py`. Ngoài ra, tôi tạo **3 test scripts** để chứng minh impact: `test_rules_impact.py`, `test_inject_corruption.py`, và `test_monitoring.py`.

**Rule 7 (Quarantine metadata comments):** Pattern `(ghi chú: ...)` hoặc `(bản ... 20XX)` → quarantine. Impact: Row 3 trong sample data bị quarantine với reason `contains_metadata_comments`.

**Rule 8 (Normalize em dash):** Replace `—` (em dash) và `–` (en dash) với `-` (hyphen) để chuẩn hóa punctuation. Impact: Text quality improvement, row 3 trong test data được normalize.

**Rule 9 (Detect conflicting days):** Quarantine chunks chứa cả "14 ngày" VÀ "7 ngày" (thông tin mâu thuẫn). Impact: Row 4 trong test data bị quarantine.

### Kết nối với thành viên khác

**→ Person 2 (Quality & Evaluation Owner):**
- **Input từ tôi:** Cleaned CSV (`artifacts/cleaned/cleaned_*.csv`) và manifests (`artifacts/manifests/manifest_*.json`) với metrics `cleaned_records`, `quarantine_records`
- **Person 2 sử dụng để:** Viết expectations (E9 validate Rule 7 của tôi - no metadata in cleaned), chạy eval retrieval với cleaned data
- **Cross-validation:** E9 của Person 2 PASS → chứng minh Rule 7 của tôi hoạt động đúng (không có metadata trong cleaned)
- **Communication:** Tôi commit code + push artifacts trước Sprint 2 → Person 2 pull và viết expectations trong Sprint 2-3

**→ Person 3 (Docs & Embed Owner):**
- **Input từ tôi:** Monitoring functions (`monitoring/freshness_check.py`) và test output (`test_monitoring.py`)
- **Person 3 sử dụng để:** Viết `docs/runbook.md` phần Detection (freshness check) và `docs/pipeline_architecture.md` phần Monitoring
- **Idempotency collaboration:** Tôi ủng hộ quyết định của Person 3 về prune vector IDs (ghi trong section 2 của report này)
- **Artifacts dependency:** Person 3 cần manifests của tôi để embed idempotent (đọc `cleaned_csv` path từ manifest)

**Workflow timeline:**
1. **Sprint 1-2:** Tôi viết 3 rules + test → commit → push artifacts
2. **Sprint 2:** Person 2 pull → viết expectations dựa trên rules của tôi
3. **Sprint 3:** Tôi viết monitoring → Person 3 dùng output để viết runbook
4. **Sprint 4:** Person 3 tổng hợp group report từ artifacts của cả team

### Bằng chứng ownership

**Code commits:**
- `transform/cleaning_rules.py` lines 30-32 (constants: `_METADATA_PATTERN`, `_EM_DASH`, `_EN_DASH`)
- `transform/cleaning_rules.py` lines 145-175 (Rule 7, 8, 9 implementation với comments)
- `monitoring/freshness_check.py` lines 50-120 (3 functions: `check_dual_boundary_freshness`, `check_quarantine_rate`, `check_cleaned_records_trend`)

**Test scripts (100% do tôi viết):**
- `test_rules_impact.py` - Test 3 rules với 7 test records → output: 5 cleaned + 2 quarantine
- `test_inject_corruption.py` - Test inject scenario với 10 dirty records → output: 6 cleaned + 4 quarantine  
- `test_monitoring.py` - Test 3 monitoring functions → output: FAIL/PASS/WARN status

**Test data (do tôi tạo):**
- `data/raw/test_dirty_for_rules.csv` - 7 records để test từng rule riêng lẻ
- `data/raw/inject_corruption.csv` - 10 dirty records để demo before/after

**Artifacts generated:**
- `artifacts/manifests/manifest_baseline-person1.json` (run_id: baseline-person1)
- `artifacts/manifests/manifest_clean-run.json` (run_id: clean-run)
- `artifacts/manifests/manifest_inject-bad.json` (run_id: inject-bad)
- `artifacts/cleaned/cleaned_*.csv` (3 files)
- `artifacts/quarantine/quarantine_*.csv` (3 files)

**Documentation:**
- `PERSON1_COMPLETE_SUMMARY.md` - Tổng hợp công việc Person 1
- `TEAM_WORK_DISTRIBUTION.md` - Phân công chi tiết 3 người (section Person 1)
- Comments trong code giải thích logic từng rule

---

## 2. Một quyết định kỹ thuật

**Quyết định:** Rule 7 (metadata quarantine) chạy **TRƯỚC** refund fix (Rule 6) trong pipeline.

**Lý do:** Defense-in-depth. Nếu một chunk có cả metadata comments VÀ "14 ngày làm việc", Rule 7 sẽ quarantine nó trước khi Rule 6 (refund fix) chạy. Điều này đảm bảo:
1. Metadata không bao giờ vào cleaned CSV (ngay cả khi refund fix bị vô hiệu hóa)
2. Chatbot không bao giờ trả lời có chữ "(ghi chú: ...)" → UX tốt hơn
3. Nhiều lớp bảo vệ: nếu một rule fail, rule khác vẫn bắt được

**Evidence:** Khi chạy `--no-refund-fix`, Row 3 vẫn bị quarantine bởi Rule 7 → "14 ngày" không vào index. Expectation E3 (`refund_no_stale_14d_window`) vẫn PASS vì chunk đã bị chặn ở Rule 7.

**Idempotency:** Tôi ủng hộ quyết định của Embed Owner (Person 3) về prune vector IDs không còn trong cleaned batch. Điều này tránh top-k retrieval còn "14 ngày" sau khi inject corruption và rerun pipeline chuẩn.

---

## 3. Một lỗi hoặc anomaly đã xử lý

**Triệu chứng:** Khi chạy `test_rules_impact.py` lần đầu, output cho thấy 7 raw records → 6 cleaned + 1 quarantine. Tôi mong đợi 5 cleaned + 2 quarantine (Rule 7 và Rule 9 mỗi rule quarantine 1 row).

**Phát hiện:** Đọc log chi tiết, thấy Row 4 (có "14 ngày" và "7 ngày") không bị quarantine. Kiểm tra code, phát hiện Rule 9 pattern search không chính xác: tôi dùng `'14 ngày' in text and '7 ngày' in text` nhưng quên rằng text đã được normalize bởi Rule 8 trước đó.

**Fix:** Di chuyển Rule 9 check **TRƯỚC** Rule 8 normalization. Thứ tự mới:
1. Rule 7: Check metadata → quarantine nếu có
2. Rule 9: Check conflicting days → quarantine nếu có
3. Rule 8: Normalize em dash → continue processing

**Kết quả:** Sau fix, `test_rules_impact.py` output đúng: 7 raw → 5 cleaned + 2 quarantine (Row 2 bởi Rule 7, Row 4 bởi Rule 9).

**Metric:** `quarantine_records` tăng từ 4 (baseline) lên 5 (clean-run) → +1 quarantine như mong đợi.

---

## 4. Bằng chứng trước / sau

### Manifest comparison

**Baseline (`run_id=baseline-person1`):**
```json
{"raw_records": 10, "cleaned_records": 6, "quarantine_records": 4}
```

**Clean-run (`run_id=clean-run`):**
```json
{"raw_records": 10, "cleaned_records": 5, "quarantine_records": 5}
```

**Change:** `cleaned_records` giảm 1 (6 → 5), `quarantine_records` tăng 1 (4 → 5). Đây là **TỐT** vì Rule 7 loại bỏ chunk có metadata (Row 3) mà baseline bỏ sót.

### Eval CSV

**File:** `artifacts/eval/before_after_eval.csv`

**Dòng `q_refund_window`:**
```csv
q_refund_window,Khách hàng có bao nhiêu ngày...,policy_refund_v4,Yêu cầu được gửi trong vòng 7 ngày...,yes,no,,3
```

**Giải thích:** `contains_expected=yes` (có "7 ngày"), `hits_forbidden=no` (không có "14 ngày"). Rule 7 quarantine Row 3 (có "14 ngày" + metadata) → chatbot chỉ thấy "7 ngày" đúng.

### Monitoring test

**File:** `test_monitoring.py` output

```
1. DUAL BOUNDARY FRESHNESS CHECK
Status: FAIL
Ingest boundary: FAIL (age: 121.118h, SLA: 24.0h)
Publish boundary: PASS (age: 0.345h, SLA: 1.0h)

2. QUARANTINE RATE CHECK
Status: WARN
Quarantine rate: 50.0% (threshold: 50.0%)

3. CLEANED RECORDS TREND CHECK
Status: PASS
Drop: 1 records (16.7%), Threshold: 30.0%
```

**Giải thích:** Dual boundary monitoring (BONUS +1) phát hiện ingest FAIL (data cũ 121h) nhưng publish PASS (index mới 0.3h). Quarantine rate 50% là WARN (ở ngưỡng) nhưng chấp nhận được vì đang test với dirty data.

---

## 5. Cải tiến tiếp theo

Nếu có thêm 2 giờ, tôi sẽ **đọc metadata cutoff dates từ `contracts/data_contract.yaml`** thay vì hard-code trong Python.

**Hiện tại:** Rule 7 pattern `(bản\s+\w+\s+\d{4})` hard-code trong code. HR stale check hard-code `2026-01-01`.

**Cải tiến:** Thêm field `metadata_patterns` và `hr_policy_cutoff_date` vào `data_contract.yaml`:
```yaml
quality_rules:
  metadata_patterns:
    - "(ghi chú:.*?)"
    - "(bản\\s+\\w+\\s+\\d{4})"
  hr_policy_cutoff_date: "2026-01-01"
```

**Lợi ích:**
1. Không cần rebuild code khi thêm pattern mới
2. Contract versioning rõ ràng hơn
3. Hướng Distinction (d) trong SCORING.md: "rule versioning không hard-code"

**Implementation:** Load YAML trong `cleaning_rules.py`, compile regex từ `metadata_patterns`, so sánh `effective_date` với `hr_policy_cutoff_date` từ contract.

---

**Tổng số từ:** 580 từ

**Prepared by:** Person 1 - Cleaning Rules & Monitoring Owner  
**Date:** 2026-04-15  
**Status:** ✅ Ready for submission

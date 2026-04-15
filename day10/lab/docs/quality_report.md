# Quality Report — Lab Day 10

**run_id (final clean):** `person2-final` *(sẽ cập nhật sau khi chạy lại với allowlist mới)*  
**run_id (inject stale refund):** `person2-inject`  
**run_id (inject R8/R9 rules test):** `person2-inject-rules`  
**Ngày:** 2026-04-15  
**Owner:** Dam Le Van Toan (Cleaning & Quality Owner — Person 2)
**Allowlist vào thời điểm này:** `policy_refund_v4`, `sla_p1_2026`, `it_helpdesk_faq`, `hr_leave_policy`, **`access_control_sop`** *(mới thêm)*

---

## 1. Tóm tắt số liệu

> Sau khi merge cleaning rules của Person 1 (Rule 7: metadata quarantine, Rule 8: dash normalize, Rule 9: conflict day quarantine), số liệu pipeline thay đổi so với baseline:

| Chỉ số | Baseline (trước Person 1's rules) | Sau merge (Person 1 + Person 2 rules) | Ghi chú |
|--------|-----------------------------------|---------------------------------------|---------|
| raw_records | 10 | 10 | CSV mẫu không đổi |
| cleaned_records | 6 | **5** | Row 3 bị quarantine bởi Person 1's Rule 7 |
| quarantine_records | 4 | **5** | Row 3: `contains_metadata_comments` |
| Expectation halt? | NO — 8/8 pass | NO — **9/9 pass** | E9 mới thêm |

**Quarantine breakdown (sau merge):**

| reason | count | Rule gây ra |
|--------|-------|-------------|
| unknown_doc_id | 1 | Baseline (allowlist) |
| missing_effective_date | 1 | Baseline |
| duplicate_chunk_text | 1 | Baseline (dedupe) |
| stale_hr_policy_effective_date | 1 | Baseline (HR stale) |
| **contains_metadata_comments** | **1** | **Person 1 Rule 7 (mới)** |

**Row 3 quarantined:** `"...14 ngày làm việc kể từ xác nhận đơn (ghi chú: bản sync cũ policy-v3 — lỗi migration)."` → bị Rule 7's `_METADATA_PATTERN` bắt.

---

## 2. Before / after retrieval

> File: `artifacts/eval/before_after_eval.csv` (sau clean), `artifacts/eval/after_inject_bad.csv` (inject stale refund)

### Câu q_refund_window — Cửa sổ hoàn tiền

| Scenario | contains_expected | hits_forbidden | Ghi chú |
|----------|------------------|----------------|---------|
| **Inject `--no-refund-fix`** | yes | **NO** | Row 3 bị quarantine tại Rule 7 trước khi tới refund fix → `14 ngày` không vào index |
| **Clean (pipeline chuẩn)** | yes | **NO** | Row 3 bị quarantine — cùng kết quả |

> **Thay đổi quan trọng sau merge:** Person 1's Rule 7 quarantine Row 3 (có metadata comment) TRƯỚC khi bước refund fix chạy. Do đó inject `--no-refund-fix` không còn trigger `E3 FAIL` nữa — chunk "14 ngày" bị chặn ở Rule 7, không bao giờ vào index dù có hay không có `apply_refund_window_fix`. Đây là **defensive design tốt hơn**: nhiều lớp bảo vệ.

### Câu q_leave_version — Phiên bản phép năm HR (Merit evidence)

| Scenario | contains_expected | hits_forbidden | top1_doc_expected |
|----------|------------------|----------------|-------------------|
| **Inject** | yes | no | yes |
| **Clean** | yes | no | yes |

> HR versioning vẫn đúng — chunk 2025 bị quarantine trước Rule 7 (HR stale rule chạy trước).

---

## 3. Freshness & Monitor

**Kết quả:** `freshness_check=FAIL` — CSV mẫu có `exported_at=2026-04-10T08:00:00`, cách ~120h, vượt SLA 24h.

```json
{"latest_exported_at": "2026-04-10T08:00:00", "age_hours": 120.2, "sla_hours": 24.0, "reason": "freshness_sla_exceeded"}
```

**Diễn giải:** Hành vi đúng — CSV mẫu là snapshot giả lập cũ. Trong production, FAIL sẽ trigger alert. Được ghi nhận trong runbook là chấp nhận được cho lab.

---

## 4. Expectation Suite — Tổng hợp (9 expectations sau merge)

| ID | Tên | Severity | Baseline | Inject |
|----|-----|----------|----------|--------|
| E1 | min_one_row | halt | OK | OK |
| E2 | no_empty_doc_id | halt | OK | OK |
| E3 | refund_no_stale_14d_window | halt | OK | OK *(Person 1's Rule 7 chặn trước)* |
| E4 | chunk_min_length_8 | warn | OK | OK |
| E5 | effective_date_iso_yyyy_mm_dd | halt | OK | OK |
| E6 | hr_leave_no_stale_10d_annual | halt | OK | OK |
| **E7** | **no_bom_or_control_in_chunk_text** | **halt** | OK | OK |
| **E8** | **chunk_ids_unique** | **halt** | OK | OK |
| **E9** | **no_metadata_comments_in_cleaned** | **halt** | OK | OK |
| **E10** | **doc_id_in_contract_allowlist** | **warn** | OK | OK |

*E7, E8 = Person 2 (BOM guard, unique chunk_id). E9 = Person 2 validate Person 1's Rule 7. E10 = Person 2 mirror ALLOWED_DOC_IDS từ `cleaning_rules.py` vào expectation — tự động cập nhật khi contract mở rộng (vd `access_control_sop`).*

---

## 6. Allowlist mở rộng — `access_control_sop` (git pull từ main)

**Thay đổi:** `ALLOWED_DOC_IDS` trong `cleaning_rules.py` được thêm `"access_control_sop"` để đồng bộ với `contracts/data_contract.yaml` (source `data/docs/access_control_sop.txt`, `effective_from: 2026-02-01`).

**Tác động lên Person 2's files:**
- Số liệu CSV mẫu hiện tại **không đổi** (chưa có chunk nào `doc_id=access_control_sop` trong `policy_export_dirty.csv`).
- `quality/expectations.py` được thêm **E10** `doc_id_in_contract_allowlist` — import trực tiếp `ALLOWED_DOC_IDS` từ `cleaning_rules.py`, tự động cập nhật sau lần mở rộng này và lần tiếp theo.
- Nếu nhóm nhập CSV thật có chunk `access_control_sop`, chúng sẽ được process (không bị `unknown_doc_id`) và E10 mớị chứng minh pipeline đã sync contract.

**File inject:** `data/raw/inject_rules_test.csv` (4 dòng test)

| Dòng inject | Rule kích hoạt | Quarantine reason | Kết quả |
|-------------|----------------|-------------------|---------|
| BOM + chunk `it_helpdesk_faq` | **R7 (Person 2)** | — (BOM stripped, cleaned) | ✅ cleaned |
| `effective_date=2030-06-01` | **R8 (Person 2)** | `far_future_effective_date` | ❌ quarantined |
| `exported_at` rỗng | **R9 (Person 2)** | `missing_exported_at` | ❌ quarantined |

**Kết quả:** `raw_records=4` → `cleaned_records=2`, `quarantine_records=2` — chứng minh R8, R9 có metric_impact thực tế.

---

## 6. Tác động khi merge Person 1 + Person 2 rules

| Thay đổi | Nguyên nhân | Tác động |
|----------|-------------|---------|
| `cleaned_records` 6 → **5** | Person 1 Rule 7 quarantine Row 3 | Ít chunk hơn nhưng sạch hơn (không có metadata) |
| `quarantine_records` 4 → **5** | `contains_metadata_comments` | Log quarantine rõ ràng hơn |
| Inject `--no-refund-fix` không còn FAIL E3 | Rule 7 chặn "14 ngày" chunk trước khi refund check | Defense-in-depth: pipeline an toàn hơn |
| Thêm E9 | Validate output của Person 1's Rule 7 | Cross-team validation: cleaning rule ↔ expectation |

---

## 7. Hạn chế & Việc chưa làm

- Chiến lược freshness SLA 24h cứng trong `.env`; chưa có alert channel thực (email/Slack).
- Chưa tích hợp Great Expectations hoặc pydantic model validate schema đầy đủ.
- Inject test FAIL E3 cần tạo row mới không có metadata comments nhưng có "14 ngày làm việc" plain text để demo E3 vẫn hoạt động.

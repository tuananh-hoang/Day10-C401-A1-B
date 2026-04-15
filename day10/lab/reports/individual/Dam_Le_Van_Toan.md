# Báo Cáo Cá Nhân — Lab Day 10: Data Pipeline & Data Observability

**Họ và tên:** Dam Le Van Toan  
**Vai trò:** Cleaning & Quality Owner (Person 2)  
**Ngày nộp:** 2026-04-15  
**Độ dài yêu cầu:** 400–650 từ

---

## 1. Tôi phụ trách phần nào?

**File / module:**

- `quality/expectations.py` — thêm 3 expectation mới (E7, E8, E9)
- `transform/cleaning_rules.py` — đóng góp 3 rule (R7 BOM guard, R8 far-future date, R9 missing exported_at); phối hợp merge với Person 1's Rule 7/8/9

**Kết nối với thành viên khác:**

- **Person 1 (Cleaning Owner):** Merge rules trực tiếp trong `cleaning_rules.py` — Person 1 thêm Rule 7 (metadata quarantine), Rule 8 (dash normalize), Rule 9 (conflict day values). Tôi thêm R7 BOM, R8 far-future date, R9 missing exported_at. Thứ tự rule quan trọng: R9 và R8 của tôi chạy trước Rule 7 của Person 1 trong flow, còn R7 BOM của tôi chạy sau (lớp cuối cùng trước dedup).
- **Person 3 (Embed Owner):** Expectation E8 (`chunk_ids_unique`) của tôi trực tiếp bảo vệ ChromaDB của Person 3 khỏi silent overwrite.

**Bằng chứng:**

- `quality/expectations.py` tăng từ 6 (baseline) lên 9 expectation sau merge
- `_strip_control_chars()` function trong `cleaning_rules.py` do tôi viết, vẫn còn trong file
- Log `artifacts/logs/run_person2-final.log` thể hiện 8/8 expectation OK

---

## 2. Một quyết định kỹ thuật: Thêm E9 để cross-validate Person 1's Rule 7

Sau khi merge code với Person 1, tôi thêm **E9 `no_metadata_comments_in_cleaned`** (severity=halt) để xác minh output của Rule 7 (Person 1).

**Lý do:** Đây là nguyên tắc **defense-in-depth** trong data pipeline: cleaning rule và expectation là 2 lớp độc lập. Nếu regex trong Rule 7 bị sửa sai (thêm lookahead, thay đổi flag), cleaning rule sẽ không bắt được chunk metadata nữa, nhưng E9 sẽ phát hiện khi expectation chạy.

Pattern regex trong E9 dùng chính xác cùng pattern với `_METADATA_PATTERN` của Person 1, đảm bảo tính nhất quán. Tôi chọn halt thay vì warn vì metadata comment như `"(ghi chú: bản sync cũ policy-v3)"` trong context RAG sẽ làm agent trả lời thông tin sai (`"bản sync cũ"` thay vì chính sách thật).

---

## 3. Một lỗi / anomaly đã xử lý: Inject scenario E3 không còn FAIL sau merge

**Triệu chứng:** Sau khi merge Person 1's Rule 7 vào pipeline, tôi thấy inject run `--no-refund-fix` không còn ra `expectation[refund_no_stale_14d_window] FAIL` như trước.

**Phân tích:** Person 1's Rule 7 quarantine Row 3 (chứa `"(ghi chú: bản sync cũ policy-v3)"`) **trước khi** bước refund window check chạy. Row 3 cũng là chunk duy nhất chứa `"14 ngày làm việc"` trong CSV mẫu. Vì nó bị loại sớm bởi metadata rule, expectation `refund_no_stale_14d_window` không còn thấy vi phạm dù có `--no-refund-fix`.

**Đây không phải lỗi mà là defense-in-depth tốt hơn:** chunk stale bị block bởi 2 rule khác nhau (Rule 7 metadata + E3 refund check). Tôi ghi nhận trong quality report mục "Tác động khi merge rules" để team hiểu sự thay đổi và không nhầm với regression.

---

## 4. Bằng chứng trước / sau

**Trước merge (run_id: `baseline-person2`)** — 6 expectations (baseline):
```
cleaned_records=6  |  quarantine_records=4
expectation[refund_no_stale_14d_window] OK :: violations=0
```

**Sau merge (run_id: `person2-final`)** — 9 expectations (Person 1 + Person 2 rules):
```
cleaned_records=5  |  quarantine_records=5
expectation[no_bom_or_control_in_chunk_text] OK (halt) :: chunks_with_hidden_chars=0
expectation[chunk_ids_unique] OK (halt) :: duplicate_chunk_ids=0
expectation[no_metadata_comments_in_cleaned] OK (halt) :: chunks_with_metadata_pattern=0
PIPELINE_OK
```

**Inject R8/R9 evidence (run_id: `person2-inject-rules`):**
```
raw_records=4  →  cleaned_records=2  |  quarantine_records=2
# Row với date=2030-06-01 → quarantine: far_future_effective_date
# Row thiếu exported_at    → quarantine: missing_exported_at
```

Trích `artifacts/eval/before_after_eval.csv` (q_refund_window):
```
contains_expected=yes, hits_forbidden=no  ← pipeline chuẩn
```

---

## 5. Cải tiến tiếp theo (nếu có thêm 2 giờ)

Tôi muốn tạo **bộ inject test tự động** chứng minh E3 vẫn hoạt động sau khi merge: thêm một dòng raw CSV chứa `"14 ngày làm việc"` plain text (không có metadata comment) và chạy `--no-refund-fix`. Dòng này sẽ không bị Rule 7 bắt (vì không có pattern `(ghi chú:...)`), nhưng E3 sẽ FAIL khi nó lọt vào cleaned rows. Điều này chứng minh hệ thống 2 lớp bảo vệ (Rule 7 + E3) hoạt động đúng theo từng trường hợp, không phải "may mắn" do 1 rule chặn hết.

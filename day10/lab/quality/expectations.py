"""
Expectation suite đơn giản (không bắt buộc Great Expectations).

Sinh viên có thể thay bằng GE / pydantic / custom — miễn là có halt có kiểm soát.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple


@dataclass
class ExpectationResult:
    name: str
    passed: bool
    severity: str  # "warn" | "halt"
    detail: str


def run_expectations(cleaned_rows: List[Dict[str, Any]]) -> Tuple[List[ExpectationResult], bool]:
    """
    Trả về (results, should_halt).

    should_halt = True nếu có bất kỳ expectation severity halt nào fail.
    """
    results: List[ExpectationResult] = []

    # E1: có ít nhất 1 dòng sau clean
    ok = len(cleaned_rows) >= 1
    results.append(
        ExpectationResult(
            "min_one_row",
            ok,
            "halt",
            f"cleaned_rows={len(cleaned_rows)}",
        )
    )

    # E2: không doc_id rỗng
    bad_doc = [r for r in cleaned_rows if not (r.get("doc_id") or "").strip()]
    ok2 = len(bad_doc) == 0
    results.append(
        ExpectationResult(
            "no_empty_doc_id",
            ok2,
            "halt",
            f"empty_doc_id_count={len(bad_doc)}",
        )
    )

    # E3: policy refund không được chứa cửa sổ sai 14 ngày (sau khi đã fix)
    bad_refund = [
        r
        for r in cleaned_rows
        if r.get("doc_id") == "policy_refund_v4"
        and "14 ngày làm việc" in (r.get("chunk_text") or "")
    ]
    ok3 = len(bad_refund) == 0
    results.append(
        ExpectationResult(
            "refund_no_stale_14d_window",
            ok3,
            "halt",
            f"violations={len(bad_refund)}",
        )
    )

    # E4: chunk_text đủ dài
    short = [r for r in cleaned_rows if len((r.get("chunk_text") or "")) < 8]
    ok4 = len(short) == 0
    results.append(
        ExpectationResult(
            "chunk_min_length_8",
            ok4,
            "warn",
            f"short_chunks={len(short)}",
        )
    )

    # E5: effective_date đúng định dạng ISO sau clean (phát hiện parser lỏng)
    iso_bad = [
        r
        for r in cleaned_rows
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", (r.get("effective_date") or "").strip())
    ]
    ok5 = len(iso_bad) == 0
    results.append(
        ExpectationResult(
            "effective_date_iso_yyyy_mm_dd",
            ok5,
            "halt",
            f"non_iso_rows={len(iso_bad)}",
        )
    )

    # E6: không còn marker phép năm cũ 10 ngày trên doc HR (conflict version sau clean)
    bad_hr_annual = [
        r
        for r in cleaned_rows
        if r.get("doc_id") == "hr_leave_policy"
        and "10 ngày phép năm" in (r.get("chunk_text") or "")
    ]
    ok6 = len(bad_hr_annual) == 0
    results.append(
        ExpectationResult(
            "hr_leave_no_stale_10d_annual",
            ok6,
            "halt",
            f"violations={len(bad_hr_annual)}",
        )
    )

    # E7 (new — Person 2): không có BOM / control character trong chunk_text sau clean.
    # Cleaning rule R7 nên đã strip/quarantine, expectation này là lớp xác minh lại.
    # severity=halt: BOM ẩn làm hỏng exact-match ở retrieval và embedding vector.
    # metric_impact: inject dòng chứa BOM mà không qua cleaning fix → E7 FAIL;
    #   sau khi R7 hoạt động đúng → E7 OK; baseline CSV không BOM → OK ngay.
    _BOM_CHARS = frozenset('\ufeff\u200b\u200c\u200d')
    _CTRL = frozenset(chr(c) for c in range(0x00, 0x20) if c not in (0x09, 0x0A, 0x0D))
    bad_bom = [
        r
        for r in cleaned_rows
        if any(c in _BOM_CHARS or c in _CTRL for c in (r.get("chunk_text") or ""))
    ]
    ok7 = len(bad_bom) == 0
    results.append(
        ExpectationResult(
            "no_bom_or_control_in_chunk_text",
            ok7,
            "halt",
            f"chunks_with_hidden_chars={len(bad_bom)}",
        )
    )

    # E8 (new — Person 2): tất cả chunk_id trong cleaned output phải unique.
    # severity=halt: chunk_id trùng → ChromaDB upsert sẽ ghi đè vector không kiểm soát,
    #   gây mất dữ liệu âm thầm trong index.
    # metric_impact: inject 2 dòng khác nhau nhưng cố tình tạo ra cùng chunk_id
    #   (hoặc cleaning hash collision) → E8 FAIL; baseline + các run chuẩn → E8 OK.
    all_ids = [r.get("chunk_id") or "" for r in cleaned_rows]
    dup_ids = len(all_ids) - len(set(all_ids))
    ok8 = dup_ids == 0
    results.append(
        ExpectationResult(
            "chunk_ids_unique",
            ok8,
            "halt",
            f"duplicate_chunk_ids={dup_ids}",
        )
    )

    # E9 (new — Person 2 validates Person 1's Rule 7):
    # Không có metadata / comments pattern trong chunk_text của cleaned rows.
    # Expectation này là lớp xác minh output của cleaning Rule 7 (Person 1):
    #   nếu Rule 7 bị bypass hoặc pattern regex thay đổi, E9 sẽ FAIL và halt pipeline.
    # severity=halt: metadata như "(ghi chú: bản sync cũ)" làm nhiễu retrieval —
    #   agent sẽ trả lời "bản sync cũ policy-v3" thay vì nội dung chính sách thật.
    # metric_impact: inject dòng có "(ghi chú:...)" không qua Rule 7 → E9 FAIL;
    #   trên CSV mẫu sau khi Rule 7 hoạt động → E9 OK.
    _META_PAT = re.compile(r'\(ghi chú:.*?\)|\(bản\s+\w+\s+\d{4}\)', re.IGNORECASE)
    bad_meta = [
        r
        for r in cleaned_rows
        if _META_PAT.search(r.get("chunk_text") or "")
    ]
    ok9 = len(bad_meta) == 0
    results.append(
        ExpectationResult(
            "no_metadata_comments_in_cleaned",
            ok9,
            "halt",
            f"chunks_with_metadata_pattern={len(bad_meta)}",
        )
    )

    # E10 (new — Person 2): tất cả doc_id trong cleaned rows phải thuộc ALLOWED_DOC_IDS.
    # Expectation này mirror contract allowlist từ cleaning_rules.py,
    # đảm bảo khi nhóm thêm doc_id mới (vd access_control_sop), cả cleaning lẫn
    # expectation đều đồng bộ — không cần sửa expectations.py mỗi khi contract đổi.
    # severity=warn: cleaning đã lọc doc_id ở cổng đầu, nên cleaned rows về lý thuyết
    #   luôn thuộc allowlist. Nếu E10 FAIL → có lỗi logic nghiêm trọng trong pipeline.
    # metric_impact: thêm doc_id mới vào allowlist mà chưa update cleaning →
    #   chunk đó không qua → warn khi count < expected; ngược lại cleaning lọc sai → E10 warn.
    try:
        from transform.cleaning_rules import ALLOWED_DOC_IDS as _ALLOWED
        bad_docid = [
            r for r in cleaned_rows
            if (r.get("doc_id") or "") not in _ALLOWED
        ]
        ok10 = len(bad_docid) == 0
        results.append(
            ExpectationResult(
                "doc_id_in_contract_allowlist",
                ok10,
                "warn",
                f"out_of_contract_doc_ids={len(bad_docid)}"
                + (f" ({set(r.get('doc_id') for r in bad_docid)})" if bad_docid else ""),
            )
        )
    except ImportError:
        results.append(
            ExpectationResult(
                "doc_id_in_contract_allowlist",
                False,
                "warn",
                "import_error: cannot load ALLOWED_DOC_IDS from cleaning_rules",
            )
        )

    halt = any(not r.passed and r.severity == "halt" for r in results)
    return results, halt

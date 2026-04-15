"""
Kiểm tra freshness từ manifest pipeline (SLA đơn giản theo giờ).

Sinh viên mở rộng: đọc watermark DB, so sánh với clock batch, v.v.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Tuple


def parse_iso(ts: str) -> datetime | None:
    if not ts:
        return None
    try:
        # Cho phép "2026-04-10T08:00:00" không có timezone
        if ts.endswith("Z"):
            return datetime.fromisoformat(ts.replace("Z", "+00:00"))
        dt = datetime.fromisoformat(ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def check_manifest_freshness(
    manifest_path: Path,
    *,
    sla_hours: float = 24.0,
    now: datetime | None = None,
) -> Tuple[str, Dict[str, Any]]:
    """
    Trả về ("PASS" | "WARN" | "FAIL", detail dict).

    Đọc trường `latest_exported_at` hoặc max exported_at trong cleaned summary.
    """
    now = now or datetime.now(timezone.utc)
    if not manifest_path.is_file():
        return "FAIL", {"reason": "manifest_missing", "path": str(manifest_path)}

    data: Dict[str, Any] = json.loads(manifest_path.read_text(encoding="utf-8"))
    ts_raw = data.get("latest_exported_at") or data.get("run_timestamp")
    dt = parse_iso(str(ts_raw)) if ts_raw else None
    if dt is None:
        return "WARN", {"reason": "no_timestamp_in_manifest", "manifest": data}

    age_hours = (now - dt).total_seconds() / 3600.0
    detail = {
        "latest_exported_at": ts_raw,
        "age_hours": round(age_hours, 3),
        "sla_hours": sla_hours,
    }
    if age_hours <= sla_hours:
        return "PASS", detail
    return "FAIL", {**detail, "reason": "freshness_sla_exceeded"}


def check_dual_boundary_freshness(
    manifest_path: Path,
    *,
    ingest_sla_hours: float = 24.0,
    publish_sla_hours: float = 1.0,
    now: datetime | None = None,
) -> Tuple[str, Dict[str, Any]]:
    """
    Check 2 boundaries (Person 1 enhancement - BONUS eligible):
    1. Ingest boundary: latest_exported_at (khi data export từ source)
    2. Publish boundary: run_timestamp (khi data embed vào vector DB)
    
    Trả về ("PASS" | "WARN" | "FAIL", detail dict).
    
    FAIL nếu bất kỳ boundary nào vượt SLA.
    """
    now = now or datetime.now(timezone.utc)
    if not manifest_path.is_file():
        return "FAIL", {"reason": "manifest_missing", "path": str(manifest_path)}

    data: Dict[str, Any] = json.loads(manifest_path.read_text(encoding="utf-8"))
    
    # Boundary 1: Ingest (data từ source)
    ingest_ts = parse_iso(str(data.get("latest_exported_at", "")))
    ingest_age = (now - ingest_ts).total_seconds() / 3600.0 if ingest_ts else None
    
    # Boundary 2: Publish (data vào vector DB)
    publish_ts = parse_iso(str(data.get("run_timestamp", "")))
    publish_age = (now - publish_ts).total_seconds() / 3600.0 if publish_ts else None
    
    detail = {
        "ingest": {
            "timestamp": str(ingest_ts) if ingest_ts else None,
            "age_hours": round(ingest_age, 3) if ingest_age else None,
            "sla_hours": ingest_sla_hours,
            "status": "PASS" if ingest_age and ingest_age <= ingest_sla_hours else "FAIL"
        },
        "publish": {
            "timestamp": str(publish_ts) if publish_ts else None,
            "age_hours": round(publish_age, 3) if publish_age else None,
            "sla_hours": publish_sla_hours,
            "status": "PASS" if publish_age and publish_age <= publish_sla_hours else "FAIL"
        }
    }
    
    # Overall status: FAIL nếu bất kỳ boundary nào FAIL
    if detail["ingest"]["status"] == "FAIL" or detail["publish"]["status"] == "FAIL":
        return "FAIL", detail
    return "PASS", detail


def check_quarantine_rate(
    manifest_path: Path,
    *,
    max_quarantine_rate: float = 0.5,
) -> Tuple[str, Dict[str, Any]]:
    """
    Cảnh báo nếu tỷ lệ quarantine quá cao (Person 1 enhancement).
    
    Nếu > 50% data bị quarantine → có vấn đề với source data hoặc rules quá strict.
    Nếu > 40% → WARN (gần ngưỡng).
    
    Trả về ("PASS" | "WARN" | "FAIL", detail dict).
    """
    if not manifest_path.is_file():
        return "FAIL", {"reason": "manifest_missing", "path": str(manifest_path)}
    
    data: Dict[str, Any] = json.loads(manifest_path.read_text(encoding="utf-8"))
    raw = data.get("raw_records", 0)
    quarantine = data.get("quarantine_records", 0)
    
    if raw == 0:
        return "WARN", {"reason": "no_raw_records"}
    
    rate = quarantine / raw
    detail = {
        "raw_records": raw,
        "quarantine_records": quarantine,
        "quarantine_rate": round(rate, 3),
        "threshold": max_quarantine_rate
    }
    
    if rate > max_quarantine_rate:
        return "FAIL", {**detail, "reason": "quarantine_rate_exceeded"}
    elif rate > max_quarantine_rate * 0.8:  # 40%
        return "WARN", {**detail, "reason": "quarantine_rate_high"}
    return "PASS", detail


def check_cleaned_records_trend(
    current_manifest: Path,
    baseline_manifest: Path,
    *,
    max_drop_rate: float = 0.3,
) -> Tuple[str, Dict[str, Any]]:
    """
    So sánh cleaned_records với baseline (Person 1 enhancement).
    
    Cảnh báo nếu cleaned_records giảm > 30% so với baseline.
    Có thể do: rules mới quá strict, hoặc source data quality giảm.
    
    Trả về ("PASS" | "WARN" | "FAIL", detail dict).
    """
    if not current_manifest.is_file() or not baseline_manifest.is_file():
        return "FAIL", {"reason": "manifest_missing"}
    
    current: Dict[str, Any] = json.loads(current_manifest.read_text(encoding="utf-8"))
    baseline: Dict[str, Any] = json.loads(baseline_manifest.read_text(encoding="utf-8"))
    
    current_cleaned = current.get("cleaned_records", 0)
    baseline_cleaned = baseline.get("cleaned_records", 0)
    
    if baseline_cleaned == 0:
        return "WARN", {"reason": "no_baseline_records"}
    
    drop_rate = (baseline_cleaned - current_cleaned) / baseline_cleaned
    detail = {
        "baseline_cleaned": baseline_cleaned,
        "current_cleaned": current_cleaned,
        "drop_count": baseline_cleaned - current_cleaned,
        "drop_rate": round(drop_rate, 3),
        "threshold": max_drop_rate
    }
    
    if drop_rate > max_drop_rate:
        return "WARN", {**detail, "reason": "cleaned_records_dropped_significantly"}
    return "PASS", detail

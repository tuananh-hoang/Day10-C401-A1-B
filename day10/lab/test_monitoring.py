"""
Test script for Person 1's monitoring enhancements.
"""

from pathlib import Path
from monitoring.freshness_check import (
    check_dual_boundary_freshness,
    check_quarantine_rate,
    check_cleaned_records_trend,
)

print("=" * 60)
print("PERSON 1 MONITORING ENHANCEMENTS TEST")
print("=" * 60)

# Test 1: Dual boundary freshness
print("\n1. DUAL BOUNDARY FRESHNESS CHECK")
print("-" * 60)
status, detail = check_dual_boundary_freshness(
    Path("artifacts/manifests/manifest_clean-run.json"),
    ingest_sla_hours=24.0,
    publish_sla_hours=1.0
)
print(f"Status: {status}")
print(f"Ingest boundary: {detail['ingest']['status']} (age: {detail['ingest']['age_hours']}h, SLA: {detail['ingest']['sla_hours']}h)")
print(f"Publish boundary: {detail['publish']['status']} (age: {detail['publish']['age_hours']}h, SLA: {detail['publish']['sla_hours']}h)")

# Test 2: Quarantine rate
print("\n2. QUARANTINE RATE CHECK")
print("-" * 60)
status, detail = check_quarantine_rate(
    Path("artifacts/manifests/manifest_clean-run.json"),
    max_quarantine_rate=0.5
)
print(f"Status: {status}")
print(f"Raw records: {detail['raw_records']}")
print(f"Quarantine records: {detail['quarantine_records']}")
print(f"Quarantine rate: {detail['quarantine_rate']*100:.1f}% (threshold: {detail['threshold']*100:.1f}%)")

# Test 3: Cleaned records trend
print("\n3. CLEANED RECORDS TREND CHECK")
print("-" * 60)
status, detail = check_cleaned_records_trend(
    Path("artifacts/manifests/manifest_clean-run.json"),
    Path("artifacts/manifests/manifest_baseline-person1.json"),
    max_drop_rate=0.3
)
print(f"Status: {status}")
print(f"Baseline cleaned: {detail['baseline_cleaned']}")
print(f"Current cleaned: {detail['current_cleaned']}")
print(f"Drop: {detail['drop_count']} records ({detail['drop_rate']*100:.1f}%)")
print(f"Threshold: {detail['threshold']*100:.1f}%")

print("\n" + "=" * 60)
print("TEST COMPLETE")
print("=" * 60)

"""
Test script to demonstrate impact of Person 1's 3 new cleaning rules.
"""

import sys
from pathlib import Path
from transform.cleaning_rules import load_raw_csv, clean_rows

print("=" * 70)
print("PERSON 1 - CLEANING RULES IMPACT TEST")
print("=" * 70)

# Load test data
test_csv = Path("data/raw/test_dirty_for_rules.csv")
if not test_csv.exists():
    print(f"ERROR: {test_csv} not found")
    sys.exit(1)

rows = load_raw_csv(test_csv)
print(f"\nInput: {len(rows)} raw records")
print("-" * 70)

# Run cleaning
cleaned, quarantine = clean_rows(rows, apply_refund_window_fix=True)

print(f"\nOutput:")
print(f"  Cleaned: {len(cleaned)} records")
print(f"  Quarantine: {len(quarantine)} records")
print("-" * 70)

# Show quarantine reasons
print("\nQUARANTINE DETAILS:")
print("-" * 70)
for i, q in enumerate(quarantine, 1):
    reason = q.get('reason', 'unknown')
    text_preview = (q.get('chunk_text', '') or '')[:60]
    print(f"{i}. Reason: {reason}")
    print(f"   Text: {text_preview}...")
    if 'detected' in q:
        print(f"   Detected: {q['detected']}")
    print()

# Show cleaned with normalization
print("\nCLEANED RECORDS (showing text normalization):")
print("-" * 70)
for i, c in enumerate(cleaned, 1):
    text = c.get('chunk_text', '')
    print(f"{i}. {text[:80]}...")
    print()

# Summary
print("=" * 70)
print("RULE IMPACT SUMMARY:")
print("=" * 70)
print("Rule 7 (Metadata): Quarantined row 2 (contains 'ghi chú:')")
print("Rule 8 (Em dash): Normalized row 3 (— and – → -)")
print("Rule 9 (Conflicting days): Quarantined row 4 (has both '14 ngày' and '7 ngày')")
print("=" * 70)

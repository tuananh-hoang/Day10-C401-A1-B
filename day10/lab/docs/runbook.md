# Runbook — Lab Day 10 (incident tối giản)

**Owner:** Nguyễn Quang Trường  
**Last updated:** 2026-04-15

---

## Symptom

**User/Agent observation:** Agent trả lời sai thông tin, ví dụ:
- "Khách hàng có 14 ngày để yêu cầu hoàn tiền" (sai - đúng là 7 ngày)
- "Nhân viên được 10 ngày phép năm" (sai - đúng là 12 ngày theo policy 2026)
- Retrieval trả về chunk có metadata như "(ghi chú: bản sync cũ...)"

**System observation:**
- Eval CSV shows `hits_forbidden=yes` for q_refund_window
- Grading JSONL shows `contains_expected=false` or `hits_forbidden=true`
- Agent confidence score low or contradictory answers

---

## Detection

**Automated metrics:**
1. **Freshness check:** `freshness_check=FAIL` in manifest
   - Trigger: `age_hours > sla_hours` (default 24h)
   - Location: `artifacts/manifests/manifest_<run-id>.json`

2. **Expectation failure:** `expectation[...] FAIL (halt)` in log
   - Examples:
     - `refund_no_stale_14d_window FAIL` → "14 ngày" found in cleaned data
     - `hr_leave_no_stale_10d_annual FAIL` → "10 ngày phép" found in cleaned data
   - Location: `artifacts/logs/run_<run-id>.log`

3. **Eval degradation:** `hits_forbidden=yes` or `contains_expected=no` in eval CSV
   - Location: `artifacts/eval/*.csv`
   - Compare with baseline: `before_after_eval.csv`

4. **Quarantine spike:** `quarantine_records` > 50% of `raw_records`
   - Indicates upstream data quality issue
   - Location: Manifest JSON `quarantine_records` field

**Manual detection:**
- User reports incorrect answer
- Spot check: Query "hoàn tiền" → check if top-k contains "14 ngày"

---

## Diagnosis

| Bước | Việc làm | Kết quả mong đợi | Command |
|------|----------|------------------|---------|
| 1 | Kiểm tra freshness | PASS (age < 24h) | `python etl_pipeline.py freshness --manifest artifacts/manifests/manifest_<run-id>.json` |
| 2 | Kiểm tra expectation log | All OK (halt) | `cat artifacts/logs/run_<run-id>.log \| grep expectation` |
| 3 | Kiểm tra quarantine CSV | Reason field shows root cause | `cat artifacts/quarantine/quarantine_<run-id>.csv` |
| 4 | Chạy eval retrieval | `hits_forbidden=no`, `contains_expected=yes` | `python eval_retrieval.py --out artifacts/eval/diagnosis.csv` |
| 5 | Kiểm tra cleaned CSV | No "14 ngày", no metadata, no stale HR | `cat artifacts/cleaned/cleaned_<run-id>.csv \| grep "14 ngày"` |

**Common root causes:**

| Symptom | Root cause | Evidence |
|---------|-----------|----------|
| `hits_forbidden=yes` for q_refund_window | Stale chunk "14 ngày" in index | Quarantine CSV missing row 3, or refund fix not applied |
| `contains_expected=no` for q_leave_version | Stale HR policy (10 ngày) in index | Quarantine CSV missing row 7, or HR version filter not applied |
| Freshness FAIL | `exported_at` too old (> 24h) | Manifest shows `age_hours=122.66` |
| Expectation halt | Cleaning rules failed | Log shows `expectation[...] FAIL (halt)` |
| High quarantine rate | Upstream data quality issue | Quarantine CSV shows many `invalid_date_format` or `unknown_doc_id` |

**Debug order (from Day 10 slide):**
```
Freshness / version → Volume & errors → Schema & contract → Lineage / run_id → mới đến model/prompt
```

---

## Mitigation

### Immediate actions (< 5 minutes)

1. **Rollback to last good run:**
   ```bash
   # Find last PASS run
   ls -lt artifacts/manifests/ | head -5
   
   # Check freshness of candidate
   python etl_pipeline.py freshness --manifest artifacts/manifests/manifest_<good-run-id>.json
   
   # If PASS, rebuild index from that cleaned CSV
   # (Manual: delete chroma_db/, rerun embed with that CSV)
   ```

2. **Temporary banner:** Notify users "Data being refreshed, answers may be stale"

3. **Stop serving:** If critical (e.g., financial policy), disable agent endpoint

### Short-term fix (< 30 minutes)

1. **Rerun pipeline with fix:**
   ```bash
   # Standard run (with refund fix, validation)
   python etl_pipeline.py run --run-id hotfix-$(date +%Y%m%d-%H%M)
   
   # Verify expectations PASS
   cat artifacts/logs/run_hotfix-*.log | grep FAIL
   
   # Verify eval
   python eval_retrieval.py --out artifacts/eval/hotfix_eval.csv
   cat artifacts/eval/hotfix_eval.csv | grep hits_forbidden
   ```

2. **If expectation still fails:**
   - Check quarantine CSV for new patterns
   - Add new cleaning rule or expectation
   - Test with `--skip-validate` first (diagnosis only, not production)

3. **If freshness FAIL:**
   - Contact upstream system owner to refresh export
   - Update `FRESHNESS_SLA_HOURS` in .env if SLA needs adjustment
   - Document exception in manifest

### Long-term prevention (< 2 hours)

1. **Add monitoring:**
   ```bash
   # Run monitoring checks
   python test_monitoring.py
   
   # Expected output:
   # - check_dual_boundary_freshness: PASS/WARN/FAIL
   # - check_quarantine_rate: PASS/WARN (threshold 50%)
   # - check_cleaned_records_trend: PASS (drop < 30%)
   ```

2. **Enhance expectations:**
   - Add expectation for new failure mode discovered
   - Example: If BOM found, add `no_bom_or_control_in_chunk_text`

3. **Update data contract:**
   - Document new source or failure mode in `data_contract.md`
   - Update `contracts/data_contract.yaml` with new constraints

4. **Improve cleaning rules:**
   - Add rule to catch new pattern (e.g., metadata comments)
   - Test impact with `test_rules_impact.py`

---

## Prevention

### Proactive measures

1. **Automated freshness alerts:**
   - Set up cron job to check freshness every 6 hours
   - Alert channel: Slack `#data-quality-alerts` or email `data-eng@company.com`
   - Threshold: WARN at 20h, FAIL at 24h

2. **Expectation monitoring:**
   - Track expectation failure rate over time
   - Alert if any halt expectation fails
   - Dashboard: Grafana panel showing `expectation_fail_count`

3. **Quarantine trend analysis:**
   - Weekly review of quarantine reasons
   - If `unknown_doc_id` increases → update allowlist or reject upstream
   - If `invalid_date_format` increases → fix upstream export

4. **Eval regression testing:**
   - Run `eval_retrieval.py` after every pipeline run
   - Compare with baseline: `before_after_eval.csv`
   - Alert if `hits_forbidden` changes from `no` to `yes`

5. **Data contract versioning:**
   - Version `data_contract.yaml` with semantic versioning
   - Breaking changes (new required field) → major version bump
   - New optional field → minor version bump

### Guardrails (Day 11 integration)

- **Pre-publish check:** Run eval before updating vector store
- **Canary deployment:** Serve 10% traffic from new index, monitor metrics
- **Rollback automation:** Auto-rollback if eval degradation detected
- **Human-in-the-loop:** Require approval for high-risk changes (e.g., new cleaning rule affecting >30% records)

### Ownership

| Component | Owner | Escalation |
|-----------|-------|------------|
| Freshness SLA | Data Engineering Lead | VP Engineering |
| Expectation failures | Quality Owner (Person 2) | Data Engineering Lead |
| Quarantine review | Cleaning Owner (Person 1) | Data Engineering Lead |
| Eval regression | Embed Owner (Person 2) | ML Engineering Lead |
| Upstream issues | Source system owners | VP Engineering |

### SLA commitments

- **Freshness:** 24 hours from `exported_at` to `run_timestamp`
- **Availability:** 99.5% uptime for vector store
- **Accuracy:** <1% `hits_forbidden` rate in production eval
- **Quarantine:** <30% quarantine rate (>30% triggers upstream investigation)

# DemandSYNC — RBAC & Security
**K:\DemandSYNC | 2026-09-21**

---

## 1. Roles (6 Portals, Same Backend/DB)

| Role | Portal | Employee Code Prefix | Representative IDs | Access |
|------|--------|----------------------|--------------------|--------|
| `ADMIN` | System Admin / Data Trust | `EMP2020` | `OFF-00671, OFF-00672` | Dataset import, validation, RBAC management, cycle creation |
| `DISTRICT_OFFICER` | DSO Control Centre | `EMP2021` | `OFF-00001..06` | Monitor → Lock → Allocate → Optimize → Authorize → Track → Reconcile → Close cycle |
| `FIELD_FOOD_INSPECTOR` | Inspector Portal | `EMP2022` | `OFF-00007..66` (60) | Select target → Inspect → Evidence → Seal |
| `FPS_OWNER` | FPS Dealer Portal | `EMP2023` | `OFF-06001..06600` (600, maps to `fps_master.owner_id = FPS-0001..0600`) | Receive dispatch, verify, dispense, ePOS, reconcile FPS |
| `BENEFICIARY` | Beneficiary Portal | `RC2023-*` (ration_card) | `BEN-000001..010000` (10k, via `beneficiaries_master`) | Intent submit, track, grievance, ePOS view |
| `AUDITOR` | Auditor Portal | `EMP2025` | `OFF-00668..673` (5) | Full trace, audit intelligence, seal audit |

`officers_master.csv:673 rows` covers first 5 roles; beneficiaries are separate table but authenticate via `ration_card_id` + OTP (synthetic).

## 2. Permissions Matrix

| Capability | ADMIN | DISTRICT_OFFICER | INSPECTOR | FPS_OWNER | BENEFICIARY | AUDITOR |
|------------|:-----:|:----------------:|:---------:|:---------:|:-----------:|:-------:|
| Import dataset | ✓ |  |  |  |  |  |
| Approve dataset ACTIVE | ✓ |  |  |  |  | ✓(read) |
| Open/close choice window |  | ✓ |  |  |  |  |
| Lock demand |  | ✓ |  |  |  |  |
| Approve allocation |  | ✓ |  |  |  |  |
| Authorize dispatch (LOCKED) |  | ✓ |  |  |  |  |
| Track vehicles |  | ✓ | ✓ |  |  | ✓ |
| Verify delivery |  |  | ✓ | ✓ |  |  |
| Submit intent |  |  |  |  | ✓ |  |
| Submit grievance |  |  |  |  | ✓ |  |
| ePOS dispense |  |  |  | ✓ | ✓(receive) |  |
| Submit inspection |  |  | ✓ |  |  |  |
| Seal inspection (SHA256) |  |  | ✓ |  |  |  |
| Audit trace / Seal audit |  |  |  |  |  | ✓ |
| Close cycle | ✓ | ✓ |  |  |  |  |
| View audit logs | ✓ | ✓ | ✓ | ✓(own FPS) | ✓(own) | ✓ |
| Manage users | ✓ |  |  |  |  |  |

## 3. Enforcement

*   **Backend:** FastAPI `Depends(get_current_user)` + `@require_role("DISTRICT_OFFICER")` per endpoint. Never frontend-only hiding. `JWT (HS256, 24h expiry, python-jose)` + `bcrypt (passlib)`.
*   **Database:** FK constraints, CHECKs (status enums, `entitlement = rice+wheat`, `closing = opening+received-dispatched-distributed`), triggers (demand_locks immutable, manifest hash).
*   **Audit:** Append-only `audit_logs` — every state transition logs `who/what/when/why/result/hash`. Immutable `sealed_hash` on inspections/manifests.
*   **Secrets:** `DATABASE_URL`, `JWT_SECRET` env only, `requirements-data.txt` no secrets, `.env` not committed.

## 4. Dataset Row Counts by Role Use

*   Beneficiary: reads `beneficiaries_master` (own row), `intent_signals` (own 1-2 intents), `epos_transactions` (own history)
*   FPS Owner: reads `fps_master` (own 1), `dispatch_manifests/items` (own stops), `inventory` (own FPS), `epos` (own FPS transactions)
*   DSO: reads all 83k rows aggregated, writes locks/allocations/manifests
*   Inspector: reads `inspections` (own), `exceptions`, `deliveries` for target FPS
*   Auditor: reads full trace chain, writes `audit_events` findings
*   Admin: reads `dataset_manifest.json`, `data_quality_report.csv`

## 5. Test Accounts (Synthetic)

```
ADMIN: OFF-00671 / password: admin123 (synthetic)
DSO:   OFF-00001 / dso123
INSPECTOR: OFF-00007 / insp123
FPS_OWNER: OFF-06001 (FPS-0001 owner) / fps123
BENEFICIARY: BEN-000001 (RC202300100000) / ben123
AUDITOR: OFF-00668 / audit123
```
All synthetic, safe phones `90000xxxxx`.

# BCS-E Care Gap Knowledge Graph — Project Guide

## What This Project Does

This project builds a **Neo4j knowledge graph** for the **BCS-E (Breast Cancer Screening)** HEDIS measure.

It takes member, provider, claims, and enrollment data from an Excel file and:
1. Models every real-world clinical scenario as a **Persona node** (51 realistic combinations)
2. Loads all real member/provider/claims data into the graph
3. Runs a **guideline-accurate care gap engine** that evaluates each member and assigns a gap status
4. Links each member to their matching Persona and CareGap node
5. Exposes a **REST API** for real-time care gap prediction on any member

---

## Project Structure

```
Caregap_knowledge_graph/
│
├── Scenario 2_care_gap_multi_measure_dataset.xlsx  ← Source data (Excel)
│
├── build_full_graph.py         ← MAIN SCRIPT — builds entire graph in one run
├── api.py                      ← Flask REST API for care gap prediction
├── care_gap_engine.py          ← Standalone engine — runs gap evaluation on graph members
│
├── bcs_all_combinations.py     ← 51 realistic persona builder (standalone)
├── bcs_personas.py             ← Persona definitions and Neo4j loader
├── bcs_all_combinations.json   ← Auto-generated JSON snapshot of 51 personas
│
├── check_graph.py              ← Utility: verify node/relationship counts in Neo4j
├── explore_data.py             ← Utility: inspect Excel sheets (columns + sample rows)
│
├── BCS.pdf                     ← HEDIS BCS-E official guidelines reference
├── BCS_CareGap_API.postman_collection.json  ← Postman collection for API testing
├── requirements.txt            ← Python dependencies
└── .env                        ← Neo4j connection + measurement year config (not committed)
```

---

## What `build_full_graph.py` Does (Step by Step)

### 1. Constraints
Creates uniqueness constraints in Neo4j for all node types so `MERGE` operations are safe and fast.

### 2. Clear Old Personas
Runs `MATCH (p:Persona) DETACH DELETE p` to wipe stale personas before reloading fresh ones.

### 3. Measure Node
Creates/updates the single `BCS-E` Measure node with metadata: eligible age range (42–74), eligible gender (Female), lookback window (Oct 1 two years prior → Dec 31 of measurement year).

### 4. ComplianceCode Nodes
Creates one `ComplianceCode` node per mammography CPT code (77061–77067) and links each to the Measure node via `HAS_COMPLIANCE_CODE`.

### 5. ExclusionCode Nodes
Creates `ExclusionCode` nodes for all CPT, ICD-10-CM, and ICD-10-PCS codes that trigger exclusions, linked to the Measure via `HAS_EXCLUSION_CODE`.

### 6. 51 Realistic Persona Nodes
Generates every **clinically valid** combination — replacing the old 3,072 brute-force boolean model:

| Category | Count | Logic |
|---|---|---|
| NOT_ELIGIBLE | 3 | Gender not Female / Age outside 42–74 / Not enrolled |
| COMPLIANT / OPEN_GAP | 12 | 3 GC × 2 age bands × 2 mammogram states |
| EXCLUDED (age 42–65) | 15 | 3 GC × 5 exclusions (no frailty/SNP for under 66) |
| EXCLUDED (age 66–74) | 21 | 3 GC × 7 exclusions |
| **Total** | **51** | |

Each persona gets a `care_gap_status`: `NOT_ELIGIBLE`, `COMPLIANT`, `OPEN_GAP`, or `EXCLUDED`.

Also saved to `bcs_all_combinations.json`.

### 7. BenefitPlan Node
Loads plan data (copay, deductible, eligibility rules) from the `BenefitPlan` sheet.

### 8. Provider Nodes
Loads each provider with specialty, facility type, network status, and location.

### 9. Member Nodes + HAS_PCP
Loads each member with DOB, gender, ZIP, enrollment dates, and age. Creates `Member -[:HAS_PCP]-> Provider` relationship.

### 10. Enrollment Nodes
Creates `Enrollment` nodes linking members to their benefit plan:
`Member -[:HAS_ENROLLMENT]-> Enrollment -[:UNDER_PLAN]-> BenefitPlan`

### 11. Claim Nodes
Loads each claim with CPT code, ICD code, service date, and status. Tags each claim with `bcs_compliant` and `bcs_exclusion` booleans. Creates:
- `Member -[:HAS_CLAIM]-> Claim`
- `Claim -[:SERVICED_BY]-> Provider`

### 12. CareGap Nodes (Guideline-Accurate Engine)
For each member, runs the gap evaluation with full HEDIS accuracy:
1. **Gender criteria waterfall** — GC1 (Admin) → GC2 (Birth Sex) → GC3 (Clinical Use)
2. **Age check** — 42–74 as of Dec 31 of measurement year
3. **Exclusion check** — priority-based, date-sensitive, with unilateral side/14-day logic
4. **Mammogram compliance** — CPT 77061–77067 within lookback window
5. **Assign status** — `EXCLUDED` / `COMPLIANT` / `OPEN_GAP` / `NOT_ELIGIBLE`
6. **Write relationships**:
   - `Member -[:HAS_CARE_GAP]-> CareGap`
   - `CareGap -[:FOR_MEASURE]-> Measure`
   - `Member -[:MATCHES_PERSONA]-> Persona`

### 13. Outreach Nodes
Loads outreach activity from `CareMngnt_Outreach_Dashboard` sheet:
- `Outreach -[:FOR_CARE_GAP]-> CareGap`
- `Outreach -[:OUTREACH_TO]-> Member`

---

## Graph Schema (Node Types & Relationships)

```
Measure
  └─[:HAS_COMPLIANCE_CODE]──► ComplianceCode
  └─[:HAS_EXCLUSION_CODE]───► ExclusionCode

Persona ──[:BELONGS_TO_MEASURE]──► Measure

Member ──[:HAS_PCP]──────────────► Provider
Member ──[:HAS_ENROLLMENT]───────► Enrollment ──[:UNDER_PLAN]──► BenefitPlan
Member ──[:HAS_CLAIM]────────────► Claim ──────[:SERVICED_BY]──► Provider
Member ──[:HAS_CARE_GAP]─────────► CareGap ───[:FOR_MEASURE]──► Measure
Member ──[:MATCHES_PERSONA]──────► Persona

Outreach ──[:FOR_CARE_GAP]───────► CareGap
Outreach ──[:OUTREACH_TO]────────► Member
```

---

## REST API (`api.py`)

Start the API:
```bash
python api.py
```
Runs on `http://127.0.0.1:5000`

### Endpoint 1 — Predict (external member data)
`POST /care-gap/bcs/predict`

Evaluates any member you send — does not require them to be in the graph.

```json
{
  "member_id": "M999",
  "admin_gender": "F",
  "birth_sex": "",
  "clinical_use_gender": "",
  "age": 55,
  "enrollment_start": "2024-10-01",
  "enrollment_end": "2026-12-31",
  "claims": [
    { "cpt_code": "77067", "icd_code": "", "service_date": "2025-06-15", "status": "paid" }
  ],
  "save": false
}
```

Set `"save": true` to persist the member, claims, and CareGap node into Neo4j.

### Endpoint 2 — Check (member already in graph)
`POST /care-gap/bcs`

Looks up a member already loaded in Neo4j and evaluates their care gap.

```json
{
  "member_id": "M001"
}
```

### Response Fields

| Field | Description |
|---|---|
| `care_gap_status` | `OPEN_GAP` / `COMPLIANT` / `EXCLUDED` / `NOT_ELIGIBLE` |
| `gender_criteria` | Which GC qualified the member (GC1 / GC2 / GC3) |
| `persona_id` | Matched persona from the 51 realistic personas |
| `exclusion_reason` | Reason if EXCLUDED (e.g. `bilateral_mastectomy`) |
| `compliant_mammogram` | CPT code + date of qualifying mammogram if COMPLIANT |
| `recommendation` | Outreach message if OPEN_GAP |
| `lookback_window` | Start and end dates of the compliance window |

---

## Key Business Rules (BCS-E)

| Rule | Detail |
|---|---|
| Eligible gender | Female via GC1 (Admin), GC2 (Birth Sex), or GC3 (Clinical Use) — priority waterfall |
| Eligible age | 42–74 years old as of Dec 31 of measurement year |
| Compliance window | Oct 1 two years prior through Dec 31 of measurement year |
| Mammography CPT codes | 77061, 77062, 77063, 77065, 77066, 77067 |
| Exclusion: bilateral mastectomy | ICD-10-PCS: 0HTV0ZZ / ICD-10-CM: Z90.13 — any time through Dec 31 MY |
| Exclusion: unilateral mastectomy (both sides) | CPT: 19180–19307 with modifier LT+RT or 50 / ICD-10-CM: Z90.11+Z90.12 / 14-day rule for no-side claims |
| Exclusion: gender-affirming chest surgery | CPT 19318 + gender dysphoria ICD (F64.1, F64.2, F64.8, F64.9, Z87.890) — both required |
| Exclusion: hospice / palliative / deceased | Must occur during measurement year only |
| Exclusion: frailty + advanced illness | Age 66+ only |
| Exclusion: institutional SNP / LTC | Age 66+ only |

### Exclusion Priority (highest first)
1. Deceased
2. Hospice / Palliative
3. Bilateral mastectomy
4. Unilateral mastectomy (both sides)
5. Gender-affirming chest surgery
6. Frailty + advanced illness *(66+ only)*
7. Institutional SNP / LTC *(66+ only)*

---

## Care Gap Statuses

| Status | Meaning |
|---|---|
| `OPEN_GAP` | Eligible, enrolled, no exclusion, no mammogram found — needs outreach |
| `COMPLIANT` | Eligible, enrolled, mammogram CPT found within lookback window |
| `EXCLUDED` | Meets an exclusion criterion — removed from measure denominator |
| `NOT_ELIGIBLE` | Gender not Female, age outside 42–74, or enrollment gap |

---

## Setup & Run

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure `.env`
```
NEO4J_URI=neo4j+ssc://your-instance.databases.neo4j.io
NEO4J_USERNAME=your_username
NEO4J_PASSWORD=your_password
NEO4J_DATABASE=your_database
MEASUREMENT_YEAR=2026
```

> `MEASUREMENT_YEAR` controls all date windows. Update to `2027` when the 2026 HEDIS audit cycle closes. If not set, defaults to the current calendar year.

### 3. Run the full graph builder
```bash
python build_full_graph.py
```

### 4. Start the API
```bash
python api.py
```

### 5. Verify the graph
```bash
python check_graph.py
```

---

## Utility Scripts

| Script | Purpose |
|---|---|
| `explore_data.py` | Print all Excel sheet names, columns, and sample rows |
| `check_graph.py` | Connect to Neo4j and print node/relationship counts |
| `care_gap_engine.py` | Run gap evaluation directly on all members already in the graph |
| `bcs_all_combinations.py` | Standalone: build and load 51 personas independently |

---

## Persona Model — 51 Realistic Combinations

The old model generated 3,072 personas using brute-force boolean combinations (2⁷ exclusion flags). The new model generates exactly 51 clinically valid personas — one per real-world scenario a member can actually be in.

| Old Model | New Model |
|---|---|
| 3,072 personas | 51 personas |
| 7 boolean exclusion flags (128 combos) | Single exclusion enum (priority-based) |
| Frailty/SNP applied to all ages | Frailty/SNP restricted to age 66+ |
| Single gender field check | 3 GC priority waterfall (GC1 → GC2 → GC3) |
| No unilateral side logic | Left + Right side detection + 14-day rule |
| No date check on exclusions | Hospice/deceased checked against measurement year |
| Matched on boolean flags | Matched on semantic fields (status, exclusion_reason, mammogram_found) |

---

## Data Source

**`Scenario 2_care_gap_multi_measure_dataset.xlsx`** — contains these sheets:

| Sheet | Contents |
|---|---|
| Members | MemberID, Name, DOB, Gender, ZIP, EnrollmentStart, EnrollmentEnd, Member Age, PCPID |
| Providers | ProviderID, Name, Specialty, FacilityType, NetworkStatus, Location |
| Claims | ClaimID, MemberID, ProviderID, CPTCode, ICDCode, ServiceDate, Status |
| Enrolment Eligibility | MemberID, PlanID, PCPID, EffectiveFrom, EffectiveTo |
| BenefitPlan | PlanID, PreventiveServicesCovered, Copay, Deductible, EligibilityRules |
| CareMngnt_Outreach_Dashboard | OutreachID, CareGapID, MemberID, CareManagerID, Channel, Date, Status |

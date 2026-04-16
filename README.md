<<<<<<< HEAD
# BCS-E Care Gap Knowledge Graph — Project Guide

## What This Project Does

This project builds a **Neo4j knowledge graph** for the **BCS-E (Breast Cancer Screening)** HEDIS measure.

It takes member, provider, claims, and enrollment data from an Excel file and:
1. Models every possible clinical scenario as a **Persona node** (3,072 combinations)
2. Loads all real member/provider/claims data into the graph
3. Runs a **care gap engine** that evaluates each member and assigns a gap status
4. Links each member to their matching Persona and CareGap node

---

## Project Structure

```
Caregap_knowledge_graph/
│
├── Scenario 2_care_gap_multi_measure_dataset.xlsx   ← Source data (Excel)
│
├── build_full_graph.py      ← MAIN SCRIPT — does everything in one run
│
├── explore_data.py          ← Utility: inspect Excel sheets (columns + sample rows)
├── check_graph.py           ← Utility: verify node/relationship counts in Neo4j
├── bcs_all_combinations.json← Auto-generated JSON snapshot of all 3,072 personas
├── requirements.txt         ← Python dependencies
└── .env                     ← Neo4j connection credentials (not committed)
```

---

## What `build_full_graph.py` Does (Step by Step)

### 1. Constraints
Creates uniqueness constraints in Neo4j for all node types so `MERGE` operations are safe and fast.

### 2. Clear Old Personas
Runs `MATCH (p:Persona) DETACH DELETE p` to wipe any previously loaded personas before reloading fresh ones.

### 3. Measure Node
Creates/updates the single `BCS-E` Measure node with metadata: eligible age range (42–74), eligible gender (Female), lookback window (Oct 1, 2 years prior → Dec 31 of measurement year).

### 4. ComplianceCode Nodes (CPT only)
Creates one `ComplianceCode` node per mammography CPT code (77061–77067) and links each to the Measure node via `HAS_COMPLIANCE_CODE`.

### 5. ExclusionCode Nodes
Creates `ExclusionCode` nodes for all CPT, ICD-10-CM, and ICD-10-PCS codes that trigger exclusions, linked to the Measure via `HAS_EXCLUSION_CODE`.

### 6. All 3,072 Persona Nodes
Generates every combination of:
- 3 gender criteria (GC1, GC2, GC3)
- 2 age bands (AB1: 42–65, AB2: 66–74)
- Enrolled: True/False
- Mammogram via CPT: True/False
- 7 exclusion flags × True/False = 128 combos

Formula: `3 × 2 × 2 × 2 × 128 = 3,072`

Each persona gets a `care_gap_status` derived from business logic:
- Not enrolled → `NOT_ELIGIBLE`
- Any exclusion flag True → `EXCLUDED`
- Enrolled + mammogram CPT → `COMPLIANT`
- Enrolled + no mammogram → `OPEN_GAP`

Loaded in batches of 500. Also saved to `bcs_all_combinations.json`.

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

### 12. CareGap Nodes (Engine Logic)
For each member, runs the gap evaluation inline:
1. Check gender = Female → else `NOT_ELIGIBLE`
2. Check age 42–74 → else `NOT_ELIGIBLE`
3. Scan claims for exclusion CPT/ICD codes
4. Scan claims for mammography CPT in lookback window (Oct 1, 2024 – Dec 31, 2026)
5. Assign status: `EXCLUDED` / `COMPLIANT` / `OPEN_GAP`
6. Write `CareGap` node and relationships:
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

## Key Business Rules (BCS-E)

| Rule | Detail |
|---|---|
| Eligible gender | Female (Administrative, Birth, or Clinical Use) |
| Eligible age | 42–74 years old |
| Compliance window | Oct 1 two years prior through Dec 31 of measurement year |
| Mammography CPT codes | 77061, 77062, 77063, 77065, 77066, 77067 |
| Exclusion: bilateral mastectomy | ICD-10-PCS: 0HTV0ZZ / ICD-10-CM: Z90.13 |
| Exclusion: unilateral mastectomy (both sides) | CPT: 19180–19307 / ICD-10-CM: Z90.11, Z90.12 / ICD-10-PCS: 0HTU0ZZ, 0HTT0ZZ |
| Exclusion: gender-affirming chest surgery | CPT: 19318 / ICD-10-CM: F64.1, F64.2, F64.8, F64.9, Z87.890 |
| Other exclusions (modeled in personas) | Hospice/palliative, frailty+advanced illness, deceased, institutional SNP/LTC (age 66+) |

---

## Care Gap Statuses

| Status | Meaning |
|---|---|
| `OPEN_GAP` | Eligible, enrolled, no exclusion, no mammogram found — needs outreach |
| `COMPLIANT` | Eligible, enrolled, mammogram CPT found within lookback window |
| `EXCLUDED` | Meets an exclusion criterion — removed from measure denominator |
| `NOT_ELIGIBLE` | Gender not Female or age outside 42–74 |

---

## Setup & Run

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure `.env`
```
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=<your_password>
NEO4J_DATABASE=neo4j
```

### 3. Run the full graph builder
```bash
python build_full_graph.py
```

### 4. Verify the graph
```bash
python check_graph.py
```

---

## Utility Scripts

| Script | Purpose |
|---|---|
| `explore_data.py` | Print all Excel sheet names, columns, and sample rows |
| `check_graph.py` | Connect to Neo4j and print node/relationship counts |

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
=======
# Care_gap_using_knowledge_graph
>>>>>>> 72e97b2651f2fda09f7475baac2149607f4ae994

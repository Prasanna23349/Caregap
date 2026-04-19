# BCS Care Gap Knowledge Graph Engine

## Overview

A **HEDIS BCS-E compliant care gap detection engine** built on **Neo4j Knowledge Graph** for Breast Cancer Screening (Hopkins Health Plans). The system automatically identifies screening gaps, matches members to clinical personas, generates personalized outreach recommendations, and tracks gap closure — all aligned to the Hopkins HEDIS BCS-E rulebook.

---

## Measurement Parameters

| Parameter | Value |
|---|---|
| Measure | BCS-E (Breast Cancer Screening — Extended) |
| Measurement Year | 2026 |
| Eligible Age Range | 42–74 years (as of Dec 31, 2026) |
| Lookback Age Minimum | 40 years (at time of mammogram) |
| Lookback Window | Oct 1, 2024 → Dec 31, 2026 (27 months) |
| Proactive Window | Jun 1, 2025 → Dec 31, 2026 (18 months from end) |
| Valid CPT Codes | 77067, 77066, 77065, 77062, 77061 |
| Standalone 77063 | ❌ Not accepted alone |
| MRI / Ultrasound / Biopsy | ❌ Not accepted for compliance |
| CAD alone | ❌ Not accepted |
| Gender | Female only (administrative + sex assigned at birth) |

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                  NEO4J KNOWLEDGE GRAPH                  │
│                                                         │
│  ┌──────────────────────┐   ┌────────────────────────┐  │
│  │   MEMBER SUBGRAPH    │   │  PERSONA RULEBOOK      │  │
│  │   (30 members)       │   │  (51 IdealPersonas)    │  │
│  │                      │   │                        │  │
│  │  Member              │   │  IdealPersona          │  │
│  │  ├─ Demographics     │   │  ├─ AgeRuleCheck       │  │
│  │  ├─ Enrollment       │   │  ├─ EnrollmentProfile  │  │
│  │  ├─ AgeRuleCheck     │   │  ├─ ScreeningProfile   │  │
│  │  ├─ ExclusionProfile │   │  ├─ RiskProfile        │  │
│  │  ├─ ScreeningHistory │   │  ├─ ComorbidityProfile │  │
│  │  ├─ ClinicalHistory  │   │  ├─ ExclusionProfile   │  │
│  │  ├─ Vitals           │   │  ├─ EngagementProfile  │  │
│  │  ├─ SDOH             │   │  └─ CareGapOutput      │  │
│  │  ├─ Consent          │   │                        │  │
│  │  ├─ CareGap          │   │  ISOLATED SUBGRAPH     │  │
│  │  ├─ Claim            │   │  No direct links to    │  │
│  │  ├─ Outreach         │   │  member nodes          │  │
│  │  └─ CareGapRec.      │   └────────────────────────┘  │
│  └──────────┬───────────┘              ▲                 │
│             │    MATCHED_TO ───────────┘                 │
│             │    (Python comparison — no DB relationship)│
└─────────────────────────────────────────────────────────┘
```

**Design Principle:** The persona rulebook is **strictly isolated** — member nodes never form database relationships with persona nodes. Comparison happens in Python, and only the output (recommendations) is written back to the member's `CareGap` node.

---

## Project File Structure

```
Care_gap_using_knowledge_graph/
│
├── .env                         # Neo4j credentials (NEO4J_URI, USERNAME, PASSWORD)
├── requirements.txt             # Python dependencies
├── BCS.pdf                      # Hopkins BCS-E HEDIS source guidelines
│
├── schema.py                    # Node labels, properties, constraints, relationship definitions
├── graph_builder.py             # General-purpose graph building utilities
│
├── bcs_personas.py              # 51 IdealPersona definitions (9-node structure each)
├── persona_graph_builder.py     # Loads all 51 personas into Neo4j as isolated subgraph
│
├── bcs_step1_neo4j_load.cypher  # Cypher: Load 30 members, providers, plans, claims
├── bcs_step1_runner.py          # Python runner that executes the Step 1 Cypher file
├── bcs_cleanup_old_seeds.py     # Removes old seed members (MBR-*) from prior sessions
│
├── bcs_step2_matching.py        # Step 2 — Matching algorithm (member → best persona)
├── bcs_step3_inherit.py         # Step 3 — Inherits persona outputs → CareGapRecommendation
├── bcs_step4_hedis_validate.py  # 10 HEDIS compliance validation checks
├── bcs_step5_outreach.py        # Creates Outreach nodes with care manager assignment
├── bcs_step6_analytics.py       # Step 6 — Population analytics: compliance rate, risk tiers, outreach channels
├── bcs_step7_closure.py         # Step 7 — Gap closure tracking, claim validation, re-screening flags
│
├── bcs_check_member.py          # Interactive single-member gap checker (instant eligibility + persona match)
├── bcs_logger.py                # Centralized logger — color console + rotating log file
│
├── activate_venv.bat            # Virtual environment activation script
└── README.md                    # This file
```

---

## The Persona Rulebook — 51 IdealPersonas

The rulebook is an isolated subgraph of **51 clinically validated personas** covering every meaningful BCS patient type. Each persona has exactly **9 nodes**:

| Node | Purpose |
|---|---|
| `IdealPersona` | Root — persona ID, name, group |
| `AgeRuleCheck` | Eligibility age check, lookback age check, SNP/LTC flag |
| `EnrollmentProfile` | Continuous enrollment, gap presence |
| `ScreeningProfile` | Mammogram status, CPT validity, window compliance |
| `RiskProfile` | BRCA, family history, dense breast, HRT, BMI, biopsy |
| `ComorbidityProfile` | Comorbidities, mental health conditions |
| `ExclusionProfile` | Bilateral mastectomy, hospice, frailty, gender-affirming surgery |
| `EngagementProfile` | Engagement level, barriers, transportation, preferred contact |
| `CareGapOutput` | Gap status, priority, risk tier, screening type, actions, channel, escalation |

### Persona Groups

| Group | Personas | Count | Description |
|---|---|---|---|
| 1 | P-001 – P-005 | 5 | **Excluded** — bilateral mastectomy, hospice, frailty, gender surgery, Medicare SNP/LTC |
| 2 | P-006 – P-008 | 3 | **Not Eligible** — wrong age, wrong gender, enrollment gap |
| 3 | P-009 – P-012 | 4 | **Never Screened** — very high → low risk |
| 4 | P-013 – P-018 | 6 | **Overdue — Very High Risk** — BRCA+, HRT, dense breast D, atypical hyperplasia |
| 5 | P-019 – P-024 | 6 | **Overdue — High Risk** — family history, dense breast C, lifestyle risks |
| 6 | P-025 – P-028 | 4 | **Overdue — Medium Risk** — transportation, mental health, language barrier |
| 7 | P-029 – P-032 | 4 | **Overdue — Low Risk** — cost concern, forgot, unverified self-report, OON claim |
| 8 | P-033 – P-040 | 8 | **Proactive Window** — approaching 18-month mark, action before gap opens |
| 9 | P-041 – P-048 | 8 | **Compliant** — valid screening, false compliant cases (CAD only, CPT billing errors) |
| 10 | P-049 – P-051 | 3 | **Edge Cases** — age 40 lookback rule, age 39 rejection, bilateral mastectomy 14-day rule |

---

## 7-Step Pipeline

### Step 1 — Load 30 Members
**File:** `bcs_step1_runner.py` → executes `bcs_step1_neo4j_load.cypher`

Loads all 30 members from the dataset into Neo4j. Eligible females (age 42–74) get a **full 20-node subgraph**. Males and ineligible members get minimal nodes with a `NOT ELIGIBLE` CareGap.

**Node structure per eligible female member (20 nodes):**
```
Member → Demographics → Enrollment → AgeRuleCheck → ExclusionProfile
       → ScreeningHistory → ClinicalHistory → Vitals → SDOH → Consent
       → CareGap → Claim(s) → Provider → BenefitPlan → QualityMeasure
       → Outreach → CareGapRecommendation → CareManager
```

**Result:** 30 members loaded | 17 NOT ELIGIBLE | 9 OPEN | 4 CLOSED

---

### Step 2 — Matching Algorithm
**File:** `bcs_step2_matching.py`

Compares each member against all 51 IdealPersonas using a **4-layer weighted scoring function**:

```
Layer 1 — Group Classification  (10 pts mandatory gate)
  Excluded | Not Eligible | Never Screened | Overdue | Proactive | Compliant

Layer 2 — Screening Profile     (3 pts)
  Mammogram status, CPT code, window compliance, HEDIS validity

Layer 3 — Risk Profile          (5 pts, PENDING = 0.3 partial credit)
  BRCA, family history, dense breast, HRT, BMI, prior biopsy

Layer 4 — Engagement / SDOH    (2 pts)
  Transportation, language, fear barrier, preferred contact method
```

**Writes:** `MATCHED_TO` relationship between Member and IdealPersona with match score.

**Result:** 30/30 members matched | All OPEN members → P-009 (conservative default — clinical data PENDING)

---

### Step 3 — Inherit Care Gap Outputs
**File:** `bcs_step3_inherit.py`

Pulls the full `CareGapOutput` node from each matched persona and writes a `CareGapRecommendation` node per member containing:

- Priority level (VERY HIGH / HIGH / MEDIUM / LOW)
- Risk category and risk flags (BRCA+, family history, etc.)
- Recommended screening type (2D / 3D / MRI)
- Ordered action list (e.g. "Urgent phone outreach", "Alert PCP + OB-GYN")
- Outreach channel (Phone urgent / SMS / Mail)
- Escalation path (Care Manager → PCP → OB-GYN → Oncologist)
- Follow-up days (7 / 14 / 21 / 30 / 45 / 60)

**Result:** 12 `CareGapRecommendation` nodes created and linked to members.

---

### Step 4 — HEDIS Validation
**File:** `bcs_step4_hedis_validate.py`

Runs **10 compliance checks** before generating outreach:

| # | Check | Result |
|---|---|---|
| 1 | All 30 members have a BCS CareGap | ✅ PASS |
| 2 | No male member has OPEN/CLOSED gap | ✅ PASS |
| 3 | No female under 42 has OPEN gap | ✅ PASS |
| 4 | No female over 74 has OPEN gap | ✅ PASS |
| 5 | Every CLOSED gap backed by valid in-window mammogram | ✅ PASS |
| 6 | M0011 (age 39 at mammogram) correctly OPEN | ✅ PASS |
| 7 | M0016 (age 28, CLOSED) flagged as data anomaly | ✅ PASS |
| 8 | All eligible OPEN females matched to a persona | ✅ PASS |
| 9 | No standalone CPT 77063 closes a BCS gap | ✅ PASS |
| 10 | Every OPEN gap member has a CareGapRecommendation | ✅ PASS |

**Result: 10/10 PASS ✅**

---

### Step 5 — Outreach Workflow
**File:** `bcs_step5_outreach.py`

Creates `Outreach` nodes for every OPEN gap member with:
- Channel (Phone urgent / SMS / Mail — inherited from persona)
- Outreach date and follow-up date (today + followUpDays)
- Care manager assignment (by priority tier)
- Links: `CareGap → TRIGGERED_OUTREACH → Outreach → PERFORMED_BY → CareManager`

**Care Manager Tier Assignment:**
| Priority | Care Manager |
|---|---|
| VERY HIGH | CM-101 |
| HIGH | CM-102 |
| MEDIUM | CM-103 |
| LOW | CM-104 |

**Result:** 8 outreach records created | All 8 OPEN gap members assigned | Follow-up: 2026-04-27

---

### Step 6 — Population Analytics
**File:** `bcs_step6_analytics.py`

Generates 8 population-level quality metrics:

1. **Gap Status Distribution** — NOT ELIGIBLE 56.7% | OPEN 26.7% | CLOSED 16.7%
2. **BCS Compliance Rate** — 4/12 eligible females = **33.3%** | Gap Rate = **66.7%**
3. **Age Band Distribution** — Older members (61–74) have 0% compliance
4. **Persona Match Distribution** — P-009 (8 members), P-048 (3), P-013 (1)
5. **Risk Category Breakdown** — All OPEN = Very High (due to PENDING clinical data)
6. **Outreach Channel Distribution** — Phone (urgent): 8 members
7. **Data Completeness** — 8/8 OPEN members missing EHR clinical data
8. **Urgent Action List** — All 8 OPEN members require ≤ 7-day follow-up

---

### Step 7 — Gap Closure Tracking
**File:** `bcs_step7_closure.py`

Implements the mechanism to close gaps and track re-screening:

**Claim Validation Rules:**
```python
valid_cpt    = {77067, 77066, 77065, 77062, 77061}  # 77063 standalone ❌
window_start = 2024-10-01
window_end   = 2026-12-31
lookback_age_min = 40  # member must be ≥ 40 at time of mammogram
```

**Closure Process:**
1. New mammogram claim arrives → validate CPT + date + age
2. If valid → SET `CareGap.gapStatus = 'CLOSED'`, log claim ID and date
3. Update outreach outcome → `'Gap Closed'`
4. Flag members approaching 24-month re-screening window

**Proactive Re-Screening Flags:**
- Members with CLOSED gaps are monitored for their next 24-month cycle
- Alert triggered at 18 months (6 months before gap re-opens)

---

## Running the Pipeline

> **Prerequisites:** Neo4j running locally, Python venv active, `.env` with credentials

```bash
# Activate environment
.\activate_venv.bat

# Step 0: Load persona rulebook (run once)
python persona_graph_builder.py

# Step 1: Load 30 members
python bcs_step1_runner.py

# Cleanup (if re-running after previous session)
python bcs_cleanup_old_seeds.py

# Steps 2–7: Run sequentially
python bcs_step2_matching.py
python bcs_step3_inherit.py
python bcs_step4_hedis_validate.py
python bcs_step5_outreach.py
python bcs_step6_analytics.py
python bcs_step7_closure.py
```

### Re-run after EHR enrichment
When clinical data (BRCA, BMI, family history) is available from EHR:
1. Update `ClinicalHistory`, `Vitals`, `SDOH` nodes for each member
2. Re-run `bcs_step2_matching.py` — members will redistribute to specific personas
3. Re-run `bcs_step3_inherit.py` → updated recommendations
4. Re-run `bcs_step5_outreach.py` → updated outreach channels and priorities

---

## Known Issues & Limitations

| Issue | Detail |
|---|---|
| **Clinical data PENDING** | All 8 OPEN members default to P-009 (Very High Risk). After EHR enrichment, re-run Step 2. |
| **M0016 data anomaly** | Taylor Lopez (age 28) has CLOSED gap — below eligibility age. Flagged in Step 4. |
| **M0011 edge case** | Quinn Iyer — mammogram at age 39 (below 40 lookback minimum) + outside window. Correctly OPEN. |
| **Older members (61–74)** | 0% compliance in 61–74 age band — highest priority group for outreach. |
| **Persona rulebook size** | Shows 50 in Neo4j instead of 51 — one persona may have a duplicate ID. Run `persona_graph_builder.py` to recheck. |

---

## Neo4j Verification Queries

```cypher
// Count all members
MATCH (m:Member) RETURN count(m) AS totalMembers;

// BCS compliance rate (eligible females)
MATCH (m:Member)-[:HAS_DEMOGRAPHICS]->(d:Demographics)
MATCH (m)-[:HAS_CARE_GAP]->(cg:CareGap {measureID:'BCS'})
WHERE d.administrativeGender = 'Female' AND d.age >= 42 AND d.age <= 74
RETURN cg.gapStatus, count(m) ORDER BY count(m) DESC;

// OPEN gap members with their matched persona
MATCH (m:Member)-[:HAS_CARE_GAP]->(cg:CareGap {measureID:'BCS', gapStatus:'OPEN'})
MATCH (m)-[:MATCHED_TO]->(p:IdealPersona)
MATCH (m)-[:HAS_DEMOGRAPHICS]->(d:Demographics)
RETURN m.memberID, m.fullName, d.age, p.personaID, p.group
ORDER BY d.age DESC;

// All outreach records pending
MATCH (m:Member)-[:HAS_OUTREACH]->(o:Outreach {outreachStatus:'Pending'})
MATCH (o)-[:PERFORMED_BY]->(cm:CareManager)
RETURN m.memberID, m.fullName, o.channel, o.followUpDate, cm.careManagerID
ORDER BY o.followUpDate;

// View all 51 personas in rulebook
MATCH (p:IdealPersona) RETURN p.personaID, p.personaName, p.group
ORDER BY p.personaID;
```

---

## Environment Setup

```bash
# .env file required
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_password

# Dependencies (installed in .venv)
neo4j
python-dotenv
```

---

## Changelog

> All future changes to this project must be documented here.

| Date | Version | Change | Author |
|---|---|---|---|
| 2026-04-19 | v1.0 | Initial schema design — 20-node member structure + 51 persona rulebook (9-node each) | Dev |
| 2026-04-19 | v1.0 | `bcs_personas.py` — All 51 personas built across 10 groups per Hopkins BCS-E guidelines | Dev |
| 2026-04-19 | v1.0 | `persona_graph_builder.py` — Isolated persona subgraph loaded into Neo4j (459 nodes, 408 relationships) | Dev |
| 2026-04-19 | v1.0 | `bcs_step1_neo4j_load.cypher` — 30 members loaded (M0001–M0030), 18 providers, BenefitPlan, QualityMeasure | Dev |
| 2026-04-19 | v1.0 | `bcs_step2_matching.py` — 4-layer scoring algorithm, 30/30 members matched to IdealPersonas | Dev |
| 2026-04-19 | v1.0 | `bcs_step3_inherit.py` — 12 CareGapRecommendation nodes created with full clinical outputs | Dev |
| 2026-04-19 | v1.0 | `bcs_step4_hedis_validate.py` — 10/10 HEDIS validation checks passed | Dev |
| 2026-04-19 | v1.0 | `bcs_step5_outreach.py` — 8 outreach records created, care manager assigned, follow-up scheduled | Dev |
| 2026-04-19 | v1.0 | `bcs_step6_analytics.py` — Population analytics: 33.3% compliance rate, 66.7% gap rate | Dev |
| 2026-04-19 | v1.0 | `bcs_step7_closure.py` — Gap closure tracking with claim validation and re-screening flags | Dev |
| 2026-04-20 | v1.1 | Cleanup — removed legacy files: `bcs_engine.py`, `bcs_rulebook_graph.py`, `seed_data.py`, `rewrite_seed_data.py`, `rewrite_seed_data2.py`, `fix_seed_data.py`, `test_engine.py`, `app.py`, `bcs_step1_cleanup.py` | Dev |
| 2026-04-20 | v1.2 | Added `bcs_logger.py` — centralized logging with color console output (INFO/DEBUG/WARNING/ERROR), rotating file handler (`logs/bcs_pipeline.log`, 5MB × 3 backups), and step-level helpers (`log_step_start`, `log_step_end`, `log_member`, `log_validation`). Integrated into all 7 step files. | Dev |

---

*Hopkins BCS-E HEDIS Measure | Measurement Year 2026 | Knowledge Graph Engine v1.1*

# BCS Care Gap Knowledge Graph Engine

## 📖 Overview
The **BCS Care Gap Knowledge Graph Engine** is a **HEDIS BCS‑E compliant** solution that uses a **Neo4j Knowledge Graph** to detect breast‑cancer‑screening gaps, match members to clinically‑validated personas, generate personalized outreach recommendations, and track gap closure.  It demonstrates a modern data‑centric architecture for population‑health analytics.

---

## 🎯 Core Concepts
- **Dynamic Configuration** – Clinical rules (age ranges, look‑back windows, CPT codes, etc.) are stored in Neo4j `QualityMeasure` nodes and loaded at runtime via `bcs_config.py`. Adjusting a measure does **not** require code changes.
- **EHR & SDOH Enrichment** – Synthetic clinical and social‑determinant‑of‑health data replace placeholder values, providing realistic member profiles.
- **Persona Rulebook** – 51 `IdealPersona` definitions represent every meaningful BCS patient type. A weighted‑scoring algorithm matches members to these personas.
- **Automated HEDIS Validation** – A 10‑point checklist validates data integrity before outreach, ensuring compliance with the BCS‑E measure.

---

## 🏗️ Architecture
```text
┌─────────────────────────────────────────────────────────┐
│                  NEO4J KNOWLEDGE GRAPH                │
│                                                         │
│   ┌──────────────────────┐   ┌───────────────────────┐ │
│   │   MEMBER SUBGRAPH    │   │   PERSONA RULEBOOK    │ │
│   │   (≈30 members)     │   │   (51 IdealPersonas)   │ │
│   └─────────┬──────────┘   └─────────┬─────────────┘ │
│             │ MATCHED_TO               │               │
│             ▼                          ▼               │
│   ┌─────────────────────────────────────────────────┐ │
│   │            GAP ANALYTICS & OUTREACH           │ │
│   └─────────────────────────────────────────────────┘ │
└───────────────────────────────────────────────────────┘
```
- **Member Subgraph** – Holds member demographics, enrollment, claims, clinical history, vitals, and SDOH.
- **Persona Rulebook** – Isolated subgraph containing persona definitions and rule logic.
- **Gap Analytics & Outreach** – Matches members to personas, validates HEDIS compliance, creates `Outreach` nodes with personalized recommendations, and tracks closure status.

---

## 📂 Project File Structure
```
Care_gap_using_knowledge_graph/
│
├─ .env                         # Neo4j credentials
├─ requirements.txt             # Python dependencies
├─ BCS.pdf                     # HEDIS source guidelines
│
├─ bcs_config.py               # Dynamic configuration engine (loads QualityMeasure nodes)
├─ bcs_logger.py               # Centralised logger (colour console + rotating file)
├─ schema.py                   # Neo4j node labels, properties, constraints
│
├─ bcs_mock_ehr_data.json      # Synthetic EHR clinical data
├─ bcs_mock_sdoh_data.json     # Synthetic SDOH data
│
├─ bcs_personas.py            # 51 IdealPersona class definitions
├─ persona_graph_builder.py    # Loads persona subgraph into Neo4j
│
├─ bcs_step1_neo4j_load.cypher # Seed step – loads members, providers, plans
├─ bcs_step1_runner.py         # Executes the Step‑1 Cypher file
├─ bcs_ehr_ingestion.py        # Ingests EHR & SDOH data into the member subgraph
│
├─ bcs_step2_matching.py       # Weighted scoring and persona matching
├─ bcs_step3_inherit.py        # Propagates persona outputs to recommendation nodes
├─ bcs_step4_hedis_validate.py # 10‑point HEDIS compliance checks
├─ bcs_step5_outreach.py        # Generates Outreach nodes with personalized actions
├─ bcs_step6_analytics.py       # Population‑health analytics & reporting
├─ bcs_step7_closure.py         # Tracks gap‑closure events & updates status
│
├─ bcs_api.py                  # Flask API exposing metrics & member‑level endpoints
├─ bcs_check_member.py         # Interactive CLI for single‑member gap checking
│
├─ run_pipeline.bat            # End‑to‑end automation (wipe DB → run steps 1‑7)
├─ wipe_db.py                  # Utility to clean Neo4j for a fresh start
└─ README.md                   # **You are reading it now**
```

---

## ⚙️ Setup & Prerequisites
1. **Neo4j** – Install Neo4j Desktop or run a Neo4j Server (v5+). Create a database and note the bolt URL, username, and password.
2. **Python 3.10+** – Install the required packages:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```
3. **Environment File** – Copy `.env.example` to `.env` and fill in your Neo4j credentials:
   ```text
   NEO4J_URI=bolt://localhost:7687
   NEO4J_USER=neo4j
   NEO4J_PASSWORD=your_password
   ```
4. (Optional) **IDE** – Open the project in VS Code for easy navigation.

---

## ▶️ Running the Pipeline
Two ways are provided:
### Automated (Recommended)
```bat
# Executes wipe, load, enrichment, matching, validation, outreach, analytics
run_pipeline.bat
```
### Manual Step‑by‑Step
```bash
# 1. Clean the graph
python wipe_db.py

# 2. Load members & plans (Step 1)
python bcs_step1_runner.py

# 3. Load persona rulebook
python persona_graph_builder.py

# 4. Enrich members with EHR/SDOH data
python bcs_ehr_ingestion.py

# 5. Run matching & generate recommendations (Steps 2‑5)
python bcs_step2_matching.py
python bcs_step3_inherit.py
python bcs_step4_hedis_validate.py
python bcs_step5_outreach.py

# 6. Run analytics (Step 6)
python bcs_step6_analytics.py

# 7. Track closure events (Step 7)
python bcs_step7_closure.py
```
All scripts write progress to the console and log file `bcs_engine.log` (rotates daily).

---

## 🌐 API
The Flask API in `bcs_api.py` exposes two useful endpoints:
- `GET /metrics` – Returns population‑level statistics (e.g., % of members compliant, overdue, proactive).
- `GET /member/<member_id>` – Returns the gap status, matched persona, and outreach recommendations for a single member.
Run the API with:
```bash
python bcs_api.py
```
It will start on `http://127.0.0.1:5000` by default.

---

## 🧪 Testing & Validation
- **HEDIS Validation** – `bcs_step4_hedis_validate.py` runs ten checks and prints a PASS/FAIL table. A final summary is shown in the README under *HEDIS Validation Result*.
- **Unit Tests** – (If added) can be executed via `pytest tests/`.
- **Manual Spot‑Check** – Use `bcs_check_member.py` to query a specific member ID and view the computed gap and recommendations.

---

## 🔧 Extending the Engine
1. **Add New Measures** – Insert a new `QualityMeasure` node in Neo4j with the desired parameters. The engine will automatically pick it up via `bcs_config.py`.
2. **Create Additional Personas** – Define new `IdealPersona` objects in `bcs_personas.py` and re‑run `persona_graph_builder.py`.
3. **Custom Scoring** – Modify `bcs_step2_matching.py` to adjust weightings or introduce new attributes.
4. **Integrate Real Data** – Replace the synthetic JSON files with real EHR/SDOH extracts and adjust the ingestion logic accordingly.

---

## 📦 Changelog
| Date | Version | Change |
|---|---|---|
| 2026‑04‑26 | v1.3 | Added dynamic config (`bcs_config.py`), synthetic EHR/SDOH data, refactored steps, improved logging, and full pipeline automation (`run_pipeline.bat`). |
| 2026‑04‑20 | v1.2 | Introduced `bcs_logger.py` for centralised logging across all steps. |
| 2026‑04‑20 | v1.1 | Cleaned up legacy files and documentation. |
| 2026‑04‑19 | v1.0 | Initial release – 7‑step pipeline + 51‑persona rulebook. |

---

## 📜 License & Acknowledgements
This project is provided under the MIT License. The HEDIS BCS‑E measure specifications are sourced from the **Hopkins Health Plan** guidelines (see `BCS.pdf`).

---

*Hopkins BCS‑E HEDIS Measure | Knowledge Graph Engine v1.3 | 2026*

## 📖 Overview
The **BCS Care Gap Knowledge Graph Engine** is a **HEDIS BCS‑E compliant** solution that uses a **Neo4j Knowledge Graph** to detect breast cancer screening gaps, match members to clinically validated personas, generate personalized outreach recommendations, and track gap closure.

---

## 🎯 Key Concepts
- **Dynamic Configuration** – Clinical rules (age ranges, look‑back windows, CPT codes, etc.) are stored in Neo4j `QualityMeasure` nodes and loaded at runtime via `bcs_config.py`. No code changes are needed to adjust measures.
- **EHR & SDOH Enrichment** – Synthetic clinical and social determinants of health data replace placeholder values, giving a realistic member profile.
- **Persona Rulebook** – 51 `IdealPersona` definitions represent every meaningful BCS patient type. A weighted scoring algorithm matches members to these personas.
- **Automated Validation** – A 10‑point HEDIS‑compliance checklist verifies data integrity before outreach.

---

## 🏗️ Architecture
```
┌─────────────────────────────────────────────────────────┐
│                  NEO4J KNOWLEDGE GRAPH                  │
│                                                         │
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
│             │    (Written to DB post-match)              │
└─────────────────────────────────────────────────────────┘
```

---

## Project File Structure

```
Care_gap_using_knowledge_graph/
│
├── .env                         # Neo4j credentials
├── requirements.txt             # Python dependencies
├── BCS.pdf                      # HEDIS source guidelines
│
├── bcs_config.py                # NEW: Centralized dynamic configuration engine
├── bcs_logger.py                # Centralized logging (color console + rotating file)
├── schema.py                    # Node labels, properties, and constraints
│
├── bcs_mock_ehr_data.json       # Synthetic EHR clinical data (vitals, history)
├── bcs_mock_sdoh_data.json       # Synthetic SDOH data (barriers, literacy)
│
├── bcs_personas.py              # 51 IdealPersona definitions
├── persona_graph_builder.py     # Loads personas into Neo4j
│
├── bcs_step1_neo4j_load.cypher  # Seed: Load 30 members, providers, plans
├── bcs_step1_runner.py          # Executes the Step 1 Cypher file
├── bcs_ehr_ingestion.py         # NEW: Ingests EHR/SDOH data into graph
│
├── bcs_step2_matching.py        # Step 2 — Matching algorithm (weighted scoring)
├── bcs_step3_inherit.py         # Step 3 — Inherits persona outputs -> Recs
├── bcs_step4_hedis_validate.py  # 10 HEDIS compliance validation checks
├── bcs_step5_outreach.py        # Creates Outreach nodes
├── bcs_step6_analytics.py       # Step 6 — Population health analytics
├── bcs_step7_closure.py         # Step 7 — Gap closure tracking
│
├── bcs_api.py                   # Flask API for population health metrics
├── bcs_check_member.py          # Interactive single-member gap checker
│
├── run_pipeline.bat             # Automation: Executes all 7 steps end-to-end
├── wipe_db.py                   # Utility: Wipes Neo4j for a clean start
└── README.md                    # This file
```

---

## The Persona Rulebook — 51 IdealPersonas

The rulebook is an isolated subgraph of **51 clinically validated personas** covering every meaningful BCS patient type.

| Group | Description |
|---|---|
| **Excluded** | Mastectomy, hospice, frailty, gender surgery |
| **Not Eligible** | Wrong age, gender, or enrollment gaps |
| **Never Screened** | Various risk levels |
| **Overdue** | High/Medium/Low risk personas |
| **Proactive** | Approaching the 24-month gap opening |
| **Compliant** | Valid screening history |

---

## Running the Pipeline

> [!IMPORTANT]
> Ensure Neo4j is running and `.env` is configured.

### The Automated Way (Recommended)
```bash
# Wipes DB and runs all steps (1-4) in sequence
.\run_pipeline.bat
```

### The Manual Way
```bash
# 1. Start fresh
python wipe_db.py

# 2. Load members & personas
python bcs_step1_runner.py
python persona_graph_builder.py

# 3. Enrich with EHR/SDOH data
python bcs_ehr_ingestion.py

# 4. Run analytics & outreach pipeline
python bcs_step2_matching.py
python bcs_step3_inherit.py
python bcs_step4_hedis_validate.py
```

---

## HEDIS Validation Result
The pipeline is verified against the Hopkins BCS-E rulebook.

| # | Check | Result |
|---|---|---|
| 1-10 | Comprehensive HEDIS Compliance | **10/10 PASS ✅** |

---

## Changelog

| Date | Version | Change |
|---|---|---|
| 2026-04-26 | v1.3 | **EHR & Dynamic Config Update**: Created `bcs_config.py` for centralized clinical rules. Expanded `bcs_mock_ehr_data.json` and created `bcs_mock_sdoh_data.json`. Refactored all steps to remove hardcoding. Fixed session leaks and ID mismatches (M0011). Added `run_pipeline.bat` and `wipe_db.py`. |
| 2026-04-20 | v1.2 | Added `bcs_logger.py` — integrated centralized logging across all steps. |
| 2026-04-20 | v1.1 | Cleanup — removed legacy files. |
| 2026-04-19 | v1.0 | Initial release — 7-step pipeline + 51 persona rulebook. |

---

*Hopkins BCS-E HEDIS Measure | Knowledge Graph Engine v1.3 | 2026*


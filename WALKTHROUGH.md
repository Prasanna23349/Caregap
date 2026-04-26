# 🚀 BCS Care Gap Knowledge Graph Engine – Walkthrough

## Overview
The **BCS Care Gap Knowledge Graph Engine** is a **HEDIS BCS‑E compliant** solution that leverages a **Neo4j Knowledge Graph** to:
- Detect breast‑cancer‑screening gaps.
- Match members to 51 clinically‑validated **IdealPersonas**.
- Generate personalized outreach recommendations.
- Track gap‑closure over time.

It demonstrates a modern, data‑centric architecture for population‑health analytics.

---

## Core Concepts
| Concept | What it means |
|---|---|
| **Dynamic Configuration** | Clinical rules (age ranges, look‑back windows, CPT codes, etc.) are stored as `QualityMeasure` nodes in Neo4j and loaded at runtime via `bcs_config.py`. No code changes are needed to tweak measures. |
| **EHR & SDOH Enrichment** | Synthetic (or real) clinical and social‑determinant‑of‑health data replace placeholder values, giving each member a realistic profile. |
| **Persona Rulebook** | 51 `IdealPersona` definitions capture every meaningful BCS patient type. A weighted‑scoring algorithm matches members to these personas. |
| **Automated HEDIS Validation** | A 10‑point checklist (`bcs_step4_hedis_validate.py`) verifies data integrity and compliance before outreach. |

---

## Architecture Snapshot
```text
┌─────────────────────────────────────────────────┐
│               NEO4J KNOWLEDGE GRAPH             │
│                                                 │
│  ┌───────────────┐   ┌─────────────────────┐   │
│  │ MEMBER SUBGRAPH│   │ PERSONA RULEBOOK   │   │
│  │ (≈30 members) │   │ (51 IdealPersonas) │   │
│  └───────┬───────┘   └───────┬─────────────┘   │
│          │ MATCHED_TO       │               │
│          ▼                  ▼               │
│  ┌───────────────────────────────────────┐   │
│  │ GAP ANALYTICS & OUTREACH (Recommendations)│ │
│  └───────────────────────────────────────┘   │
└─────────────────────────────────────────────────┘
```
- **Member Subgraph** – Demographics, enrollment, claims, clinical history, vitals, SDOH.
- **Persona Rulebook** – Isolated subgraph containing persona nodes and rule logic.
- **Gap Analytics & Outreach** – Matches members → validates HEDIS → creates `Outreach` nodes with personalised actions.

---

## Project Layout
```
Care_gap_using_knowledge_graph/
│   .env                # Neo4j credentials
│   requirements.txt    # Python deps
│   BCS.pdf             # HEDIS source doc
│
├─ bcs_config.py        # Dynamic config loader
├─ bcs_logger.py        # Centralised logger (console + rotating file)
├─ schema.py            # Neo4j schema definitions
│
├─ bcs_mock_ehr_data.json   # Synthetic EHR data
├─ bcs_mock_sdoh_data.json  # Synthetic SDOH data
│
├─ bcs_personas.py          # 51 IdealPersona class definitions
├─ persona_graph_builder.py # Loads persona subgraph into Neo4j
│
├─ bcs_step1_neo4j_load.cypher   # Seed data (members, providers, plans)
├─ bcs_step1_runner.py           # Executes step‑1 cypher
├─ bcs_ehr_ingestion.py          # Loads EHR & SDOH data into member subgraph
│
├─ bcs_step2_matching.py        # Weighted scoring & persona match
├─ bcs_step3_inherit.py         # Propagates persona output to recommendations
├─ bcs_step4_hedis_validate.py  # 10‑point HEDIS checks
├─ bcs_step5_outreach.py         # Generates Outreach nodes
├─ bcs_step6_analytics.py        # Population‑health analytics
├─ bcs_step7_closure.py          # Tracks gap‑closure events
│
├─ bcs_api.py                   # Flask API (metrics & member endpoint)
├─ bcs_check_member.py          # CLI for single‑member gap check
│
├─ run_pipeline.bat              # End‑to‑end automation (wipe → steps 1‑7)
└─ wipe_db.py                    # Utility to clear Neo4j DB
```

---

## Setup & Prerequisites
1. **Neo4j** – Install Neo4j Desktop or a Neo4j Server (v5+). Create a database and note the Bolt URL, username, and password.
2. **Python 3.10+** – Create a virtual environment and install deps:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate   # Windows
   pip install -r requirements.txt
   ```
3. **Environment file** – Copy `.env.example` to `.env` and populate:
   ```text
   NEO4J_URI=bolt://localhost:7687
   NEO4J_USER=neo4j
   NEO4J_PASSWORD=your_password
   ```
4. (Optional) Open the folder in VS Code for easy navigation.

---

## Running the Pipeline
### Automated (recommended)
```bat
run_pipeline.bat
```
This script:
1. Wipes the Neo4j database.
2. Loads members & personas.
3. Ingests synthetic EHR/SDOH data.
4. Performs matching, validation, outreach, analytics, and closure tracking.

### Manual Step‑by‑Step
```bash
python wipe_db.py
python bcs_step1_runner.py
python persona_graph_builder.py
python bcs_ehr_ingestion.py
python bcs_step2_matching.py
python bcs_step3_inherit.py
python bcs_step4_hedis_validate.py
python bcs_step5_outreach.py
python bcs_step6_analytics.py
python bcs_step7_closure.py
```
Each script logs progress to the console and to `bcs_engine.log` (rotating daily).

---

## API
Start the Flask API with:
```bash
python bcs_api.py
```
Endpoints:
- `GET /metrics` – Population‑level statistics (compliance %, overdue, proactive, etc.)
- `GET /member/<member_id>` – Gap status, matched persona, and outreach recommendations for a specific member.

---

## Testing & Validation
- **HEDIS Validation** – Run `bcs_step4_hedis_validate.py` to see a PASS/FAIL table (see *HEDIS Validation Result* section).
- **Unit Tests** – If a `tests/` folder exists, execute via `pytest tests/`.
- **Spot‑Check** – Use `bcs_check_member.py <member_id>` to view a single member’s gap analysis.

---

## Extending the Engine
1. **Add New Measures** – Create a new `QualityMeasure` node in Neo4j; it will be consumed automatically by `bcs_config.py`.
2. **Add Personas** – Define additional `IdealPersona` objects in `bcs_personas.py` and re‑run `persona_graph_builder.py`.
3. **Custom Scoring** – Modify `bcs_step2_matching.py` to adjust weights or incorporate new attributes.
4. **Real Data Integration** – Replace the synthetic JSON files with real EHR/SDOH extracts and adapt `bcs_ehr_ingestion.py` accordingly.

---

## Changelog
| Date | Version | Change |
|---|---|---|
| 2026‑04‑26 | v1.3 | Dynamic config (`bcs_config.py`), synthetic EHR/SDOH, refactored steps, improved logging, full pipeline automation (`run_pipeline.bat`). |
| 2026‑04‑20 | v1.2 | Centralised logging (`bcs_logger.py`). |
| 2026‑04‑20 | v1.1 | Cleanup of legacy files and docs. |
| 2026‑04‑19 | v1.0 | Initial 7‑step pipeline + 51‑persona rulebook. |

---

## License & Acknowledgements
This project is licensed under the **MIT License**. The HEDIS BCS‑E measure specifications are sourced from the **Hopkins Health Plan** guidelines (see `BCS.pdf`).

---

*Hopkins BCS‑E HEDIS Measure | Knowledge Graph Engine v1.3 | 2026*

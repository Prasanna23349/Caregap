"""
BCS-E Breast Cancer Screening — 51 Realistic Persona Combinations

Replaces the old 3,072 brute-force boolean model with 51 clinically valid,
real-world personas based on HEDIS BCS-E guidelines.

Combination logic:
  NOT_ELIGIBLE:  3 personas (gender / age / enrollment)
  COMPLIANT/OPEN_GAP: 3 GC × 2 age bands × 2 mammogram = 12
  EXCLUDED (42-65): 3 GC × 5 exclusions = 15  (no frailty/SNP for <66)
  EXCLUDED (66-74): 3 GC × 7 exclusions = 21
  Total: 51
"""

import os, json
from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

URI      = os.getenv("NEO4J_URI")
USER     = os.getenv("NEO4J_USERNAME")
PASSWORD = os.getenv("NEO4J_PASSWORD")
DB       = os.getenv("NEO4J_DATABASE")

# ── Dimensions ────────────────────────────────────────────────────────────────

GENDER_CRITERIA = [
    {"code": "GC1", "label": "AdministrativeGender=Female",
     "description": "Administrative Gender of Female at any time in member history"},
    {"code": "GC2", "label": "SexAssignedAtBirth=Female",
     "description": "Sex Assigned at Birth (LOINC 76689-9) of Female (LOINC LA3-6) at any time in member history"},
    {"code": "GC3", "label": "SexParamClinicalUse=Female",
     "description": "Sex Parameter for Clinical Use of Female (female-typical) during measurement period"},
]

AGE_BANDS = [
    {"code": "AB1", "label": "Age 42-65", "min_age": 42, "max_age": 65},
    {"code": "AB2", "label": "Age 66-74", "min_age": 66, "max_age": 74},
]

# Exclusions available per age band (HEDIS rules)
# Frailty+advanced illness and Institutional SNP/LTC apply only to 66+
EXCLUSIONS_AB1 = [
    "bilateral_mastectomy",
    "unilateral_mastectomy_both_sides",
    "gender_affirming_chest_surgery",
    "hospice_or_palliative",
    "deceased",
]

EXCLUSIONS_AB2 = [
    "bilateral_mastectomy",
    "unilateral_mastectomy_both_sides",
    "gender_affirming_chest_surgery",
    "hospice_or_palliative",
    "deceased",
    "frailty_advanced_illness",
    "institutional_snp_or_ltc_66plus",
]

# Exclusion priority order (highest first) — used by engine for multi-exclusion members
EXCLUSION_PRIORITY = [
    "deceased",
    "hospice_or_palliative",
    "bilateral_mastectomy",
    "unilateral_mastectomy_both_sides",
    "gender_affirming_chest_surgery",
    "frailty_advanced_illness",
    "institutional_snp_or_ltc_66plus",
]

MAMMOGRAPHY_CPT = ["77062", "77061", "77066", "77065", "77063", "77067"]

EXCLUSION_CODES = {
    "bilateral_mastectomy": {
        "ICD10PCS": ["0HTV0ZZ"],
        "ICD10CM":  ["Z90.13"],
    },
    "unilateral_mastectomy_both_sides": {
        "CPT":      ["19180", "19200", "19220", "19240", "19303", "19304", "19305", "19306", "19307"],
        "Modifier": ["50", "LT", "RT"],
        "ICD10CM":  ["Z90.12", "Z90.11"],
        "ICD10PCS": ["0HTU0ZZ", "0HTT0ZZ"],
    },
    "gender_affirming_chest_surgery": {
        "CPT":     ["19318"],
        "ICD10CM": ["F64.1", "F64.2", "F64.8", "F64.9", "Z87.890"],
    },
}


# ── Build 51 Realistic Personas ──────────────────────────────────────────────

def build_realistic_personas():
    personas = []
    idx = 1

    # ── 3 NOT_ELIGIBLE personas ──────────────────────────────────────────────
    for reason, desc in [
        ("gender_not_female", "None of GC1/GC2/GC3 criteria met — gender not Female"),
        ("age_outside_range", "Age outside eligible range 42-74"),
        ("not_enrolled",      "Continuous enrollment requirement not met"),
    ]:
        personas.append({
            "persona_id":           f"BCS_P{idx:03d}",
            "measure":              "BCS-E",
            "care_gap_status":      "NOT_ELIGIBLE",
            "not_eligible_reason":  reason,
            "gender_criteria_code": None,
            "age_band_code":        None,
            "exclusion_reason":     None,
            "mammogram_found":      None,
            "description":          f"NOT_ELIGIBLE: {desc}",
        })
        idx += 1

    # ── 12 COMPLIANT / OPEN_GAP personas ─────────────────────────────────────
    for gc in GENDER_CRITERIA:
        for ab in AGE_BANDS:
            for mammo in [True, False]:
                status = "COMPLIANT" if mammo else "OPEN_GAP"
                personas.append({
                    "persona_id":           f"BCS_P{idx:03d}",
                    "measure":              "BCS-E",
                    "care_gap_status":      status,
                    "not_eligible_reason":  None,
                    "gender_criteria_code": gc["code"],
                    "gender_criteria_label": gc["label"],
                    "age_band_code":        ab["code"],
                    "age_band_label":       ab["label"],
                    "min_age":              ab["min_age"],
                    "max_age":              ab["max_age"],
                    "exclusion_reason":     None,
                    "mammogram_found":      mammo,
                    "description": (
                        f"{status}: {gc['label']} | {ab['label']} | "
                        f"Enrolled | No exclusion | Mammogram={'Yes' if mammo else 'No'}"
                    ),
                })
                idx += 1

    # ── EXCLUDED personas (age-band-aware) ───────────────────────────────────
    for gc in GENDER_CRITERIA:
        for ab in AGE_BANDS:
            exclusions = EXCLUSIONS_AB1 if ab["code"] == "AB1" else EXCLUSIONS_AB2
            for excl in exclusions:
                personas.append({
                    "persona_id":           f"BCS_P{idx:03d}",
                    "measure":              "BCS-E",
                    "care_gap_status":      "EXCLUDED",
                    "not_eligible_reason":  None,
                    "gender_criteria_code": gc["code"],
                    "gender_criteria_label": gc["label"],
                    "age_band_code":        ab["code"],
                    "age_band_label":       ab["label"],
                    "min_age":              ab["min_age"],
                    "max_age":              ab["max_age"],
                    "exclusion_reason":     excl,
                    "mammogram_found":      None,
                    "description": (
                        f"EXCLUDED: {gc['label']} | {ab['label']} | "
                        f"Enrolled | Exclusion={excl}"
                    ),
                })
                idx += 1

    return personas


# ── Neo4j Loader ─────────────────────────────────────────────────────────────

def load_graph(driver, personas):
    with driver.session(database=DB) as session:
        session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (p:Persona) REQUIRE p.persona_id IS UNIQUE")
        session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (m:Measure) REQUIRE m.measure_id IS UNIQUE")
        session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (c:ComplianceCode) REQUIRE c.code IS UNIQUE")
        session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (e:ExclusionCode) REQUIRE e.code IS UNIQUE")

        # Clear old personas
        session.run("MATCH (p:Persona) DETACH DELETE p")

        # Measure node
        session.run("""
            MERGE (m:Measure {measure_id: 'BCS-E'})
            SET m.name             = 'Breast Cancer Screening',
                m.product_lines    = 'Advantage MD, EHP, Priority Partners, USFHP',
                m.eligible_age_min = 42,
                m.eligible_age_max = 74,
                m.eligible_gender  = 'Female',
                m.lookback_start   = 'Oct 1 two years prior to measurement year',
                m.lookback_end     = 'Dec 31 of measurement year',
                m.measurement_year = 2026
        """)

        # Compliance codes
        for cpt in MAMMOGRAPHY_CPT:
            session.run("""
                MERGE (c:ComplianceCode {code: $code})
                SET c.type = 'CPT', c.measure = 'BCS-E', c.description = 'Mammography CPT'
                WITH c MATCH (m:Measure {measure_id: 'BCS-E'})
                MERGE (m)-[:HAS_COMPLIANCE_CODE]->(c)
            """, code=cpt)

        # Exclusion codes
        for excl_name, code_map in EXCLUSION_CODES.items():
            for code_type, codes in code_map.items():
                for code in codes:
                    session.run("""
                        MERGE (e:ExclusionCode {code: $code})
                        SET e.type = $code_type, e.exclusion_reason = $excl_name, e.measure = 'BCS-E'
                        WITH e MATCH (m:Measure {measure_id: 'BCS-E'})
                        MERGE (m)-[:HAS_EXCLUSION_CODE]->(e)
                    """, code=code, code_type=code_type, excl_name=excl_name)

        # Load personas in batch
        session.run("""
            UNWIND $personas AS p
            MERGE (n:Persona {persona_id: p.persona_id})
            SET n += p
            WITH n
            MATCH (m:Measure {measure_id: 'BCS-E'})
            MERGE (n)-[:BELONGS_TO_MEASURE]->(m)
        """, personas=personas)

        print(f"Loaded {len(personas)} realistic BCS-E personas into Neo4j.")


def print_summary(personas):
    from collections import Counter
    status_counts = Counter(p["care_gap_status"] for p in personas)
    print(f"\n{'='*60}")
    print("BCS-E Realistic Persona Summary (51 combinations)")
    print(f"{'='*60}")
    print(f"Total personas: {len(personas)}")
    for status, count in sorted(status_counts.items()):
        print(f"  {status:<15}: {count:>3}")
    print(f"\nBreakdown:")
    print(f"  NOT_ELIGIBLE:     3 (gender / age / enrollment)")
    print(f"  COMPLIANT/OPEN:  12 (3 GC × 2 age × 2 mammogram)")
    print(f"  EXCLUDED 42-65:  15 (3 GC × 5 exclusions)")
    print(f"  EXCLUDED 66-74:  21 (3 GC × 7 exclusions)")
    print(f"{'='*60}\n")

    print(f"{'#':<4} {'ID':<10} {'Status':<14} {'GC':<5} {'AB':<5} {'Exclusion':<35} {'Mammo'}")
    print("-" * 95)
    for i, p in enumerate(personas, 1):
        print(
            f"{i:<4} {p['persona_id']:<10} {p['care_gap_status']:<14} "
            f"{(p.get('gender_criteria_code') or '-'):<5} "
            f"{(p.get('age_band_code') or '-'):<5} "
            f"{(p.get('exclusion_reason') or '-'):<35} "
            f"{str(p.get('mammogram_found') or '-')}"
        )


def main():
    personas = build_realistic_personas()
    print_summary(personas)

    out_path = os.path.join(os.path.dirname(__file__), "bcs_all_combinations.json")
    with open(out_path, "w") as f:
        json.dump(personas, f, indent=2)
    print(f"\nSaved to: {out_path}")

    driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))
    try:
        driver.verify_connectivity()
        print("Neo4j connected. Loading personas...\n")
        load_graph(driver, personas)
    finally:
        driver.close()


if __name__ == "__main__":
    main()
